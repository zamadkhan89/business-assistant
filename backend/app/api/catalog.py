"""
Catalog API — manage per-table and per-column business metadata.

Metadata stored here is injected into the schema agent context so the LLM
has rich descriptions, KPI definitions, and join hints when generating SQL.
The /enrich endpoint calls the LLM to auto-generate descriptions from column
names and sample values, which the user can then review and edit.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db
from app.core.llm import get_llm
from app.data.duckdb_connector import describe_user_tables
from app.models.table_metadata import ColumnMetadata, TableMetadata
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/catalog", tags=["catalog"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class JoinHint(BaseModel):
    left_table: str
    left_col: str
    right_table: str
    right_col: str
    description: str = ""


class TableMetaUpdate(BaseModel):
    display_name: str = ""
    description: str = ""
    business_context: str = ""
    join_hints: list[JoinHint] = []


class ColumnMetaUpdate(BaseModel):
    display_name: str = ""
    description: str = ""
    is_kpi: bool = False
    kpi_definition: str = ""


class ColumnMetaOut(BaseModel):
    column_name: str
    display_name: str | None
    description: str | None
    data_type: str | None
    sample_values: list[str]
    is_kpi: bool
    kpi_definition: str | None


class TableMetaOut(BaseModel):
    table_key: str
    source_type: str
    display_name: str | None
    description: str | None
    business_context: str | None
    join_hints: list[JoinHint]
    columns: list[ColumnMetaOut]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_create_table_meta(
    table_key: str,
    source_type: str,
    user_id: str,
    db: AsyncSession,
) -> TableMetadata:
    result = await db.execute(
        select(TableMetadata).where(
            TableMetadata.user_id == user_id,
            TableMetadata.table_key == table_key,
        )
    )
    meta = result.scalar_one_or_none()
    if meta is None:
        meta = TableMetadata(user_id=user_id, table_key=table_key, source_type=source_type)
        db.add(meta)
        await db.flush()
    return meta


def _col_to_out(col: ColumnMetadata) -> ColumnMetaOut:
    samples: list[str] = []
    if col.sample_values:
        try:
            samples = json.loads(col.sample_values)
        except Exception:
            pass
    return ColumnMetaOut(
        column_name=col.column_name,
        display_name=col.display_name,
        description=col.description,
        data_type=col.data_type,
        sample_values=samples,
        is_kpi=col.is_kpi,
        kpi_definition=col.kpi_definition,
    )


def _table_to_out(meta: TableMetadata) -> TableMetaOut:
    hints: list[JoinHint] = []
    if meta.join_hints:
        try:
            hints = [JoinHint(**h) for h in json.loads(meta.join_hints)]
        except Exception:
            pass
    return TableMetaOut(
        table_key=meta.table_key,
        source_type=meta.source_type,
        display_name=meta.display_name,
        description=meta.description,
        business_context=meta.business_context,
        join_hints=hints,
        columns=[_col_to_out(c) for c in (meta.columns or [])],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TableMetaOut])
async def list_catalog(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List metadata records for all tables the user has access to."""
    result = await db.execute(
        select(TableMetadata).where(TableMetadata.user_id == current_user.id)
    )
    return [_table_to_out(m) for m in result.scalars()]


@router.get("/{table_key}", response_model=TableMetaOut)
async def get_table_meta(
    table_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TableMetadata).where(
            TableMetadata.user_id == current_user.id,
            TableMetadata.table_key == table_key,
        )
    )
    meta = result.scalar_one_or_none()
    if meta is None:
        raise HTTPException(status_code=404, detail="No metadata found for this table")
    return _table_to_out(meta)


