"""Schema Agent: links user query to relevant DuckDB tables and enriches with metadata."""
from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.data.duckdb_connector import describe_user_tables

logger = logging.getLogger(__name__)

_chroma_client = None
_chroma_collection = None


def init_chroma() -> None:
    """Create the ChromaDB collection (called once at startup — no data loaded yet)."""
    global _chroma_client, _chroma_collection
    try:
        import chromadb

        _chroma_client = chromadb.EphemeralClient()
        _chroma_collection = _chroma_client.get_or_create_collection(
            "schema_embeddings",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("[schema] ChromaDB initialised")
    except Exception as exc:
        logger.warning("[schema] ChromaDB unavailable (%s); will send full schema to LLM", exc)


def _build_chroma_docs(
    user_tables: dict,
    user_id: str,
) -> tuple[list[str], list[str], list[dict]]:
    """Return (documents, ids, metadatas) for Chroma upsert — scoped to one user."""
    docs, ids, metas = [], [], []
    for table_name, info in user_tables.items():
        cols = ", ".join(c["column"] for c in info.get("schema", []))
        docs.append(f"Table {table_name}: columns are {cols}")
        ids.append(table_name)
        metas.append({"user_id": user_id})
    return docs, ids, metas


def search_schema(
    query: str,
    user_id: str,
    n_results: int = 6,
    selected_only: list[str] | None = None,
) -> dict:
    """Return relevant table schemas for *query*, strictly scoped to *user_id*.

    Includes CSV-uploaded and Athena-loaded tables (both live in DuckDB).
    If *selected_only* is non-empty, restrict to those table names.
    """
    user_tables = describe_user_tables(user_id)
    if not user_tables:
        return {}

    if selected_only:
        user_tables = {k: v for k, v in user_tables.items() if k in selected_only}
        if not user_tables:
            return {}

    if _chroma_collection is not None:
        try:
            # Only index THIS user's tables — never touch other users' schemas.
            docs, ids, metas = _build_chroma_docs(user_tables, user_id)
            if docs:
                _chroma_collection.upsert(documents=docs, ids=ids, metadatas=metas)

            results = _chroma_collection.query(
                query_texts=[query],
                n_results=min(n_results, max(1, len(user_tables))),
                where={"user_id": user_id},  # hard filter: only this user's tables
            )
            relevant_names = results["ids"][0]
            filtered = {name: user_tables[name] for name in relevant_names if name in user_tables}
            if filtered:
                return filtered
        except Exception as exc:
            logger.warning("[schema] ChromaDB query failed (%s); returning full user schema", exc)

    return user_tables


def refresh_chroma(user_id: str) -> None:
    """Re-embed *user_id*'s tables after a schema change (upload, delete, Athena load)."""
    if _chroma_collection is None:
        return
    try:
        user_tables = describe_user_tables(user_id)
        docs, ids, metas = _build_chroma_docs(user_tables, user_id)
        if docs:
            _chroma_collection.upsert(documents=docs, ids=ids, metadatas=metas)
        logger.info(
            "[schema] ChromaDB refreshed: %d tables for user=%s", len(docs), user_id[:8]
        )
    except Exception as exc:
        logger.warning("[schema] refresh_chroma failed: %s", exc)


def _load_metadata_sync(user_id: str, table_names: list[str]) -> dict[str, dict]:
    """Load rich table/column metadata from PostgreSQL synchronously."""
    try:
        import asyncio
        import concurrent.futures

        async def _fetch():
            from sqlalchemy import select

            from app.core.db import AsyncSessionLocal
            from app.models.table_metadata import TableMetadata

            result: dict[str, dict] = {}
            async with AsyncSessionLocal() as db:
                rows = await db.execute(
                    select(TableMetadata).where(
                        TableMetadata.user_id == user_id,
                        TableMetadata.table_key.in_(table_names),
                    )
                )
                for tm in rows.scalars():
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
                    join_hints: list[dict] = []
                    if tm.join_hints:
                        try:
                            join_hints = json.loads(tm.join_hints)
                        except Exception:
                            pass
                    result[tm.table_key] = {
                        "description": tm.description or "",
                        "business_context": tm.business_context or "",
                        "display_name": tm.display_name or "",
                        "join_hints": join_hints,
                        "columns": cols,
                    }
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _fetch())
            return future.result(timeout=5)
    except Exception as exc:
        logger.warning("[schema] Could not load metadata from DB: %s", exc)
        return {}


