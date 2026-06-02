"""
Chat API — the primary HTTP interface between the Next.js frontend and the LangGraph pipeline.

Endpoints
---------
POST /chat          Start a new message on a thread. Invokes the graph and either:
                      - Returns status="done" with the assistant reply + optional chart.
                      - Returns status="needs_approval" when the SQL agent hits interrupt().
POST /chat/resume   Resume a paused graph after the user approves / rejects / edits SQL.
                    Calls graph.ainvoke(Command(resume=decision)) to continue from the
                    exact point of the interrupt with all prior state intact.
POST /chat/echo     Auth-protected health-check that echoes the message back (Day 2 artifact).
GET  /chat/graph    Returns the LangGraph pipeline as a Mermaid diagram (debug helper).

Two-database usage
------------------
- PostgreSQL (via SQLAlchemy): persists Thread and Message records so the chat
  history sidebar works even after a server restart.
- LangGraph checkpointer (MemorySaver in dev / AsyncPostgresSaver in prod):
  stores the full AgentState between the interrupt and the resume so the graph
  can continue mid-execution without re-running schema linking or SQL generation.
"""
import asyncio
import json
import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import is_rate_limited
from app.models.glossary import GlossaryEntry
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class EchoRequest(BaseModel):
    message: str


class EchoResponse(BaseModel):
    role: str = "assistant"
    content: str


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    selected_datasets: list[str] = []


class ChatResponse(BaseModel):
    thread_id: str
    role: str = "assistant"
    content: str
    status: str = "done"
    draft_sql: str = ""
    sql_explanation: str = ""
    chart_json: str = ""
    query_results: list[dict] = []
    executed_sql: str = ""
    steps_taken: list[str] = []
    interpretation_note: str = ""
    cleaned_question: str = ""


class ResumeRequest(BaseModel):
    thread_id: str
    action: str                    # "approve" | "reject" | "edit"
    edited_sql: str = ""


def _get_graph(request: Request):
    """Retrieve the compiled LangGraph instance from FastAPI app state."""
    return request.app.state.graph


def _sanitize_meta(obj):
    """Recursively replace float NaN/Infinity with None so PostgreSQL JSON accepts the payload."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_meta(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_meta(v) for v in obj]
    return obj


@router.get("/graph")
async def get_graph_definition(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the LangGraph pipeline as a Mermaid diagram string."""
    graph = _get_graph(request)
    mermaid = graph.get_graph().draw_mermaid()
    return {"mermaid": mermaid}


def _extract_interrupt(result: dict) -> dict | None:
    """Return the first interrupt value if the graph is paused, else None."""
    interrupts = result.get("__interrupt__")
    if interrupts:
        return interrupts[0].value  # Interrupt(value=...)
    return None


