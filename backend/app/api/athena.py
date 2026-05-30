"""
Athena API — browse the AWS Glue Data Catalog and run Athena queries.

Credential resolution (all active sets are used together):
  - Personal credentials  (athena_configs.user_id = current user's ID)
  - Global shared creds   (athena_configs.user_id = '__global__')
  - Environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) — fallback
    when neither personal nor global is configured in the DB.

Personal credentials are ADDITIVE: they expose additional AWS accounts/databases
alongside the shared connection rather than replacing it.

When querying, pass ?source=personal|global|env so the backend uses the right
credential set for that database.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db
from app.data.athena_connector import (
    AthenaNotConfiguredError,
    get_table_schema,
    list_databases,
    list_tables,
    preview_table,
    run_query,
)
from app.models.athena_config import AthenaConfig
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/athena", tags=["athena"])

_GLOBAL_ID = "__global__"


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AthenaConfigIn(BaseModel):
    aws_region: str = "us-east-1"
    aws_access_key_id: str
    aws_secret_access_key: str
    athena_workgroup: str = "primary"
    athena_output_bucket: str = ""


class AthenaConfigOut(BaseModel):
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key_hint: str
    athena_workgroup: str
    athena_output_bucket: str


class QueryRequest(BaseModel):
    sql: str
    database: str
    source: Optional[str] = None  # "personal" | "global" | "env"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _row_to_dict(cfg: AthenaConfig) -> dict:
    return {
        "aws_region": cfg.aws_region,
        "aws_access_key_id": cfg.aws_access_key_id,
        "aws_secret_access_key": cfg.aws_secret_access_key,
        "athena_workgroup": cfg.athena_workgroup,
        "athena_output_bucket": cfg.athena_output_bucket,
    }


def _row_to_out(cfg: AthenaConfig) -> AthenaConfigOut:
    hint = ("****" + cfg.aws_secret_access_key[-4:]) if len(cfg.aws_secret_access_key) >= 4 else "****"
    return AthenaConfigOut(
        aws_region=cfg.aws_region,
        aws_access_key_id=cfg.aws_access_key_id,
        aws_secret_access_key_hint=hint,
        athena_workgroup=cfg.athena_workgroup,
        athena_output_bucket=cfg.athena_output_bucket,
    )


async def _fetch_cfg(owner_id: str, db: AsyncSession) -> AthenaConfig | None:
    result = await db.execute(select(AthenaConfig).where(AthenaConfig.user_id == owner_id))
    return result.scalar_one_or_none()


async def _resolve_all_creds(user_id: str, db: AsyncSession) -> list[dict]:
    """
    Return all active credential sets for this user, each tagged with 'source'.
    Personal and global are always both included when configured (additive).
    Env vars are included only as a last resort when neither DB source is set.
    """
    from app.core.config import settings

    result: list[dict] = []

    personal = await _fetch_cfg(user_id, db)
    if personal and personal.aws_access_key_id and personal.aws_secret_access_key:
        result.append({**_row_to_dict(personal), "source": "personal"})

    shared = await _fetch_cfg(_GLOBAL_ID, db)
    if shared and shared.aws_access_key_id and shared.aws_secret_access_key:
        result.append({**_row_to_dict(shared), "source": "global"})

    if not result and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        result.append({
            "aws_region": settings.AWS_REGION,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "athena_workgroup": settings.ATHENA_WORKGROUP,
            "athena_output_bucket": settings.ATHENA_OUTPUT_BUCKET,
            "source": "env",
        })

    return result


async def _resolve_creds_by_source(source: str | None, user_id: str, db: AsyncSession) -> dict | None:
    """Return the specific credential set for the given source label, or fall back to best available."""
    all_creds = await _resolve_all_creds(user_id, db)
    if not all_creds:
        return None
    if source:
        for c in all_creds:
            if c["source"] == source:
                return c
    return all_creds[0]  # best available


async def _upsert_cfg(owner_id: str, body: AthenaConfigIn, db: AsyncSession) -> AthenaConfig:
    cfg = await _fetch_cfg(owner_id, db)
    if cfg is None:
        cfg = AthenaConfig(user_id=owner_id)
        db.add(cfg)
    cfg.aws_region = body.aws_region.strip() or "us-east-1"
    cfg.aws_access_key_id = body.aws_access_key_id.strip()
    cfg.aws_secret_access_key = body.aws_secret_access_key.strip()
    cfg.athena_workgroup = body.athena_workgroup.strip() or "primary"
    cfg.athena_output_bucket = body.athena_output_bucket.strip()
    await db.commit()
    await db.refresh(cfg)
    return cfg


def _is_admin(user: User) -> bool:
    from app.core.config import settings as _s
    raw = _s.ADMIN_EMAILS.strip()
    if not raw:
        return True  # no restriction configured
    emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return user.email.lower() in emails


def _require_admin(user: User) -> None:
    if not _is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can modify the shared Athena connection. Contact your admin.",
        )


def _handle_athena_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AthenaNotConfiguredError):
        return HTTPException(status_code=503, detail=str(exc))
    logger.error("[athena] Unexpected error: %s", exc)
    return HTTPException(status_code=500, detail=str(exc))


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def athena_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.config import settings

    personal = await _fetch_cfg(current_user.id, db)
    shared   = await _fetch_cfg(_GLOBAL_ID, db)

    has_personal = bool(personal and personal.aws_access_key_id and personal.aws_secret_access_key)
    has_global   = bool(shared   and shared.aws_access_key_id   and shared.aws_secret_access_key)
    has_env      = bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)

    active_sources: list[str] = []
    if has_personal:
        active_sources.append("personal")
    if has_global:
        active_sources.append("global")
    if not active_sources and has_env:
        active_sources.append("env")

    # For backwards compat: primary source is first in list
    primary_source = active_sources[0] if active_sources else None
    if primary_source == "personal":
        region = personal.aws_region  # type: ignore[union-attr]
    elif primary_source == "global":
        region = shared.aws_region  # type: ignore[union-attr]
    elif primary_source == "env":
        region = settings.AWS_REGION
    else:
        region = None

    return {
        "configured": bool(active_sources),
        "source": primary_source,           # kept for backwards compat
        "active_sources": active_sources,   # all active sources
        "region": region,
        "has_personal": has_personal,
        "has_global": has_global,
        "has_env": has_env,
    }


# ── Global (shared) config ────────────────────────────────────────────────────

@router.get("/global-config", response_model=AthenaConfigOut)
async def get_global_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _fetch_cfg(_GLOBAL_ID, db)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No global Athena config saved yet")
    return _row_to_out(cfg)


@router.put("/global-config", response_model=AthenaConfigOut)
async def save_global_config(
    body: AthenaConfigIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    if not body.aws_access_key_id.strip() or not body.aws_secret_access_key.strip():
        raise HTTPException(status_code=400, detail="Access Key ID and Secret are required")
    cfg = await _upsert_cfg(_GLOBAL_ID, body, db)
    return _row_to_out(cfg)


@router.delete("/global-config", status_code=204)
async def delete_global_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    cfg = await _fetch_cfg(_GLOBAL_ID, db)
    if cfg:
        await db.delete(cfg)
        await db.commit()


# ── Personal (per-user) config ────────────────────────────────────────────────

@router.get("/config", response_model=AthenaConfigOut)
async def get_personal_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _fetch_cfg(current_user.id, db)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No personal Athena config saved yet")
    return _row_to_out(cfg)


@router.put("/config", response_model=AthenaConfigOut)
async def save_personal_config(
    body: AthenaConfigIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.aws_access_key_id.strip() or not body.aws_secret_access_key.strip():
        raise HTTPException(status_code=400, detail="Access Key ID and Secret are required")
    cfg = await _upsert_cfg(current_user.id, body, db)
    return _row_to_out(cfg)


@router.delete("/config", status_code=204)
async def delete_personal_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _fetch_cfg(current_user.id, db)
    if cfg:
        await db.delete(cfg)
        await db.commit()


# ── Load Athena tables into DuckDB ────────────────────────────────────────────

_MAX_LOAD_ROWS = 500_000


@router.get("/loaded-tables")
async def list_loaded_tables(current_user: User = Depends(get_current_user)):
    """Return all Athena tables the user has loaded into DuckDB with their metadata."""
    from app.data.duckdb_connector import get_athena_loaded_tables
    return get_athena_loaded_tables(current_user.id)


@router.post("/databases/{database}/tables/{table}/load", status_code=201)
async def load_table_to_duckdb(
    database: str,
    table: str,
    background_tasks: BackgroundTasks,
    source: str = Query(default=""),
    limit: int = Query(default=_MAX_LOAD_ROWS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch an Athena table and store it in DuckDB so the chat agent can query it.

    Applies a row cap (default 500 000). If the table exceeds the cap, the first
    cap rows are loaded and row_limit_applied is set to true in the response.
    Calling this endpoint again on the same table refreshes the data in place.
    """
    from app.api.datasets import _background_enrich
    from app.api.catalog import _sync_table_schema
    from app.agents.schema_agent import refresh_chroma
    from app.data.duckdb_connector import load_athena_table

    creds = await _resolve_creds_by_source(source or None, current_user.id, db)
    actual_limit = min(limit, _MAX_LOAD_ROWS)

    # Fetch one extra row to detect whether the cap was hit
    fetch_sql = f'SELECT * FROM "{database}"."{table}" LIMIT {actual_limit + 1}'
    try:
        rows = await asyncio.to_thread(run_query, fetch_sql, database, creds=creds)
    except Exception as exc:
        raise _handle_athena_error(exc)

    row_limit_applied = len(rows) > actual_limit
    if row_limit_applied:
        rows = rows[:actual_limit]

    if not rows:
        raise HTTPException(status_code=400, detail="Athena table is empty or returned no rows")

    try:
        meta = await asyncio.to_thread(
            load_athena_table, rows, database, table,
            source or "global", current_user.id, row_limit_applied,
        )
    except Exception as exc:
        logger.error("[athena] DuckDB load failed for %s.%s: %s", database, table, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load into DuckDB: {exc}")

    refresh_chroma(current_user.id)

    try:
        await _sync_table_schema(meta["table_name"], current_user.id, db)
    except Exception as exc:
        logger.warning("[athena] Catalog sync failed for %s: %s", meta["table_name"], exc)

    background_tasks.add_task(_background_enrich, meta["table_name"], current_user.id)

    return meta


@router.delete("/databases/{database}/tables/{table}/load", status_code=204)
async def unload_table_from_duckdb(
    database: str,
    table: str,
    current_user: User = Depends(get_current_user),
):
    """Remove an Athena-loaded table from DuckDB."""
    from app.agents.schema_agent import refresh_chroma
    from app.data.duckdb_connector import _athena_duckdb_name, drop_uploaded_table

    duckdb_name = _athena_duckdb_name(database, table, current_user.id)
    try:
        drop_uploaded_table(duckdb_name, current_user.id)
    except (ValueError, PermissionError):
        pass  # already removed — treat as success
    refresh_chroma(current_user.id)


# ── Data endpoints ────────────────────────────────────────────────────────────

@router.get("/databases")
async def get_databases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List databases from ALL active credential sets, each tagged with its source."""
    all_creds = await _resolve_all_creds(current_user.id, db)
    if not all_creds:
        raise _handle_athena_error(AthenaNotConfiguredError(
            "AWS credentials not configured. Enter them on the Athena page or "
            "set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in backend/.env"
        ))

    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for creds in all_creds:
        source = creds["source"]
        try:
            dbs = list_databases(creds=creds)
            for db_item in dbs:
                key = (db_item["name"], source)
                if key not in seen:
                    seen.add(key)
                    merged.append({**db_item, "source": source})
        except Exception as exc:
            logger.warning("[athena] Failed to list databases for source=%s: %s", source, exc)

    return merged


@router.get("/databases/{database}/tables")
async def get_tables(
    database: str,
    source: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    creds = await _resolve_creds_by_source(source or None, current_user.id, db)
    try:
        return list_tables(database, creds=creds)
    except Exception as exc:
        raise _handle_athena_error(exc)


@router.get("/databases/{database}/tables/{table}/schema")
async def get_schema(
    database: str,
    table: str,
    source: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    creds = await _resolve_creds_by_source(source or None, current_user.id, db)
    try:
        return get_table_schema(database, table, creds=creds)
    except Exception as exc:
        raise _handle_athena_error(exc)


@router.get("/databases/{database}/tables/{table}/preview")
async def preview(
    database: str,
    table: str,
    limit: int = 50,
    source: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    creds = await _resolve_creds_by_source(source or None, current_user.id, db)
    try:
        rows = preview_table(database, table, limit=min(limit, 200), creds=creds)
        return {"rows": rows, "row_count": len(rows)}
    except Exception as exc:
        raise _handle_athena_error(exc)


@router.post("/databases/{database}/tables/{table}/direct", status_code=201)
async def register_table_for_direct_query(
    database: str,
    table: str,
    source: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register an Athena table for direct querying (schema-only, no data loaded into DuckDB)."""
    from app.data.duckdb_connector import register_athena_direct
    from app.agents.schema_agent import refresh_chroma

    creds = await _resolve_creds_by_source(source or None, current_user.id, db)
    try:
        schema_info = await asyncio.to_thread(get_table_schema, database, table, creds=creds)
    except Exception as exc:
        raise _handle_athena_error(exc)

    # Convert schema to our format
    columns = [{"column": c["name"], "type": c["type"]} for c in schema_info.get("columns", [])]

    try:
        meta = register_athena_direct(
            database, table, source or "global", current_user.id, columns
        )
    except Exception as exc:
        logger.error("[athena] register_athena_direct failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}")

    refresh_chroma(current_user.id)
    return meta


@router.delete("/databases/{database}/tables/{table}/direct", status_code=204)
async def unregister_table_direct_query(
    database: str,
    table: str,
    current_user: User = Depends(get_current_user),
):
    """Remove an Athena table's direct-query registration."""
    from app.data.duckdb_connector import unregister_athena_direct
    from app.agents.schema_agent import refresh_chroma

    unregister_athena_direct(database, table, current_user.id)
    refresh_chroma(current_user.id)


@router.get("/direct-refs")
async def list_direct_refs(current_user: User = Depends(get_current_user)):
    """Return all Athena tables registered for direct query by this user."""
    from app.data.duckdb_connector import get_athena_direct_refs
    return get_athena_direct_refs(current_user.id)


@router.post("/query")
async def execute_query(
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sql_upper = body.sql.strip().upper()
    for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"):
        if kw in sql_upper.split():
            raise HTTPException(status_code=400, detail=f"Forbidden keyword: {kw}")
    creds = await _resolve_creds_by_source(body.source, current_user.id, db)
    try:
        rows = run_query(body.sql, body.database, creds=creds)
        return {"rows": rows, "row_count": len(rows)}
    except Exception as exc:
        raise _handle_athena_error(exc)
