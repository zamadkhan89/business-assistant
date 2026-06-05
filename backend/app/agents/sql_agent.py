"""SQL Agent: generates and validates SQL, then passes it directly to the analysis agent."""
from __future__ import annotations

import logging
import re
import time

import sqlparse
from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agents.state import AgentState
from app.core.llm import get_llm
from app.data.duckdb_connector import dry_run_query

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|UPDATE|TRUNCATE|INSERT|ALTER|GRANT|REVOKE|CREATE|REPLACE|MERGE)\b",
    re.IGNORECASE,
)

_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def validate_sql(sql: str) -> tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Empty SQL"
    match = _FORBIDDEN.search(sql)
    if match:
        return False, f"Forbidden keyword: {match.group()}"
    try:
        parsed = sqlparse.parse(sql.strip())
    except Exception as exc:
        return False, f"Parse error: {exc}"
    if not parsed:
        return False, "Could not parse SQL"
    stmt_type = parsed[0].get_type()
    if stmt_type and stmt_type.upper() not in ("SELECT", "UNKNOWN"):
        return False, f"Only SELECT statements are allowed, got: {stmt_type}"
    return True, ""


def _extract_sql(raw: str) -> str:
    m = _SQL_FENCE.search(raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


def _build_schema_text(schema_context: dict) -> str:
    """Build rich schema description including column metadata and join hints."""
    lines = []
    all_join_hints: list[str] = []

    for table, info in schema_context.items():
        meta = info.get("metadata", {})
        col_meta = meta.get("columns", {})
        table_desc = meta.get("description", "") or meta.get("business_context", "")
        display_name = meta.get("display_name", "") or table

        col_parts = []
        for c in info.get("schema", []):
            col_name = c["column"]
            col_type = c["type"]
            cm = col_meta.get(col_name, {})
            col_str = f"  - {col_name} ({col_type})"
            if cm.get("description"):
                col_str += f": {cm['description']}"
            if cm.get("is_kpi") and cm.get("kpi_definition"):
                col_str += f" [KPI: {cm['kpi_definition']}]"
            sv = cm.get("sample_values", [])
            if sv:
                col_str += f" [e.g. {', '.join(repr(str(v)) for v in sv[:3])}]"
            col_parts.append(col_str)

        athena_direct = info.get("athena_direct", False)
        athena_db = info.get("athena_database", "")
        athena_tbl = info.get("athena_table", "")

        table_header = f"Table `{table}`"
        if display_name != table:
            table_header += f" ({display_name})"
        if table_desc:
            table_header += f": {table_desc}"
        if athena_direct:
            table_header += f" [Athena Direct — reference as \"{athena_db}\".\"{athena_tbl}\" in SQL]"

        sample_rows = info.get("sample", [])[:2]
        sample_text = ""
        if sample_rows:
            sample_text = "\n  Sample: " + "; ".join(
                ", ".join(f"{k}={v!r}" for k, v in row.items()) for row in sample_rows
            )

        lines.append(table_header + "\n" + "\n".join(col_parts) + sample_text)

        for jh in meta.get("join_hints", []):
            desc = jh.get("description", "")
            hint = (
                f"- {jh.get('left_table')}.{jh.get('left_col')} "
                f"-> {jh.get('right_table')}.{jh.get('right_col')}"
            )
            if desc:
                hint += f"  ({desc})"
            all_join_hints.append(hint)

    schema_text = "\n\n".join(lines)
    if all_join_hints:
        schema_text += "\n\nTable relationships (join hints):\n" + "\n".join(all_join_hints)
    return schema_text


def _fix_sql(sql: str, error: str, question: str, schema_text: str) -> str:
    prompt = (
        "A DuckDB SQL query failed. Fix it so it runs correctly.\n"
        "Return ONLY the corrected SQL - no explanation, no markdown.\n\n"
        "Fix guidelines:\n"
        "- Use TRY_CAST instead of CAST so NULL/empty/malformed values return NULL "
        "instead of throwing\n"
        "- Look at the sample values in the schema to understand each column's actual "
        "format and write the correct parsing expression for that format\n"
        "- Use YEAR(CURRENT_DATE) for the current year; never hard-code a year\n\n"
        f"Original question: {question}\n\n"
        f"Failed SQL:\n{sql}\n\n"
        f"DuckDB error:\n{error}\n\n"
        f"Schema:\n{schema_text}"
    )
    try:
        raw = _invoke_llm(prompt, temperature=0.0)
        fixed = _extract_sql(raw)
        logger.info("[sql] LLM-fixed SQL: %s", fixed[:120])
        return fixed or sql
    except Exception as exc:
        logger.warning("[sql] _fix_sql failed: %s", exc)
        return sql


def _invoke_llm(prompt: str, temperature: float = 0.0, retries: int = 2) -> str:
    """Call the LLM with automatic retry on transient connection errors."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            return get_llm(temperature=temperature).invoke(prompt).content
        except Exception as exc:
            msg = str(exc).lower()
            if any(kw in msg for kw in ("connection", "timeout", "network", "retry", "503", "502")):
                last_exc = exc
                if attempt <= retries:
                    wait = attempt * 2
                    logger.warning("[llm] Transient error (attempt %d/%d): %s — retrying in %ds", attempt, retries + 1, exc, wait)
                    time.sleep(wait)
                    continue
            raise
    raise RuntimeError("AI service temporarily unavailable. Please try again.") from last_exc


def generate_sql(
    question: str,
    schema_context: dict,
    glossary_context: list[dict] | None = None,
    conversation_history: list[dict] | None = None,
    query_engine: str = "duckdb",
) -> str:
    if not schema_context:
        raise ValueError("Schema context is empty - cannot generate SQL without table information")

    schema_text = _build_schema_text(schema_context)

    glossary_text = ""
    if glossary_context:
        glossary_text = "\nBusiness glossary (apply these definitions):\n" + "\n".join(
            f"- {g['term']}: {g['definition']}" for g in glossary_context
        ) + "\n"

    history_text = ""
    if conversation_history:
        history_text = "\nConversation context (use this to understand follow-up questions):\n"
        for turn in conversation_history:
            role = "User" if turn["role"] == "human" else "Assistant"
            history_text += f"{role}: {turn['content'][:300]}\n"
        history_text += "\n"

    if query_engine == "athena":
        engine_intro = "You are a SQL expert writing Athena (Presto SQL) SELECT queries.\n"
        engine_rules = (
            "- This is an Athena (Presto SQL) query — NOT DuckDB\n"
            "- Reference tables using their Athena-qualified name shown in brackets above: "
            "\"database\".\"table\"\n"
            "- Do NOT reference any DuckDB or CSV tables — only use the Athena tables shown\n"
            "- Use Presto/Athena SQL syntax (similar to standard SQL; avoid DuckDB-specific functions)\n"
        )
    else:
        engine_intro = "You are a SQL expert writing DuckDB-compatible SELECT queries.\n"
        engine_rules = (
            "- Use TRY_CAST instead of CAST for any type conversion so NULL/empty/malformed "
            "values produce NULL rather than a runtime error\n"
            "- Before writing any expression involving a column, look at the sample values "
            "in the schema to understand the actual stored format (e.g. whether a date column "
            "holds ISO strings, epoch integers, or locale-specific strings) and write the "
            "appropriate parsing expression for that exact format\n"
            "- For year/date filters: inspect the sample data to see what years are present. "
            "If sample rows show only historical years (e.g. 2013-2015), the table contains "
            "historical data — do NOT use YEAR(CURRENT_DATE) or YEAR(CURRENT_DATE)-1 because "
            "that would return 0 rows. Instead use (SELECT MAX(year) FROM table) for 'last year' "
            "or (SELECT MAX(year) FROM table) - 1 for 'the year before', so the query always "
            "targets the most recent year in the actual data.\n"
            "- Use YEAR(CURRENT_DATE) for the current year ONLY when sample rows contain "
            "recent years (within the last 2 years).\n"
        )

    prompt = (
        f"{engine_intro}"
        "Return ONLY the SQL - no explanation, no markdown fences.\n\n"
        "Rules:\n"
        "- Use only the tables and columns listed in the schema below\n"
        "- Always use correct GROUP BY when using aggregates\n"
        "- Use table aliases when joining multiple tables\n"
        "- If the question is a follow-up, use the conversation context to understand "
        "what prior grouping/filter/table is being referenced\n"
        "- Prefer readable, accurate queries over clever ones\n"
        f"{engine_rules}"
        f"\nSchema:\n{schema_text}\n"
        f"{glossary_text}"
        f"{history_text}"
        f"Current question: {question}"
    )

    logger.info("[sql] Generating SQL (engine=%s) for: %s", query_engine, question[:80])
    raw = _invoke_llm(prompt, temperature=0.0)
    sql = _extract_sql(raw)
    logger.info("[sql] Initial SQL: %s", sql[:120])

    if query_engine == "athena":
        # For Athena tables, skip DuckDB dry_run (tables don't exist in DuckDB)
        # Just validate with the keyword/syntax validator
        is_valid, val_error = validate_sql(sql)
        if not is_valid:
            logger.warning("[sql] Athena SQL failed validation: %s", val_error)
            raise ValueError(f"Generated SQL failed validation: {val_error}")
    else:
        for attempt in range(1, 3):
            error = dry_run_query(sql)
            if error is None:
                logger.info("[sql] SQL validated on attempt %d", attempt)
                break
            logger.warning("[sql] DuckDB rejected SQL (attempt %d): %s", attempt, error[:120])
            sql = _fix_sql(sql, error, question, schema_text)
        else:
            error = dry_run_query(sql)
            if error:
                raise ValueError(f"Could not produce valid SQL after 2 attempts: {error}")

    return sql


def explain_sql(sql: str) -> str:
    prompt = (
        "Explain the following SQL query in 1-2 plain English sentences. "
        "Be concise and focus on what business question it answers.\n\nSQL:\n" + sql
    )
    explanation = _invoke_llm(prompt, temperature=0.3).strip()
    logger.info("[sql] Explanation: %s", explanation[:100])
    return explanation


def sql_agent_node(state: AgentState) -> dict:
    user_question = (
        state.get("cleaned_question")
        or next((m.content for m in reversed(state["messages"]) if m.type == "human"), "")
    )
    schema_context = state.get("schema_context", {})
    glossary_context = state.get("glossary_context", [])
    query_engine = state.get("query_engine", "duckdb")

    prior_messages = state["messages"][-7:-1]
    conversation_history = [
        {"role": m.type, "content": m.content}
        for m in prior_messages
    ]

    prior_steps = state.get("steps_taken", [])

    try:
        sql = generate_sql(
            user_question, schema_context, glossary_context, conversation_history, query_engine
        )
    except Exception as exc:
        logger.error("[sql] generate_sql failed: %s", exc)
        reply = AIMessage(content=f"I couldn't generate SQL for that question: {exc}")
        return {
            "messages": [reply],
            "draft_sql": "",
            "sql_explanation": "",
            "steps_taken": prior_steps + ["sql_agent"],
            "current_step": "sql_error",
            "error": str(exc),
        }

    is_valid, error = validate_sql(sql)
    if not is_valid:
        logger.warning("[sql] Validation failed: %s | SQL: %s", error, sql[:120])
        reply = AIMessage(
            content=f"I generated SQL but it failed validation ({error}):\n\n```sql\n{sql}\n```"
        )
        return {
            "messages": [reply],
            "draft_sql": "",
            "sql_explanation": "",
            "steps_taken": prior_steps + ["sql_agent"],
            "current_step": "sql_error",
            "error": error,
        }

    # Generate plain-English explanation for the approval panel
    try:
        explanation = explain_sql(sql)
    except Exception as exc:
        logger.warning("[sql] explain_sql failed: %s", exc)
        explanation = ""

    # ── HITL: pause for user review (only if sql_approval_required is set) ──────
    if not state.get("sql_approval_required", False):
        logger.info("[sql] SQL approval not required — executing immediately")
        return {
            "messages": [],
            "draft_sql": sql,
            "sql_explanation": explanation,
            "steps_taken": prior_steps + ["sql_agent"],
            "current_step": "approved",
            "error": "",
        }

    logger.info("[sql] SQL ready — pausing for HITL approval")
    decision = interrupt({"draft_sql": sql, "sql_explanation": explanation})

    action = decision.get("action", "approve")
    logger.info("[sql] HITL decision: action=%s", action)

    if action == "reject":
        reply = AIMessage(content="Understood — query cancelled. Ask a new question whenever you're ready.")
        return {
            "messages": [reply],
            "draft_sql": "",
            "sql_explanation": "",
            "steps_taken": prior_steps + ["sql_agent"],
            "current_step": "done",
            "error": "rejected",
        }

    if action == "edit":
        edited = decision.get("edited_sql", "").strip()
        is_valid, err = validate_sql(edited)
        if not is_valid:
            reply = AIMessage(content=f"The edited SQL failed validation ({err}). Please try editing again.")
            return {
                "messages": [reply],
                "draft_sql": "",
                "sql_explanation": "",
                "steps_taken": prior_steps + ["sql_agent"],
                "current_step": "sql_error",
                "error": err,
            }
        sql = edited

    # action == "approve" or valid edit — route to analysis_agent
    reply = AIMessage(content=f"Running query:\n\n```sql\n{sql}\n```")
    return {
        "messages": [reply],
        "draft_sql": sql,
        "sql_explanation": explanation,
        "steps_taken": prior_steps + ["sql_agent"],
        "current_step": "approved",
        "error": "",
    }
