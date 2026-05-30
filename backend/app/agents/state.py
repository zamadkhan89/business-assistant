"""
Shared state TypedDict for the LangGraph pipeline.

AgentState is the single source of truth that flows through every node.
LangGraph serialises it to the checkpointer after each node so that
an interrupt() in sql_agent_node can be resumed later — even after a
server restart (when AsyncPostgresSaver is used in production).

Reducer rules
-------------
- messages     : add_messages — new messages are appended, never replaced.
                 This is why conversation history is preserved across turns.
- steps_taken  : _extend — each node appends its name; the list is never reset
                 within a single graph run (useful for debugging and audit).
- All other fields are last-write-wins (standard TypedDict behaviour).
"""
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def _extend(current: list | None, update: list | None) -> list:
    """Reducer that concatenates lists rather than replacing them."""
    return (current or []) + (update or [])


class AgentState(TypedDict):
    """
    Shared state object passed between all LangGraph nodes.

    Fields
    ------
    messages          : Full conversation history (human + AI turns). The
                        add_messages reducer ensures turns accumulate correctly
                        across interrupts and multi-turn conversations.
    current_step      : Routing signal written by each node so the conditional
                        edge functions know where to send control next.
                        Values: "schema" | "schema_done" | "approved" |
                                "sql_error" | "done"
    schema_context    : Relevant table schemas returned by schema_agent.
                        Dict of {table_name: {schema: [...], sample: [...]}}.
    draft_sql         : SQL generated (and validated) by sql_agent, awaiting
                        or having received HITL approval.
    sql_explanation   : Plain-English explanation of draft_sql shown to the user
                        in the approval panel.
    query_results     : Rows returned by DuckDB after approved SQL is executed,
                        stored as a list of dicts for JSON serialisation.
    chart_json        : Plotly figure serialised to JSON by analysis_agent.
                        Empty string if the query produced no chart.
    glossary_context  : Business term definitions loaded from PostgreSQL before
                        each graph run. [{term, definition}, …]
    user_id           : UUID of the authenticated user; scopes DuckDB table
                        access so users only see their own uploaded datasets.
    steps_taken       : Ordered list of node names visited this turn (audit trail).
    cleaned_question  : Typo-corrected / expanded version of the user's question
                        produced by the supervisor's LLM classification step.
    interpretation_note: Non-empty when the supervisor corrected an ambiguous or
                         misspelled query; displayed in the chat UI as a note.
    error             : Last error message, if any node failed. Empty on success.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    current_step: str
    schema_context: dict
    draft_sql: str
    sql_explanation: str
    query_results: list[dict]
    chart_json: str
    glossary_context: list[dict]   # [{term, definition}, …] loaded per-request
    user_id: str                   # scopes DuckDB access to this user's tables
    steps_taken: Annotated[list[str], _extend]  # agent nodes visited this turn
    cleaned_question: str          # typo-corrected / clarified version of the user question
    interpretation_note: str       # shown in UI when supervisor corrects the query
    error: str
    selected_datasets: list[str]   # empty = all user datasets; non-empty = restrict to these
    query_engine: str              # "duckdb" (default) or "athena" (when Athena direct refs are in use)
    athena_creds: dict             # {"personal": {...}, "global": {...}} pre-loaded from DB
    preloaded_metadata: dict       # {table_key: metadata_dict} pre-loaded from DB
