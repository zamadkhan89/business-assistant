"""Tests for schema agent and supervisor routing."""
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.schema_agent import search_schema
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node

_TEST_USER = "test-user-00000000"

_FAKE_TABLES = {
    "products": {
        "schema": [
            {"column": "product_id", "type": "INTEGER"},
            {"column": "name", "type": "VARCHAR"},
            {"column": "unit_price", "type": "DOUBLE"},
        ],
        "sample": [{"product_id": 1, "name": "Chai", "unit_price": 18.0}],
    },
    "order_items": {
        "schema": [
            {"column": "order_id", "type": "INTEGER"},
            {"column": "product_id", "type": "INTEGER"},
            {"column": "quantity", "type": "INTEGER"},
            {"column": "unit_price", "type": "DOUBLE"},
        ],
        "sample": [],
    },
}


# --- search_schema ---

@patch("app.agents.schema_agent.describe_user_tables", return_value=_FAKE_TABLES)
def test_search_schema_returns_all_tables(mock_duck):
    result = search_schema("show me revenue by country", user_id=_TEST_USER)
    assert isinstance(result, dict)
    assert len(result) >= 1
    for table_info in result.values():
        assert "schema" in table_info
        assert "sample" in table_info


@patch("app.agents.schema_agent.describe_user_tables", return_value=_FAKE_TABLES)
def test_search_schema_has_expected_tables(mock_duck):
    result = search_schema("customer orders", user_id=_TEST_USER)
    table_names = set(result.keys())
    known = {"products", "order_items"}
    assert table_names & known, f"Expected at least one of {known}, got {table_names}"


@patch("app.agents.schema_agent.describe_user_tables", return_value=_FAKE_TABLES)
def test_search_schema_schema_has_column_and_type(mock_duck):
    result = search_schema("anything", user_id=_TEST_USER)
    for table_info in result.values():
        for col in table_info["schema"]:
            assert "column" in col
            assert "type" in col


# --- supervisor routing ---

def _make_state(content: str) -> AgentState:
    return AgentState(
        messages=[HumanMessage(content=content)],
        current_step="",
        schema_context={},
        draft_sql="",
        sql_explanation="",
        query_results=[],
        chart_json="",
        glossary_context=[],
        user_id=_TEST_USER,
        steps_taken=[],
        cleaned_question="",
        interpretation_note="",
        error="",
    )


def test_supervisor_routes_data_query_to_schema():
    state = _make_state("show total revenue by country")
    result = supervisor_node(state)
    assert result["current_step"] == "schema"
    assert "messages" not in result or result.get("messages") == []


def test_supervisor_handles_greeting():
    state = _make_state("hello there!")
    result = supervisor_node(state)
    assert result["current_step"] == "done"
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)


def test_supervisor_routes_count_query():
    state = _make_state("how many orders do we have?")
    result = supervisor_node(state)
    assert result["current_step"] == "schema"


def test_supervisor_routes_list_query():
    state = _make_state("list top 5 customers by revenue")
    result = supervisor_node(state)
    assert result["current_step"] == "schema"