@router.put("/{table_key}", response_model=TableMetaOut)
async def upsert_table_meta(
    table_key: str,
    body: TableMetaUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meta = await _get_or_create_table_meta(table_key, "csv", current_user.id, db)
    meta.display_name = body.display_name or None
    meta.description = body.description or None
    meta.business_context = body.business_context or None
    meta.join_hints = json.dumps([h.model_dump() for h in body.join_hints]) if body.join_hints else None
    await db.commit()
    await db.refresh(meta)
    return _table_to_out(meta)


@router.put("/{table_key}/columns/{column_name}", response_model=ColumnMetaOut)
async def upsert_column_meta(
    table_key: str,
    column_name: str,
    body: ColumnMetaUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    table_meta = await _get_or_create_table_meta(table_key, "csv", current_user.id, db)

    result = await db.execute(
        select(ColumnMetadata).where(
            ColumnMetadata.table_metadata_id == table_meta.id,
            ColumnMetadata.column_name == column_name,
        )
    )
    col = result.scalar_one_or_none()
    if col is None:
        col = ColumnMetadata(
            table_metadata_id=table_meta.id,
            user_id=current_user.id,
            column_name=column_name,
        )
        db.add(col)

    col.display_name = body.display_name or None
    col.description = body.description or None
    col.is_kpi = body.is_kpi
    col.kpi_definition = body.kpi_definition or None
    await db.commit()
    await db.refresh(col)
    return _col_to_out(col)


async def _run_enrichment(table_key: str, user_id: str, db: AsyncSession) -> TableMetadata:
    """
    Core enrichment logic: calls the LLM to generate table description, column descriptions,
    and human-readable display names. Only fills blank fields — never overwrites user edits.
    Returns the updated TableMetadata row.
    """
    user_tables = describe_user_tables(user_id)
    if table_key not in user_tables:
        raise ValueError(f"Table '{table_key}' not found in datasets")

    info = user_tables[table_key]
    schema = info.get("schema", [])
    samples = info.get("sample", [])

    col_sample_map: dict[str, list[str]] = {}
    for c in schema:
        col_name = c["column"]
        vals = list({str(row.get(col_name, "")) for row in samples if row.get(col_name) is not None})[:5]
        if vals:
            col_sample_map[col_name] = vals

    cols_text = ""
    for c in schema:
        col_name = c["column"]
        line = f"  - {col_name} ({c['type']})"
        if col_name in col_sample_map:
            line += f"\n      Sample values: {', '.join(repr(v) for v in col_sample_map[col_name])}"
        cols_text += line + "\n"

    prompt = (
        "You are a data analyst. Given a database table with its columns and per-column sample values, "
        "generate:\n"
        "1. A one-sentence table description (what business entity this table represents)\n"
        "2. For EVERY column: a human-readable display name AND a one-sentence description\n\n"
        f"Table name: {table_key}\n"
        f"Columns (with sample values):\n{cols_text}\n"
        "Respond in JSON only — no markdown fences, no explanation:\n"
        "{\n"
        '  "table_description": "...",\n'
        '  "columns": {\n'
        '    "column_name": {"display_name": "Human Readable Name", "description": "What this column means"},\n'
        '    ...\n'
        "  }\n"
        "}"
    )

    raw = get_llm(temperature=0.3).invoke(prompt).content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    enrichment = json.loads(raw)

    meta = await _get_or_create_table_meta(table_key, "csv", user_id, db)
    if not meta.description:
        meta.description = enrichment.get("table_description", "")

    col_enrichment: dict[str, dict] = enrichment.get("columns", {})
    for col_schema in schema:
        col_name = col_schema["column"]
        col_type = col_schema["type"]
        col_samples = list({str(row.get(col_name, "")) for row in samples if row.get(col_name) is not None})[:5]

        result = await db.execute(
            select(ColumnMetadata).where(
                ColumnMetadata.table_metadata_id == meta.id,
                ColumnMetadata.column_name == col_name,
            )
        )
        col_meta = result.scalar_one_or_none()
        if col_meta is None:
            col_meta = ColumnMetadata(
                table_metadata_id=meta.id,
                user_id=user_id,
                column_name=col_name,
            )
            db.add(col_meta)

        col_meta.data_type = col_type
        col_meta.sample_values = json.dumps(col_samples)
        col_data = col_enrichment.get(col_name, {})
        if not col_meta.description and col_data.get("description"):
            col_meta.description = col_data["description"]
        if not col_meta.display_name and col_data.get("display_name"):
            col_meta.display_name = col_data["display_name"]

    from datetime import datetime
    meta.enriched_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meta)
    return meta


async def _sync_table_schema(table_key: str, user_id: str, db: AsyncSession) -> TableMetadata:
    """Sync column list from live DuckDB schema. Creates catalog entry if missing."""
    user_tables = describe_user_tables(user_id)
    if table_key not in user_tables:
        raise ValueError(f"Table '{table_key}' not found in datasets")

    info = user_tables[table_key]
    schema = info.get("schema", [])
    samples = info.get("sample", [])

    meta = await _get_or_create_table_meta(table_key, "csv", user_id, db)

    for col_schema in schema:
        col_name = col_schema["column"]
        col_type = col_schema["type"]
        col_samples = list({str(row.get(col_name, "")) for row in samples if row.get(col_name) is not None})[:5]

        result = await db.execute(
            select(ColumnMetadata).where(
                ColumnMetadata.table_metadata_id == meta.id,
                ColumnMetadata.column_name == col_name,
            )
        )
        col_meta = result.scalar_one_or_none()
        if col_meta is None:
            col_meta = ColumnMetadata(
                table_metadata_id=meta.id,
                user_id=user_id,
                column_name=col_name,
            )
            db.add(col_meta)
        col_meta.data_type = col_type
        col_meta.sample_values = json.dumps(col_samples)

    await db.commit()
    await db.refresh(meta)
    return meta


@router.post("/{table_key}/enrich", response_model=TableMetaOut)
async def enrich_table_meta(
    table_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Use the LLM to auto-generate table description, column descriptions, and display names.
    Only fills blanks — does not overwrite existing user-entered values.
    """
    try:
        meta = await _run_enrichment(table_key, current_user.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"LLM returned invalid JSON: {exc}")
    except Exception as exc:
        logger.error("[catalog] LLM enrichment failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"LLM enrichment failed: {exc}")
    return _table_to_out(meta)


@router.post("/{table_key}/sync-schema", response_model=TableMetaOut)
async def sync_schema(
    table_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync column list from live DuckDB schema (adds new cols, keeps existing metadata)."""
    try:
        meta = await _sync_table_schema(table_key, current_user.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _table_to_out(meta)
