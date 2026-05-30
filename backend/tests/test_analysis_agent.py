"""Tests for the Analysis Agent."""
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from langchain_core.messages import HumanMessage

from app.agents.analysis_agent import (
    analysis_agent_node,
    build_plotly_figure,
    pick_chart_type,
    summarize_result,
)
from app.agents.state import AgentState


# ── pick_chart_type ──────────────────────────────────────────────────────────

def test_pick_chart_type_bar_for_categorical_numeric():
    df = pd.DataFrame({"name": ["A", "B", "C"], "revenue": [100, 200, 300]})
    assert pick_chart_type(df) == "bar"


def test_pick_chart_type_line_for_date_column():
    df = pd.DataFrame({"order_date": pd.to_datetime(["2024-01", "2024-02"]), "total": [10, 20]})
    assert pick_chart_type(df) == "line"


def test_pick_chart_type_line_for_date_keyword_in_column_name():
    df = pd.DataFrame({"month": ["Jan", "Feb"], "sales": [10, 20]})
    assert pick_chart_type(df) == "line"


def test_pick_chart_type_scatter_for_two_numerics():
    df = pd.DataFrame({"price": [1.0, 2.0], "quantity": [10, 20]})
    assert pick_chart_type(df) == "scatter"


def test_pick_chart_type_returns_table_for_empty():
    assert pick_chart_type(pd.DataFrame()) == "table"


def test_pick_chart_type_returns_table_for_no_numerics():
    df = pd.DataFrame({"name": ["Alice", "Bob"], "city": ["NY", "LA"]})
    assert pick_chart_type(df) == "table"


def test_pick_chart_type_returns_table_for_single_row():
    df = pd.DataFrame({"total_revenue": [12345.67]})
    assert pick_chart_type(df) == "table"


def test_pick_chart_type_returns_table_for_too_many_columns():
    df = pd.DataFrame({str(i): [1, 2] for i in range(6)})
    assert pick_chart_type(df) == "table"


# ── build_plotly_figure ──────────────────────────────────────────────────────

def test_build_plotly_figure_table_returns_valid_json():
    df = pd.DataFrame({"name": ["Alice", "Bob"], "city": ["NY", "LA"]})
    fig_json = build_plotly_figure(df, "table")
    assert fig_json != ""
    parsed = json.loads(fig_json)
    assert "data" in parsed
    assert parsed["data"][0]["type"] == "table"


def test_build_plotly_figure_bar_returns_valid_json():
    df = pd.DataFrame({"name": ["A", "B"], "revenue": [100, 200]})
    fig_json = build_plotly_figure(df, "bar")
    assert fig_json != ""
    parsed = json.loads(fig_json)
    assert "data" in parsed


def test_build_plotly_figure_line_returns_valid_json():
    df = pd.DataFrame({"month": ["Jan", "Feb"], "sales": [10, 20]})
    fig_json = build_plotly_figure(df, "line")
    assert fig_json != ""
    assert "data" in json.loads(fig_json)


def test_build_plotly_figure_scatter_returns_valid_json():
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    fig_json = build_plotly_figure(df, "scatter")
    assert fig_json != ""
    assert "data" in json.loads(fig_json)


# ── analysis_agent_node ──────────────────────────────────────────────────────

def _make_state(sql: str = "SELECT name, unit_price FROM products LIMIT 3") -> AgentState:
    return AgentState(
        messages=[HumanMessage(content="show top products by price")],
        current_step="approved",
        schema_context={},
        draft_sql=sql,
        sql_explanation="",
        query_results=[],
        chart_json="",
        error="",
    )


@patch("app.agents.analysis_agent.get_llm")
@patch("app.agents.analysis_agent.execute_query")
def test_analysis_node_returns_chart_json(mock_execute, mock_get_llm):
    mock_execute.return_value = [
        {"name": "Chai", "unit_price": 18.0},
        {"name": "Chang", "unit_price": 19.0},
        {"name": "Aniseed Syrup", "unit_price": 10.0},
    ]
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Top product by price is Chang.")
    mock_get_llm.return_value = llm

    result = analysis_agent_node(_make_state())

    assert result["chart_json"] != ""
    assert "data" in json.loads(result["chart_json"])


@patch("app.agents.analysis_agent.get_llm")
@patch("app.agents.analysis_agent.execute_query")
def test_analysis_node_stores_query_results(mock_execute, mock_get_llm):
    records = [{"name": "Chai", "unit_price": 18.0}]
    mock_execute.return_value = records
    mock_get_llm.return_value = MagicMock(invoke=MagicMock(
        return_value=MagicMock(content="One product found.")
    ))

    result = analysis_agent_node(_make_state())
    assert result["query_results"] == records


@patch("app.agents.analysis_agent.execute_query")
def test_analysis_node_handles_empty_result(mock_execute):
    mock_execute.return_value = []
    result = analysis_agent_node(_make_state())
    assert result["chart_json"] == ""
    assert result["query_results"] == []
    assert result["current_step"] == "done"
    assert result["messages"][-1].content  # LLM explains why; just check non-empty


@patch("app.agents.analysis_agent.execute_query")
def test_analysis_node_handles_sql_error(mock_execute):
    mock_execute.side_effect = Exception("column not found")
    result = analysis_agent_node(_make_state())
    assert result["current_step"] == "done"
    assert "column not found" in result["error"]


def test_analysis_node_handles_missing_sql():
    state = _make_state(sql="")
    result = analysis_agent_node(state)
    assert result["error"] == "no_sql"
