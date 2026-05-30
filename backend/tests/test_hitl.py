"""Tests for the SQL auto-execution flow (HITL approval removed)."""
from unittest.mock import MagicMock, patch

import pytest

_MOCK_SQL = (
    "SELECT p.name, SUM(oi.quantity * oi.unit_price) AS revenue "
    "FROM products p JOIN order_items oi ON p.product_id = oi.product_id "
    "GROUP BY p.name ORDER BY revenue DESC LIMIT 5"
)
_MOCK_SUMMARY = "Chai leads with the highest revenue."

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

_FAKE_QUERY_RESULTS = [
    {"name": "Chai", "revenue": 5000.0},
    {"name": "Chang", "revenue": 3200.0},
    {"name": "Aniseed Syrup", "revenue": 1800.0},
]


def _llm_factory(content: str):
    msg = MagicMock()
    msg.content = content
    llm = MagicMock()
    llm.invoke.return_value = msg
    return llm


def _sql_llm(temperature=0.0):
    return _llm_factory(_MOCK_SQL)


def _analysis_llm(temperature=0.0):
    return _llm_factory(_MOCK_SUMMARY)


async def _signup_and_login(client, email="hitl@test.com"):
    await client.post("/api/auth/signup", json={"email": email, "password": "pass1234"})
    r = await client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    return r.json()["access_token"]


@patch("app.agents.analysis_agent.execute_query", return_value=_FAKE_QUERY_RESULTS)
@patch("app.agents.schema_agent.describe_user_tables", return_value=_FAKE_TABLES)
@patch("app.agents.analysis_agent.get_llm")
@patch("app.agents.sql_agent.get_llm")
async def test_chat_data_question_executes_directly(
    mock_sql_llm, mock_analysis_llm, mock_duck, mock_execute, client
):
    """Data questions go straight to done — no approval step."""
    mock_sql_llm.side_effect = _sql_llm
    mock_analysis_llm.side_effect = _analysis_llm
    token = await _signup_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/chat",
        json={"thread_id": "thread-auto-1", "message": "show top 5 products by revenue"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "done"
    assert data["content"] != ""
    assert data["chart_json"] != ""
    assert len(data["query_results"]) == 3


async def test_resume_requires_auth(client):
    r = await client.post(
        "/api/chat/resume",
        json={"thread_id": "x", "action": "approve"},
    )
    assert r.status_code == 401


async def test_resume_bad_action_returns_400(client):
    await client.post("/api/auth/signup", json={"email": "bad@test.com", "password": "pass1234"})
    r = await client.post("/api/auth/login", json={"email": "bad@test.com", "password": "pass1234"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create the thread first so the 404 check doesn't fire before action validation
    await client.post(
        "/api/chat",
        json={"thread_id": "thread-bad", "message": "hi"},
        headers=headers,
    )

    r = await client.post(
        "/api/chat/resume",
        json={"thread_id": "thread-bad", "action": "INVALID"},
        headers=headers,
    )
    assert r.status_code == 400
