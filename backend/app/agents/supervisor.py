"""Supervisor: pure intent router — classifies the message and sets current_step.

The supervisor owns NO business logic and fetches NO data.
Downstream agents (schema, sql, analysis) are responsible for their own domains.

current_step values this node can produce:
  "schema"       — a data query that requires SQL → schema_agent → sql_agent → analysis_agent
  "schema_only"  — user wants to know what data is available → schema_agent returns listing, stops
  "done"         — off_topic reply sent directly; no further agents run
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """\
You are the intent router for a business analytics assistant.

Respond with ONLY a JSON object — no explanation, no markdown:

{{
  "intent": "data_query" | "data_listing" | "show_context" | "off_topic",
  "cleaned_question": "...",
  "reply": "..."
}}

=== INTENT RULES ===

- "data_query" — User wants to QUERY or ANALYSE data (needs SQL to answer).
  Includes: metrics, aggregations, filters, comparisons, charts, trends, top-N,
  time-series, exploratory analysis on specific tables.

  TYPO / ABBREVIATION FIXING:
  • Fix all typos: "yea"→"year", "lst yr"→"last year", "revnue"→"revenue"
  • Expand shorthand: "q1"→"Q1 (January–March)", "ytd"→"year to date"

  FOLLOW-UP DETECTION (apply broadly — when in doubt, it is a follow-up):
  • Any message that is SHORT (1-4 words), uses pronouns ("those", "them", "it",
    "that", "their"), or implies continuation ("now show", "also", "break it down
    by", "compare", "filter by", "same but", "sort by", "group by", "by X") is a
    follow-up when there is prior conversation history showing a data query.
  • Phrases like "by sales", "by revenue", "per category", "top 5", "last year",
    "sort desc" standing alone are ALWAYS follow-ups — NEVER off_topic.
  • Look at the previous SQL in the conversation history (if present) to identify
    the actual column names, table, and filters already in use. Incorporate those
    into the self-contained cleaned_question so the SQL agent has full context.
  • cleaned_question must stand alone: e.g. "by sales" after a top-model query →
    "Show top 10 car models ranked by total sellingprice from u69353333_car_prices
    where saledate year is within the last 10 years".

  DISPUTE / VERIFICATION (when user challenges or doubts a result):
  • Triggers on: "i think it's X", "i thought it was X", "but X should be higher",
    "are you sure", "that doesn't seem right", "i believe it's X", "what about X".
  • CRITICAL RULE: Re-run the EXACT SAME query structure from history — same table,
    same GROUP BY column, same metric. Do NOT add WHERE filters for the disputed value.
  • Look at the previous SQL to identify the exact column used (e.g. `seller` vs `make`).
    Use THAT column in the cleaned_question. Never switch columns silently.
  • cleaned_question example: prior SQL grouped by `seller`; user says "i think it's Toyota" →
    "Show ALL sellers from u69353333_car_prices ranked by total sellingprice DESC using
    GROUP BY seller with no make filter — to show the complete ranking and verify the top seller"
  • If you significantly changed the question, set reply to:
      "I interpreted your question as: *<cleaned_question>*"
    Otherwise leave reply empty.

  ERROR CORRECTION:
  • "this is wrong", "fix the error", "try again" → always "data_query" using
    prior query as context.

  SELECTED DATASETS RULE (overrides everything except off_topic):
  • If SELECTED DATASETS are listed below, ANY data-related question is "data_query".
  • Expand vague queries ("EDA", "explore", "summarize") into concrete questions
    referencing the selected dataset.

- "data_listing" — User wants to know WHAT DATA IS AVAILABLE (no SQL needed).
  Triggers on: "what tables/datasets do you have?", "what can I query?",
               "which datasets are available?", "what data do you have?",
               "show me your tables", "list your datasets".
  • Leave cleaned_question and reply empty — the schema agent handles this.

- "show_context" — User is asking about the PREVIOUS query execution or why the
  assistant gave a specific answer. Triggers on: "which SQL did you run?",
  "show me the query", "what SQL was that?", "what query did you use?",
  "show me the code", "what did you execute?",
  "why did you say X", "why are you changing your answer", "why that result",
  "you said X before", "explain your answer", "why did you show X".
  • Leave cleaned_question and reply empty — the system will return the last SQL from state.

- "off_topic" — Clearly NOT about data (pure greetings, unrelated topics).
  • Set reply to a polite one-line redirect. Leave cleaned_question empty.
  • NOTE: questions about available data or previous queries are NOT off_topic.

=== CONVERSATION HISTORY (last few turns) ===
{history}

{selected_datasets_section}
=== LATEST USER MESSAGE ===
{message}
"""


def supervisor_node(state: AgentState) -> dict:
    last_message = state["messages"][-1].content

    prior = state["messages"][-8:-1]
    history_lines = []
    for m in prior:
        if m.type == "human":
            history_lines.append(f"User: {m.content[:300]}")
        else:
            content = m.content
            # Keep SQL blocks intact so the LLM sees real column names
            if "```sql" in content:
                history_lines.append(f"Assistant [SQL]: {content[:600]}")
            else:
                first_sentence = content.split(".")[0][:200]
                history_lines.append(f"Assistant: {first_sentence}")
    history = "\n".join(history_lines) or "(none)"

    selected = state.get("selected_datasets") or []
    if selected:
        selected_datasets_section = (
            "=== SELECTED DATASETS ===\n"
            f"{', '.join(selected)}\n"
            "The user has pre-selected these datasets. Route ALL data-related questions "
            "(including vague ones like EDA, explore, summarize) as 'data_query'. "
            "Never use 'data_listing' or 'off_topic' for data-related messages.\n\n"
        )
    else:
        selected_datasets_section = ""

    prompt = _CLASSIFY_PROMPT.format(
        history=history,
        message=last_message,
        selected_datasets_section=selected_datasets_section,
    )

    try:
        raw = get_llm(temperature=0.0).invoke(prompt).content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("[supervisor] Classification failed (%s); defaulting to data_query", exc)
        data = {"intent": "data_query", "cleaned_question": last_message, "reply": ""}

    intent = data.get("intent", "data_query")
    cleaned = (data.get("cleaned_question") or "").strip()
    reply_text = (data.get("reply") or "").strip()

    logger.info("[supervisor] intent=%s cleaned=%r", intent, (cleaned or last_message)[:100])

    if intent == "data_query":
        return {
            "current_step": "schema",
            "cleaned_question": cleaned or last_message,
            "interpretation_note": reply_text,
            "steps_taken": ["supervisor"],
        }

    if intent == "data_listing":
        return {
            "current_step": "schema_only",
            "cleaned_question": last_message,
            "interpretation_note": "",
            "steps_taken": ["supervisor"],
        }

    if intent == "show_context":
        sql = state.get("draft_sql", "").strip()
        if sql:
            content = f"Here is the SQL I ran for the previous query:\n\n```sql\n{sql}\n```"
        else:
            content = "I don't have a previous query in this conversation yet."
        return {
            "messages": [AIMessage(content=content)],
            "current_step": "done",
            "cleaned_question": "",
            "interpretation_note": "",
            "steps_taken": ["supervisor"],
            "chart_json": "",
            "error": "",
        }

    # off_topic
    reply = AIMessage(content=reply_text or "I can help with questions about your business data.")
    return {
        "messages": [reply],
        "current_step": "done",
        "cleaned_question": "",
        "interpretation_note": "",
        "steps_taken": ["supervisor"],
        "chart_json": "",
        "error": "",
    }
