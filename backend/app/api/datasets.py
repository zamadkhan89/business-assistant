"""Datasets API: CSV upload, list, and export."""
import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schema_agent import refresh_chroma
from app.agents.sql_agent import validate_sql
from app.api.auth import get_current_user
from app.core.db import AsyncSessionLocal, get_db
from app.data.duckdb_connector import drop_uploaded_table, execute_query, ingest_csv, list_uploaded_tables
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])

_MAX_BYTES = 200 * 1024 * 1024  # 200 MB
_SAFE_TABLE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


async def _background_enrich(table_key: str, user_id: str) -> None:
    """Run AI enrichment for a newly-uploaded table in a background task."""
    try:
        from app.api.catalog import _run_enrichment  # local import avoids circular import at module load
        async with AsyncSessionLocal() as db:
            await _run_enrichment(table_key, user_id, db)
        logger.info("[datasets] Background enrichment complete for %s", table_key)
    except Exception as exc:
        logger.warning("[datasets] Background enrichment failed for %s: %s", table_key, exc)


@router.post("/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    contents = await file.read()
    if len(contents) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 200 MB)")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        meta = ingest_csv(contents, file.filename, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    refresh_chroma(current_user.id)

    # Sync schema to catalog immediately (fast — just DB writes, no LLM)
    try:
        from app.api.catalog import _sync_table_schema
        await _sync_table_schema(meta["table_name"], current_user.id, db)
    except Exception as exc:
        logger.warning("[datasets] Catalog sync failed for %s: %s", meta["table_name"], exc)

    # AI enrichment in background so upload response is instant
    background_tasks.add_task(_background_enrich, meta["table_name"], current_user.id)

    return meta


@router.get("")
async def list_datasets(current_user: User = Depends(get_current_user)):
    """Return all user datasets (CSV uploads + Athena-loaded tables)."""
    return list_uploaded_tables(current_user.id)


@router.delete("/{table_name}")
async def delete_dataset(
    table_name: str,
    current_user: User = Depends(get_current_user),
):
    if not _SAFE_TABLE.match(table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")
    try:
        drop_uploaded_table(table_name, current_user.id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")
    refresh_chroma(current_user.id)
    return {"deleted": table_name}


@router.post("/export")
async def export_csv(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    sql: str = body.get("sql", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="sql is required")

    is_valid, error = validate_sql(sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid SQL: {error}")

    try:
        records = execute_query(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query failed: {exc}")

    if not records:
        raise HTTPException(status_code=404, detail="Query returned no results")

    import io
    import csv

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )
