"""Analysis Agent: executes approved SQL, picks chart type, builds Plotly figure, summarises."""
from __future__ import annotations

import logging
import re

import pandas as pd
import plotly.express as px
from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.core.config import settings
from app.core.llm import get_llm
from app.data.duckdb_connector import execute_query


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN/inf with None so downstream JSON serialization stays spec-compliant."""
    return df.where(pd.notna(df), other=None)


def _get_athena_creds_sync(user_id: str, cred_source: str) -> dict | None:
    """Synchronously fetch Athena credentials from PostgreSQL for direct query execution."""
    try:
        import asyncio
        import concurrent.futures

        async def _fetch():
            from sqlalchemy import select
            from app.core.db import AsyncSessionLocal
            from app.models.athena_config import AthenaConfig
            _GLOBAL_ID = "__global__"
            owner_id = user_id if cred_source == "personal" else _GLOBAL_ID
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AthenaConfig).where(AthenaConfig.user_id == owner_id)
                )
                cfg = result.scalar_one_or_none()
                if cfg:
                    return {
                        "aws_region": cfg.aws_region,
                        "aws_access_key_id": cfg.aws_access_key_id,
                        "aws_secret_access_key": cfg.aws_secret_access_key,
                        "athena_workgroup": cfg.athena_workgroup,
                        "athena_output_bucket": cfg.athena_output_bucket,
                    }
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _fetch())
            return future.result(timeout=5)
    except Exception as exc:
        logger.warning("[analysis] Could not fetch Athena creds: %s", exc)
        return None


def _sanitize_json_str(s: str) -> str:
    """Replace NaN/Infinity literals that Python's json module emits but PostgreSQL rejects."""
    s = re.sub(r'\bNaN\b', 'null', s)
    s = re.sub(r'\b-?Infinity\b', 'null', s)
    return s

logger = logging.getLogger(__name__)


def _fix_sql(sql: str, error: str, schema_context: dict) -> str:
    """Ask the LLM to fix a failed SQL query given the DuckDB error message."""
    schema_lines = []
    for table, info in schema_context.items():
        cols = ", ".join(f"{c['column']} ({c['type']})" for c in info.get("schema", []))
        sample_rows = info.get("sample", [])[:2]
        sample_text = ""
        if sample_rows:
            sample_text = "  Sample: " + "; ".join(
                ", ".join(f"{k}={v!r}" for k, v in row.items()) for row in sample_rows
            )
        schema_lines.append(f"Table {table}: {cols}\n{sample_text}")
    schema_text = "\n".join(schema_lines)

    prompt = (
        "A DuckDB SQL query failed during execution. Fix it so it runs correctly.\n"
        "Return ONLY the corrected SQL — no explanation, no markdown.\n\n"
        f"Failed SQL:\n{sql}\n\n"
        f"DuckDB error:\n{error}\n\n"
        f"Available tables and exact columns:\n{schema_text}\n\n"
    )
    try:
        from app.agents.sql_agent import _extract_sql  # noqa: PLC0415
        raw = get_llm(temperature=0.0).invoke(prompt).content
        fixed = _extract_sql(raw)
        logger.info("[analysis] LLM-fixed SQL: %s", fixed[:120])
        return fixed
    except Exception as exc:
        logger.warning("[analysis] _fix_sql failed: %s", exc)
        return sql


# ── Chart type heuristic ─────────────────────────────────────────────────────

def pick_chart_type(df: pd.DataFrame) -> str:
    """
    Choose the best visualisation type based on column types and result shape.

    Decision rules (in priority order):
      table  — empty result, no numeric columns, single column, >4 columns,
               or single-row aggregate (e.g. COUNT(*)).
      line   — at least one date/time column + at least one numeric column.
      scatter — two or more numeric columns and no categorical columns.
      bar    — everything else (1 categorical + 1 numeric is the common case).
    """
    if df.empty or len(df.columns) < 1:
        return "table"

    cols = list(df.columns)
    dtypes = df.dtypes

    date_cols = [c for c in cols if dtypes[c].kind in ("M",) or
                 any(k in c.lower() for k in ("date", "month", "year", "time", "week"))]
    num_cols  = [c for c in cols if dtypes[c].kind in ("i", "u", "f")]
    cat_cols  = [c for c in cols if dtypes[c].kind in ("O", "S", "U") and c not in date_cols]

    # Table wins when data is not plottable or too wide / too aggregated
    if not num_cols:          return "table"   # all-text result (list of names, etc.)
    if len(cols) == 1:        return "table"   # single-column list
    if len(cols) > 4:         return "table"   # too many dimensions for any chart
    if len(df) == 1:          return "table"   # single-row aggregate (COUNT, SUM, etc.)

    if date_cols and num_cols:
        return "line"
    if len(num_cols) >= 2 and not cat_cols:
        return "scatter"
    return "bar"


def build_plotly_figure(df: pd.DataFrame, chart_type: str) -> str:
    """
    Build a Plotly figure and return it serialised as JSON.

    Supports four types:
      table   — interactive Plotly Table with styled header (uses go.Table).
      line    — time-series line chart (plotly.express).
      scatter — numeric correlation scatter (plotly.express).
      bar     — categorical bar chart, default fallback (plotly.express).
    """
    import plotly.graph_objects as go

    cols = list(df.columns)
    dtypes = df.dtypes

    date_cols = [c for c in cols if dtypes[c].kind in ("M",) or
                 any(k in c.lower() for k in ("date", "month", "year", "time", "week"))]
    num_cols  = [c for c in cols if dtypes[c].kind in ("i", "u", "f")]
    cat_cols  = [c for c in cols if c not in date_cols and c not in num_cols]

    try:
        if chart_type == "table":
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=[f"<b>{c}</b>" for c in df.columns],
                    fill_color="rgba(99,102,241,0.25)",
                    align="left",
                    font=dict(size=12),
                    height=32,
                ),
                cells=dict(
                    values=[df[c].astype(str).tolist() for c in df.columns],
                    align="left",
                    font=dict(size=11),
                    height=28,
                ),
            )])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=10))

        elif chart_type == "line" and date_cols and num_cols:
            fig = px.line(df, x=date_cols[0], y=num_cols[0],
                          color=cat_cols[0] if cat_cols else None)
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))

        elif chart_type == "scatter" and len(num_cols) >= 2:
            fig = px.scatter(df, x=num_cols[0], y=num_cols[1],
                             color=cat_cols[0] if cat_cols else None,
                             hover_name=cat_cols[0] if cat_cols else None)
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))

        else:
            # bar — most general fallback
            x_col = cat_cols[0] if cat_cols else cols[0]
            y_col = num_cols[0] if num_cols else (cols[1] if len(cols) > 1 else cols[0])
            fig = px.bar(df, x=x_col, y=y_col,
                         color=cat_cols[1] if len(cat_cols) > 1 else None)
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))

        return _sanitize_json_str(fig.to_json())
    except Exception as exc:
        logger.warning("[analysis] build_plotly_figure failed (%s); returning empty", exc)
        return ""


def summarize_result(df: pd.DataFrame, question: str) -> str:
    """LLM call: rich, structured analysis of query results in Markdown."""
    num_cols = [c for c in df.columns if df[c].dtype.kind in ("i", "u", "f")]
    cat_cols = [c for c in df.columns if df[c].dtype.kind in ("O", "S", "U")]

    # Build stats block for numeric columns
    stats_lines = []
    for col in num_cols[:4]:
        series = df[col].dropna()
        if len(series):
            stats_lines.append(
                f"  {col}: min={series.min():,.2f}, max={series.max():,.2f}, "
                f"avg={series.mean():,.2f}, total={series.sum():,.2f}"
            )
    stats_text = ("\nNumeric column stats:\n" + "\n".join(stats_lines)) if stats_lines else ""

    # Top/bottom rows for categorical context
    preview_rows = min(30, len(df))
    preview = df.head(preview_rows).to_string(index=False)

    prompt = f"""You are a data analyst interpreting SQL query results. The user asked:
"{question}"

The query returned {len(df)} row(s) across {len(df.columns)} column(s).{stats_text}

Data preview ({preview_rows} of {len(df)} rows):
{preview}

Write a clear, insightful Markdown response that includes:
1. **Key finding** — the single most important thing the data shows (1-2 sentences)
2. **Notable patterns** — trends, comparisons, or rankings worth highlighting (2-4 bullet points)
3. **Highlights** — top value, bottom value, or any outlier if relevant (1-2 bullets)

Rules:
- Be specific: use actual numbers, names, and percentages from the data
- Be concise: no padding, no restating the question
- Use **bold** for key numbers and names
- Do NOT say "the query returned" or "based on the data" — just give the insight directly
- If the data is a simple single value, give a 1-paragraph plain answer instead of the full structure
"""
    try:
        return get_llm(temperature=0.3).invoke(prompt).content.strip()
    except Exception as exc:
        logger.warning("[analysis] summarize_result failed: %s", exc)
        return f"Query returned {len(df)} row(s)."


def explain_empty_result(sql: str, question: str, schema_context: dict) -> str:
    """LLM call: explain why a query returned 0 rows using the SQL and schema samples."""
    sample_lines = []
    for table, info in schema_context.items():
        sample = info.get("sample", [])[:2]
        if sample:
            sample_lines.append(
                f"{table} samples: " + "; ".join(
                    ", ".join(f"{k}={v!r}" for k, v in row.items()) for row in sample
                )
            )
    samples_text = "\n".join(sample_lines) or "(no samples available)"

    prompt = (
        "A SQL query returned 0 rows. Explain concisely WHY it returned no results "
        "and what the user should change. Use the sample data to reason about it "
        "(e.g. date ranges, value formats, spelling). Do NOT say 'try rephrasing'.\n\n"
        f"User question: {question}\n\n"
        f"SQL that ran:\n{sql}\n\n"
        f"Sample data from the table(s):\n{samples_text}"
    )
    try:
        return get_llm(temperature=0.3).invoke(prompt).content.strip()
    except Exception as exc:
        logger.warning("[analysis] explain_empty_result failed: %s", exc)
        return "The query returned no results. The filters may not match the data in the table."


# ── LangGraph node ────────────────────────────────────────────────────────────

def analysis_agent_node(state: AgentState) -> dict:
    """Execute approved SQL, visualise results, summarise."""
    sql = state.get("draft_sql", "")
    if not sql:
        reply = AIMessage(content="No SQL to execute.")
        return {"messages": [reply], "steps_taken": ["analysis_agent"], "current_step": "done", "error": "no_sql"}

    user_question = (
        state.get("cleaned_question")
        or next((m.content for m in reversed(state["messages"]) if m.type == "human"), "")
    )

    schema_context = state.get("schema_context", {})
    query_engine = state.get("query_engine", "duckdb")
    athena_creds_map: dict = state.get("athena_creds") or {}

    def _execute_sql(sql_to_run: str) -> list[dict]:
        """Execute SQL using the appropriate engine based on query_engine state."""
        if query_engine == "athena":
            athena_db, athena_source = None, "global"
            for info in schema_context.values():
                if info.get("athena_direct"):
                    athena_db = info["athena_database"]
                    athena_source = info.get("athena_cred_source", "global")
                    break
            if not athena_db:
                raise ValueError("No Athena direct table found in schema context")
            from app.data.athena_connector import run_query as athena_run_query
            # Use pre-loaded creds from state (avoids asyncio.run()-in-thread on Windows)
            creds = athena_creds_map.get(athena_source) if athena_source != "env" else None
            return athena_run_query(sql_to_run, athena_db, timeout_seconds=120, creds=creds)
        else:
            return execute_query(sql_to_run)

    # Execute (with one automatic self-correction attempt on failure)
    logger.info("[analysis] Executing SQL (engine=%s): %s", query_engine, sql[:120])
    try:
        records = _execute_sql(sql)
    except Exception as first_exc:
        logger.warning("[analysis] SQL failed (%s); attempting auto-fix", first_exc)
        fixed_sql = _fix_sql(sql, str(first_exc), schema_context)
        if fixed_sql != sql:
            try:
                records = _execute_sql(fixed_sql)
                sql = fixed_sql  # use the corrected query going forward
                logger.info("[analysis] Auto-fix succeeded")
            except Exception as second_exc:
                logger.error("[analysis] Auto-fix also failed: %s", second_exc)
                reply = AIMessage(content=f"SQL execution failed: {second_exc}")
                return {
                    "messages": [reply],
                    "query_results": [],
                    "chart_json": "",
                    "steps_taken": ["analysis_agent"], "current_step": "done",
                    "error": str(second_exc),
                }
        else:
            logger.error("[analysis] SQL execution failed (no fix produced): %s", first_exc)
            reply = AIMessage(content=f"SQL execution failed: {first_exc}")
            return {
                "messages": [reply],
                "query_results": [],
                "chart_json": "",
                "steps_taken": ["analysis_agent"], "current_step": "done",
                "error": str(first_exc),
            }

    df = _sanitize_df(pd.DataFrame(records))
    logger.info("[analysis] Query returned %d rows, %d columns", len(df), len(df.columns))

    if df.empty:
        explanation = explain_empty_result(sql, user_question, schema_context)
        reply = AIMessage(content=explanation)
        return {
            "messages": [reply],
            "query_results": [],
            "chart_json": "",
            "steps_taken": ["analysis_agent"], "current_step": "done",
        }

    # Chart
    chart_type = pick_chart_type(df)
    logger.info("[analysis] Chart type: %s", chart_type)
    chart_json = build_plotly_figure(df, chart_type)

    # Summary
    summary = summarize_result(df, user_question)

    reply = AIMessage(content=summary)

    # to_dict can still produce float NaN if dtype is object; convert via df (already sanitized)
    safe_records = df.to_dict(orient="records")

    return {
        "messages": [reply],
        "query_results": safe_records,
        "chart_json": chart_json,
        "steps_taken": ["analysis_agent"], "current_step": "done",
        "error": "",
    }