@router.post("/echo", response_model=EchoResponse)
async def echo(body: EchoRequest, current_user: User = Depends(get_current_user)):
    return EchoResponse(content=f"Echo: {body.message}")


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a new message and run the LangGraph pipeline.

    The graph is invoked with the user's message plus their glossary entries and
    user_id.  If sql_agent hits interrupt(), the response carries
    status="needs_approval" with draft_sql so the frontend can show the approval
    panel.  On a normal (non-interrupt) completion the assistant reply and optional
    chart_json are returned with status="done".

    Both the user message and the final assistant reply are persisted to PostgreSQL
    so the chat history sidebar can reconstruct the conversation after a restart.
    """
    if is_rate_limited(f"chat:{current_user.id}", limit=settings.CHAT_RATE_LIMIT_PER_MINUTE):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: max {settings.CHAT_RATE_LIMIT_PER_MINUTE} messages per minute.",
        )

    graph = _get_graph(request)

    # ── Thread / initial message persistence ────────────────────────────────
    try:
        thread = await db.get(Thread, body.thread_id)
        if thread is None:
            thread = Thread(
                id=body.thread_id,
                user_id=current_user.id,
                title=body.message[:60],
            )
            db.add(thread)
            await db.flush()
        elif thread.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Thread belongs to another user")

        db.add(Message(thread_id=thread.id, role="user", content=body.message))
        # Commit thread + user message NOW so the thread appears in the sidebar
        # immediately — before the graph runs (which can take 10-60 s).
        await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[chat] DB error during thread setup: %s", exc)
        raise HTTPException(status_code=500, detail="Database error setting up thread")

    # ── Glossary (non-fatal if unavailable) ─────────────────────────────────
    glossary_context: list[dict] = []
    try:
        glossary_rows = await db.execute(
            select(GlossaryEntry).where(GlossaryEntry.user_id == current_user.id)
        )
        glossary_context = [
            {"term": g.term, "definition": g.definition}
            for g in glossary_rows.scalars()
        ]
    except Exception as exc:
        logger.warning("[chat] Could not load glossary: %s", exc)

    # ── Pre-load Athena credentials (avoids asyncio.run() inside threads on Windows) ──
    athena_creds: dict = {}
    try:
        import json as _json
        from app.models.athena_config import AthenaConfig
        for owner_id, source_key, is_global in [(current_user.id, "personal", False), (None, "global", True)]:
            row = await db.execute(
                select(AthenaConfig).where(
                    AthenaConfig.is_global == True if is_global else AthenaConfig.user_id == owner_id  # noqa: E712
                )
            )
            cfg = row.scalar_one_or_none()
            if cfg and cfg.aws_access_key_id and cfg.aws_secret_access_key:
                athena_creds[source_key] = {
                    "aws_region": cfg.aws_region,
                    "aws_access_key_id": cfg.aws_access_key_id,
                    "aws_secret_access_key": cfg.aws_secret_access_key,
                    "athena_workgroup": cfg.athena_workgroup,
                    "athena_output_bucket": cfg.athena_output_bucket,
                    "source": source_key,
                }
    except Exception as exc:
        logger.warning("[chat] Could not pre-load Athena creds: %s", exc)

    # ── Pre-load table metadata (avoids asyncio.run() inside threads on Windows) ──
    preloaded_metadata: dict = {}
    try:
        from app.models.table_metadata import TableMetadata
        meta_rows = await db.execute(
            select(TableMetadata).where(TableMetadata.user_id == current_user.id)
        )
        for tm in meta_rows.scalars():
            cols = {}
            for cm in (tm.columns or []):
                sample_vals: list = []
                if cm.sample_values:
                    try:
                        sample_vals = _json.loads(cm.sample_values)
                    except Exception:
                        pass
                cols[cm.column_name] = {
                    "description": cm.description or "",
                    "display_name": cm.display_name or "",
                    "is_kpi": cm.is_kpi,
                    "kpi_definition": cm.kpi_definition or "",
                    "sample_values": sample_vals,
                }
            join_hints: list = []
            if tm.join_hints:
                try:
                    join_hints = _json.loads(tm.join_hints)
                except Exception:
                    pass
            preloaded_metadata[tm.table_key] = {
                "description": tm.description or "",
                "business_context": tm.business_context or "",
                "display_name": tm.display_name or "",
                "join_hints": join_hints,
                "columns": cols,
            }
    except Exception as exc:
        logger.warning("[chat] Could not pre-load table metadata: %s", exc)

    # ── Run the LangGraph pipeline ───────────────────────────────────────────
    config = {"configurable": {"thread_id": body.thread_id}}
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {
                    "messages": [HumanMessage(content=body.message)],
                    "glossary_context": glossary_context,
                    "user_id": current_user.id,
                    "selected_datasets": body.selected_datasets,
                    "athena_creds": athena_creds,
                    "preloaded_metadata": preloaded_metadata,
                    "sql_approval_required": current_user.sql_approval_required,
                },
                config=config,
            ),
            timeout=settings.QUERY_TIMEOUT_SECONDS + 60,  # LLM calls add overhead
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out. The query took too long to complete.")
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled by client.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {exc}")

    # ── Graph paused for HITL — surface the SQL for user approval ───────────
    interrupt_val = _extract_interrupt(result)
    if interrupt_val is not None:
        try:
            await db.commit()  # persist user message
        except Exception as exc:
            logger.error("[chat] DB commit failed for interrupt path: %s", exc)
            await db.rollback()
        return ChatResponse(
            thread_id=body.thread_id,
            content="Please review the SQL query below before I execute it.",
            status="needs_approval",
            draft_sql=interrupt_val.get("draft_sql", ""),
            sql_explanation=interrupt_val.get("sql_explanation", ""),
            steps_taken=result.get("steps_taken", []),
        )

    # ── Normal completion ────────────────────────────────────────────────────
    assistant_content: str = result["messages"][-1].content
    meta = _sanitize_meta({
        "chart_json": result.get("chart_json", ""),
        "query_results": result.get("query_results", []),
        "executed_sql": result.get("draft_sql", ""),
        "steps_taken": result.get("steps_taken", []),
        "interpretation_note": result.get("interpretation_note", ""),
        "cleaned_question": result.get("cleaned_question", ""),
    })
    try:
        db.add(Message(thread_id=body.thread_id, role="assistant", content=assistant_content, meta=meta))
        await db.commit()
    except Exception as exc:
        logger.error("[chat] DB commit failed for assistant message: %s", exc)
        await db.rollback()  # restore session so response serialization doesn't crash

    return ChatResponse(
        thread_id=body.thread_id,
        content=assistant_content,
        chart_json=meta["chart_json"],
        query_results=meta["query_results"],
        executed_sql=meta["executed_sql"],
        steps_taken=meta["steps_taken"],
        interpretation_note=meta["interpretation_note"],
        cleaned_question=meta["cleaned_question"],
    )


@router.post("/resume", response_model=ChatResponse)
async def resume(
    body: ResumeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resume a paused graph after the user makes an approval decision.

    The LangGraph checkpointer stored the full AgentState at the moment of the
    interrupt().  Calling ainvoke(Command(resume=decision)) reloads that state
    and continues execution from the sql_agent node onward.

    Actions:
      approve — SQL runs as-is through analysis_agent.
      reject  — Graph ends; no SQL is executed.
      edit    — edited_sql replaces draft_sql, re-validated, then approved.
    """
    graph = _get_graph(request)

    # ── Validate thread ownership ────────────────────────────────────────────
    try:
        thread = await db.get(Thread, body.thread_id)
    except Exception as exc:
        logger.error("[resume] DB error fetching thread: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Thread belongs to another user")

    if body.action not in ("approve", "reject", "edit"):
        raise HTTPException(status_code=400, detail="action must be approve, reject, or edit")

    if body.action == "edit" and not body.edited_sql.strip():
        raise HTTPException(status_code=400, detail="edited_sql required when action is edit")

    # ── Resume the graph ─────────────────────────────────────────────────────
    config = {"configurable": {"thread_id": body.thread_id}}
    decision = {"action": body.action, "edited_sql": body.edited_sql}

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(Command(resume=decision), config=config),
            timeout=settings.QUERY_TIMEOUT_SECONDS + 60,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out. The query took too long to complete.")
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled by client.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {exc}")

    # ── Persist assistant reply ──────────────────────────────────────────────
    assistant_content: str = result["messages"][-1].content
    meta = _sanitize_meta({
        "chart_json": result.get("chart_json", ""),
        "query_results": result.get("query_results", []),
        "executed_sql": result.get("draft_sql", ""),
        "steps_taken": result.get("steps_taken", []),
        "interpretation_note": result.get("interpretation_note", ""),
        "cleaned_question": result.get("cleaned_question", ""),
    })
    try:
        db.add(Message(thread_id=body.thread_id, role="assistant", content=assistant_content, meta=meta))
        await db.commit()
    except Exception as exc:
        logger.error("[resume] DB commit failed: %s", exc)
        await db.rollback()  # restore session so response serialization doesn't crash

    return ChatResponse(
        thread_id=body.thread_id,
        content=assistant_content,
        chart_json=meta["chart_json"],
        query_results=meta["query_results"],
        executed_sql=meta["executed_sql"],
        steps_taken=meta["steps_taken"],
        interpretation_note=meta["interpretation_note"],
        cleaned_question=meta["cleaned_question"],
    )


