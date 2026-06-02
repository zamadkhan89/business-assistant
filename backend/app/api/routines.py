"""Daily Routines API — create routine sets of questions and run them in one click."""
import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models.athena_config import AthenaConfig
from app.models.glossary import GlossaryEntry
from app.models.routine import Routine
from app.models.table_metadata import TableMetadata
from app.models.user import User

router = APIRouter(prefix="/routines", tags=["routines"])


class RoutineIn(BaseModel):
    name: str
    questions: list[str]


class RoutineOut(BaseModel):
    id: str
    name: str
    questions: list[str]
    created_at: str


class RoutineResultItem(BaseModel):
    question: str
    content: str
    chart_json: str
    query_results: list[dict]
    executed_sql: str
    error: str


def _out(r: Routine) -> RoutineOut:
    return RoutineOut(
        id=r.id,
        name=r.name,
        questions=json.loads(r.questions or "[]"),
        created_at=r.created_at.isoformat(),
    )


@router.post("", response_model=RoutineOut, status_code=201)
async def create_routine(
    body: RoutineIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = Routine(user_id=current_user.id, name=body.name, questions=json.dumps(body.questions))
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _out(r)


@router.get("", response_model=list[RoutineOut])
async def list_routines(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Routine)
        .where(Routine.user_id == current_user.id)
        .order_by(Routine.created_at.desc())
    )
    return [_out(r) for r in rows.scalars()]


@router.put("/{routine_id}", response_model=RoutineOut)
async def update_routine(
    routine_id: str,
    body: RoutineIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.get(Routine, routine_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    r.name = body.name
    r.questions = json.dumps(body.questions)
    await db.commit()
    await db.refresh(r)
    return _out(r)


@router.delete("/{routine_id}", status_code=204)
async def delete_routine(
    routine_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.get(Routine, routine_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(r)
    await db.commit()


@router.post("/{routine_id}/run", response_model=list[RoutineResultItem])
async def run_routine(
    routine_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run all questions in the routine and return results as a list."""
    r = await db.get(Routine, routine_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    questions = json.loads(r.questions or "[]")
    graph = request.app.state.graph

    glossary_rows = await db.execute(
        select(GlossaryEntry).where(GlossaryEntry.user_id == current_user.id)
    )
    glossary_context = [
        {"term": g.term, "definition": g.definition}
        for g in glossary_rows.scalars()
    ]

    # Pre-load Athena creds (avoids asyncio.run()-in-thread on Windows)
    athena_creds: dict = {}
    try:
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
    except Exception:
        pass

    # Pre-load table metadata
    preloaded_metadata: dict = {}
    try:
        meta_rows = await db.execute(
            select(TableMetadata).where(TableMetadata.user_id == current_user.id)
        )
        for tm in meta_rows.scalars():
            cols = {}
            for cm in (tm.columns or []):
                sample_vals: list = []
                if cm.sample_values:
                    try:
                        sample_vals = json.loads(cm.sample_values)
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
                    join_hints = json.loads(tm.join_hints)
                except Exception:
                    pass
            preloaded_metadata[tm.table_key] = {
                "description": tm.description or "",
                "business_context": tm.business_context or "",
                "display_name": tm.display_name or "",
                "join_hints": join_hints,
                "columns": cols,
            }
    except Exception:
        pass

    results: list[RoutineResultItem] = []

    for question in questions:
        thread_id = str(uuid.uuid4())  # fresh thread per question
        config = {"configurable": {"thread_id": thread_id}}
        try:
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {
                        "messages": [HumanMessage(content=question)],
                        "glossary_context": glossary_context,
                        "user_id": current_user.id,
                        "selected_datasets": [],
                        "athena_creds": athena_creds,
                        "preloaded_metadata": preloaded_metadata,
                    },
                    config=config,
                ),
                timeout=settings.QUERY_TIMEOUT_SECONDS + 60,
            )
            content = result["messages"][-1].content if result.get("messages") else ""
            results.append(RoutineResultItem(
                question=question,
                content=content,
                chart_json=result.get("chart_json", ""),
                query_results=result.get("query_results", []),
                executed_sql=result.get("draft_sql", ""),
                error="",
            ))
        except Exception as exc:
            results.append(RoutineResultItem(
                question=question,
                content="",
                chart_json="",
                query_results=[],
                executed_sql="",
                error=str(exc),
            ))

    return results