def _format_table_listing(user_tables: dict) -> str:
    """Format all user tables as a human-readable listing reply."""
    if not user_tables:
        return (
            "You don't have any datasets yet.\n\n"
            "Upload a CSV from the **Datasets** page or load an Athena table from the **Athena** page."
        )
    lines = [f"You have **{len(user_tables)}** dataset(s) available:\n"]
    for table_name, info in user_tables.items():
        cols = [c["column"] for c in info.get("schema", [])]
        sample = info.get("sample", [])
        lines.append(f"**{table_name}**")
        lines.append(f"  Columns ({len(cols)}): {', '.join(cols)}")
        if sample:
            first = sample[0]
            preview = ", ".join(f"{k}: {v!r}" for k, v in list(first.items())[:3])
            lines.append(f"  Sample row: {preview}")
        lines.append("")
    lines.append("Ask a question about any of these to start querying.")
    return "\n".join(lines)


def schema_agent_node(state: AgentState) -> dict:
    """LangGraph node: populate schema_context from the latest user message."""
    user_id = state.get("user_id", "")
    current_step = state.get("current_step", "schema")

    if current_step == "schema_only":
        logger.info("[schema] Listing mode for user=%s", user_id[:8])
        all_tables = describe_user_tables(user_id) if user_id else {}
        reply = AIMessage(content=_format_table_listing(all_tables))
        return {
            "messages": [reply],
            "schema_context": {},
            "current_step": "done",
            "steps_taken": ["schema_agent"],
            "error": "",
        }

    user_query = (
        state.get("cleaned_question")
        or next((m.content for m in reversed(state["messages"]) if m.type == "human"), "")
    )
    logger.info("[schema] Searching schema for user=%s query=%s", user_id[:8], user_query[:80])

    selected_datasets = state.get("selected_datasets") or []
    schema_context = search_schema(user_query, user_id, selected_only=selected_datasets)
    logger.info("[schema] Found %d relevant tables: %s", len(schema_context), list(schema_context))

    if not schema_context:
        reply = AIMessage(
            content=(
                "I couldn't find any data tables for your question. "
                "Please upload a CSV file or load an Athena table on the Athena page."
            )
        )
        return {
            "messages": [reply],
            "schema_context": {},
            "current_step": "done",
            "steps_taken": ["schema_agent"],
            "error": "no_schema",
        }

    # Detect query engine based on whether Athena direct refs are present
    query_engine = "duckdb"
    has_duckdb = any(not info.get("athena_direct") for info in schema_context.values())
    has_athena_direct = any(info.get("athena_direct") for info in schema_context.values())

    if has_athena_direct and has_duckdb:
        # Mixed engines: filter to only Athena direct tables and warn
        schema_context = {k: v for k, v in schema_context.items() if v.get("athena_direct")}
        query_engine = "athena"
        logger.info(
            "[schema] Mixed engines detected — restricting to Athena direct tables only (user=%s)",
            user_id[:8],
        )
    elif has_athena_direct:
        query_engine = "athena"

    logger.info("[schema] query_engine=%s for user=%s", query_engine, user_id[:8])

    # Attach pre-loaded metadata (passed from the async chat endpoint to avoid
    # asyncio.run()-in-thread crashes on Windows with asyncpg)
    preloaded_metadata = state.get("preloaded_metadata") or {}
    for table_name in schema_context:
        if table_name in preloaded_metadata:
            schema_context[table_name]["metadata"] = preloaded_metadata[table_name]

    # Build human-readable summary
    lines = []
    for table, info in schema_context.items():
        meta = info.get("metadata", {})
        display = meta.get("display_name") or table
        desc = meta.get("description") or ""
        col_meta = meta.get("columns", {})
        cols = []
        for c in info["schema"]:
            col_desc = col_meta.get(c["column"], {}).get("description", "")
            col_str = f"{c['column']} ({c['type']})"
            if col_desc:
                col_str += f" — {col_desc}"
            cols.append(col_str)
        line = f"- **{display}**: {', '.join(cols)}"
        if desc:
            line += f"\n  _{desc}_"
        if info.get("athena_direct"):
            line += f"\n  _(Athena direct — {info['athena_database']}.{info['athena_table']})_"
        lines.append(line)
    schema_summary = "\n".join(lines)

    glossary = state.get("glossary_context", [])
    glossary_text = ""
    if glossary:
        glossary_text = "\n\n**Business glossary:**\n" + "\n".join(
            f"- {g['term']}: {g['definition']}" for g in glossary
        )

    athena_warning = ""
    if query_engine == "athena":
        athena_warning = (
            "\n\n> **Note:** This query will run directly on Athena. "
            "Joins with CSV or DuckDB tables are not supported in direct mode."
        )

    reply = AIMessage(
        content=(
            f"Found relevant tables:\n\n{schema_summary}"
            f"{glossary_text}"
            f"{athena_warning}\n\nGenerating SQL query now."
        )
    )

    return {
        "messages": [reply],
        "schema_context": schema_context,
        "current_step": "schema_done",
        "query_engine": query_engine,
        "steps_taken": ["schema_agent"],
    }