# ── Streaming endpoint ────────────────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE variant of POST /chat.  Yields server-sent events as each agent node
    completes so the frontend can show live progress instead of a blank wait.

    Event types
    -----------
    {"type": "step",           "step": "<node_name>"}
    {"type": "needs_approval", "draft_sql": "...", "sql_explanation": "...", "steps_taken": [...]}
    {"type": "done",           "content": "...", "chart_json": "...", ...}
    {"type": "error",          "message": "..."}
    """
    if is_rate_limited(f"chat:{current_user.id}", limit=settings.CHAT_RATE_LIMIT_PER_MINUTE):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: max {settings.CHAT_RATE_LIMIT_PER_MINUTE} messages per minute.",
        )

    graph = _get_graph(request)

    # ── Thread / message persistence ─────────────────────────────────────────
    try:
        thread = await db.get(Thread, body.thread_id)
        if thread is None:
            thread = Thread(id=body.thread_id, user_id=current_user.id, title=body.message[:60])
            db.add(thread)
            await db.flush()
        elif thread.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Thread belongs to another user")
        db.add(Message(thread_id=thread.id, role="user", content=body.message))
        await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[stream] DB error during thread setup: %s", exc)
        raise HTTPException(status_code=500, detail="Database error setting up thread")

    # ── Preload context ───────────────────────────────────────────────────────
    glossary_context: list[dict] = []
    try:
        grows = await db.execute(select(GlossaryEntry).where(GlossaryEntry.user_id == current_user.id))
        glossary_context = [{"term": g.term, "definition": g.definition} for g in grows.scalars()]
    except Exception as exc:
        logger.warning("[stream] Could not load glossary: %s", exc)

    athena_creds: dict = {}
    try:
        import json as _json
        from app.models.athena_config import AthenaConfig
        for owner_id, source_key, is_global in [(current_user.id, "personal", False), (None, "global", True)]:
            row = await db.execute(
                select(AthenaConfig).where(
                    AthenaConfig.is_global == True if is_global else AthenaConfig.user_id == owner_id  # noqa: E712
                )
            )
            cfg = row.scalar_one_or_none()
            if cfg and cfg.aws_access_key_id and cfg.aws_secret_access_key:
                athena_creds[source_key] = {
                    "aws_region": cfg.aws_region, "aws_access_key_id": cfg.aws_access_key_id,
                    "aws_secret_access_key": cfg.aws_secret_access_key,
                    "athena_workgroup": cfg.athena_workgroup,
                    "athena_output_bucket": cfg.athena_output_bucket, "source": source_key,
                }
    except Exception as exc:
        logger.warning("[stream] Could not pre-load Athena creds: %s", exc)

    preloaded_metadata: dict = {}
    try:
        from app.models.table_metadata import TableMetadata
        meta_rows = await db.execute(select(TableMetadata).where(TableMetadata.user_id == current_user.id))
        for tm in meta_rows.scalars():
            tcols: dict = {}
            for cm in (tm.columns or []):
                sample_vals: list = []
                if cm.sample_values:
                    try:
                        sample_vals = _json.loads(cm.sample_values)
                    except Exception:
                        pass
                tcols[cm.column_name] = {
                    "description": cm.description or "", "display_name": cm.display_name or "",
                    "is_kpi": cm.is_kpi, "kpi_definition": cm.kpi_definition or "",
                    "sample_values": sample_vals,
                }
            join_hints: list = []
            if tm.join_hints:
                try:
                    join_hints = _json.loads(tm.join_hints)
                except Exception:
                    pass
            preloaded_metadata[tm.table_key] = {
                "description": tm.description or "", "business_context": tm.business_context or "",
                "display_name": tm.display_name or "", "join_hints": join_hints, "columns": tcols,
            }
    except Exception as exc:
        logger.warning("[stream] Could not pre-load table metadata: %s", exc)

    config = {"configurable": {"thread_id": body.thread_id}}
    input_state = {
        "messages": [HumanMessage(content=body.message)],
        "glossary_context": glossary_context,
        "user_id": current_user.id,
        "selected_datasets": body.selected_datasets,
        "athena_creds": athena_creds,
        "preloaded_metadata": preloaded_metadata,
        "sql_approval_required": current_user.sql_approval_required,
    }

    async def generate():
        accumulated: dict = {
            "chart_json": "", "query_results": [], "draft_sql": "",
            "steps_taken": [], "interpretation_note": "", "cleaned_question": "", "sql_explanation": "",
        }
        last_content = ""

        try:
            async with asyncio.timeout(settings.QUERY_TIMEOUT_SECONDS + 60):
                async for chunk in graph.astream(input_state, config=config, stream_mode="updates"):
                    for node_name, updates in chunk.items():
                        if node_name == "__interrupt__":
                            try:
                                interrupt_val = updates[0].value
                            except (IndexError, AttributeError, TypeError):
                                interrupt_val = {}
                            yield f"data: {json.dumps({'type': 'needs_approval', 'draft_sql': interrupt_val.get('draft_sql', ''), 'sql_explanation': interrupt_val.get('sql_explanation', ''), 'steps_taken': accumulated['steps_taken']})}\n\n"
                            return

                        if node_name in ("supervisor", "schema_agent", "sql_agent", "analysis_agent"):
                            yield f"data: {json.dumps({'type': 'step', 'step': node_name})}\n\n"

                        if isinstance(updates, dict):
                            for key in accumulated:
                                val = updates.get(key)
                                if val is not None:
                                    accumulated[key] = val
                            msgs = updates.get("messages")
                            if msgs:
                                lm = msgs[-1]
                                if hasattr(lm, "content"):
                                    last_content = lm.content

        except (TimeoutError, asyncio.TimeoutError):
            yield f"data: {json.dumps({'type': 'error', 'message': 'Request timed out.'})}\n\n"
            return
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("[stream] Pipeline error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return

        smeta = _sanitize_meta({
            "chart_json": accumulated["chart_json"],
            "query_results": accumulated["query_results"],
            "executed_sql": accumulated["draft_sql"],
            "steps_taken": accumulated["steps_taken"],
            "interpretation_note": accumulated["interpretation_note"],
            "cleaned_question": accumulated["cleaned_question"],
        })
        try:
            db.add(Message(thread_id=body.thread_id, role="assistant", content=last_content, meta=smeta))
            await db.commit()
        except Exception as exc:
            logger.error("[stream] DB commit failed: %s", exc)
            await db.rollback()

        yield f"data: {json.dumps({'type': 'done', 'content': last_content, **smeta})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
