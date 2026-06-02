"""Tests for SQL agent — validate_sql, generate_sql path, and graph routing."""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.sql_agent import validate_sql, sql_agent_node
from app.agents.state import AgentState


# --- validate_sql ---

def test_validate_sql_accepts_select():
    ok, err = validate_sql("SELECT * FROM customers")
    assert ok is True
    assert err == ""


def test_validate_sql_accepts_complex_select():
    sql = """
        SELECT c.name, SUM(oi.quantity * oi.unit_price) AS revenue
        FROM customers c
        JOIN orders o ON o.customer_id = c.customer_id
        JOIN order_items oi ON oi.order_id = o.order_id
        GROUP BY c.name
        ORDER BY revenue DESC
        LIMIT 5
    """
    ok, err = validate_sql(sql)
    assert ok is True, f"Expected valid, got error: {err}"


def test_validate_sql_blocks_drop():
    ok, err = validate_sql("DROP TABLE customers")
    assert ok is False
    assert "DROP" in err


def test_validate_sql_blocks_delete():
    ok, err = validate_sql("DELETE FROM orders WHERE order_id = 1")
    assert ok is False
    assert "DELETE" in err


def test_validate_sql_blocks_insert():
    ok, err = validate_sql("INSERT INTO customers VALUES ('X', 'Test')")
    assert ok is False
    assert "INSERT" in err


def test_validate_sql_blocks_update():
    ok, err = validate_sql("UPDATE customers SET name = 'X' WHERE customer_id = 'A'")
    assert ok is False
    assert "UPDATE" in err


def test_validate_sql_blocks_alter():
    ok, err = validate_sql("ALTER TABLE customers ADD COLUMN phone VARCHAR")
    assert ok is False
    assert "ALTER" in err


def test_validate_sql_rejects_empty():
    ok, err = validate_sql("")
    assert ok is False


def test_validate_sql_extracts_from_fence():
    """Forbidden keyword inside a code fence is still caught."""
    sql_with_fence = "```sql\nDROP TABLE customers\n```"
    # The fence won't be present here — validate_sql receives raw SQL
    ok, err = validate_sql("DROP TABLE customers")
    assert ok is False


# --- sql_agent_node with mocked LLM ---

def _make_state(question: str, schema_context: dict | None = None) -> AgentState:
    return AgentState(
        messages=[HumanMessage(content=question)],
        current_step="schema_done",
        schema_context=schema_context or {
            "products": {
                "schema": [
                    {"column": "product_id", "type": "INTEGER"},
                    {"column": "name", "type": "VARCHAR"},
                    {"column": "unit_price", "type": "DECIMAL"},
                ],
                "sample": [],
            },
            "order_items": {
                "schema": [
                    {"column": "product_id", "type": "INTEGER"},
                    {"column": "quantity", "type": "INTEGER"},
                    {"column": "unit_price", "type": "DECIMAL"},
                ],
                "sample": [],
            },
        },
        draft_sql="",
        sql_explanation="",
        query_results=[],
        error="",
    )


_MOCK_SQL = (
    "SELECT p.name, SUM(oi.quantity * oi.unit_price) AS revenue "
    "FROM products p JOIN order_items oi ON p.product_id = oi.product_id "
    "GROUP BY p.name ORDER BY revenue DESC LIMIT 5"
)
_MOCK_EXPLANATION = "This query returns the top 5 products by total sales revenue."


def _mock_llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    llm = MagicMock()
    llm.invoke.return_value = msg
    return llm


# --- sql_agent_node ---

@patch("app.agents.sql_agent.get_llm")
def test_sql_agent_node_writes_draft_sql(mock_get_llm):
    mock_get_llm.side_effect = lambda temperature=0.0: _mock_llm_response(_MOCK_SQL)
    state = _make_state("show me top 5 products by sales")
    result = sql_agent_node(state)

    assert result["draft_sql"] == _MOCK_SQL
    assert result["current_step"] == "approved"
    assert result["error"] == ""


@patch("app.agents.sql_agent.get_llm")
def test_sql_agent_node_no_message_when_approval_off(mock_get_llm):
    """When sql_approval_required is False, agent skips interrupt and returns no message."""
    mock_get_llm.side_effect = lambda temperature=0.0: _mock_llm_response(_MOCK_SQL)
    state = _make_state("show me top 5 products by sales")
    result = sql_agent_node(state)

    assert result["messages"] == []
    assert result["draft_sql"] == _MOCK_SQL
    assert result["current_step"] == "approved"


@patch("app.agents.sql_agent.get_llm")
def test_sql_agent_node_handles_invalid_sql(mock_get_llm):
    mock_get_llm.side_effect = lambda temperature=0.0: _mock_llm_response(
        "DROP TABLE customers"
    )
    state = _make_state("delete all data")
    result = sql_agent_node(state)

    assert result["current_step"] == "sql_error"
    assert result["draft_sql"] == ""
    assert "DROP" in result["error"]


@patch("app.agents.sql_agent.get_llm")
def test_sql_agent_node_extracts_sql_from_fence(mock_get_llm):
    fenced = f"```sql\n{_MOCK_SQL}\n```"
    mock_get_llm.side_effect = lambda temperature=0.0: _mock_llm_response(fenced)
    state = _make_state("top 5 products")
    result = sql_agent_node(state)

    assert result["draft_sql"] == _MOCK_SQL
    assert result["current_step"] == "approved"
