"""Saved Questions API — store, list, delete, and re-run user-saved queries."""
import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analysis_agent import build_plotly_figure, pick_chart_type
from app.api.auth import get_current_user
from app.agents.sql_agent import validate_sql
from app.core.db import get_db
from app.data.duckdb_connector import execute_query
from app.models.saved_query import SavedQuery
from app.models.user import User

router = APIRouter(prefix="/saved-queries", tags=["saved-queries"])


class SavedQueryIn(BaseModel):
    name: str
    question: str = ""
    sql: str = ""
    datasets: list[str] = []
    results: list[dict] = []


class SavedQueryOut(BaseModel):
    id: str
    name: str
    question: str
    sql: str
    datasets: list[str]
    results: list[dict]
    created_at: str


def _out(q: SavedQuery) -> SavedQueryOut:
    return SavedQueryOut(
        id=q.id,
        name=q.name,
        question=q.question or "",
        sql=q.sql or "",
        datasets=json.loads(q.datasets or "[]"),
        results=json.loads(q.results or "[]"),
        created_at=q.created_at.isoformat(),
    )


@router.post("", response_model=SavedQueryOut, status_code=201)
async def create_saved_query(
    body: SavedQueryIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = SavedQuery(
        user_id=current_user.id,
        name=body.name,
        question=body.question,
        sql=body.sql,
        datasets=json.dumps(body.datasets),
        results=json.dumps(body.results),
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _out(q)


@router.get("", response_model=list[SavedQueryOut])
async def list_saved_queries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(SavedQuery)
        .where(SavedQuery.user_id == current_user.id)
        .order_by(SavedQuery.created_at.desc())
    )
    return [_out(q) for q in rows.scalars()]


@router.post("/{query_id}/run")
async def run_saved_query(
    query_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-execute the saved SQL and return fresh results + chart."""
    q = await db.get(SavedQuery, query_id)
    if not q or q.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    if not q.sql or not q.sql.strip():
        raise HTTPException(status_code=400, detail="No SQL stored for this query")

    is_valid, err = validate_sql(q.sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid SQL: {err}")

    try:
        records = execute_query(q.sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query failed: {exc}")

    chart_json = ""
    if records:
        df = pd.DataFrame(records)
        if not df.empty:
            chart_json = build_plotly_figure(df, pick_chart_type(df))

    return {"results": records, "chart_json": chart_json, "row_count": len(records)}


@router.delete("/{query_id}", status_code=204)
async def delete_saved_query(
    query_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(SavedQuery, query_id)
    if not q or q.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(q)
    await db.commit()
