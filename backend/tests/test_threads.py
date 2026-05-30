"""Tests for thread and message history endpoints."""
import uuid

import pytest


async def _signup_and_token(client, email, password="password123"):
    r = await client.post("/api/auth/signup", json={"email": email, "password": password})
    return r.json()["access_token"]


async def _create_thread(client, token, message="Hello"):
    """Send a chat message to create a thread, return thread_id."""
    thread_id = str(uuid.uuid4())
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_result = MagicMock()
    mock_result.get = lambda key, default=None: default
    mock_result.__getitem__ = lambda self, key: (
        [MagicMock(content="Test reply")] if key == "messages" else []
    )

    with patch("app.api.chat.chat") as _:
        pass  # We'll hit the real endpoint but mock graph
    return thread_id


@pytest.mark.asyncio
async def test_list_threads_empty(client):
    token = await _signup_and_token(client, "th_empty@example.com")
    r = await client.get("/api/threads", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_threads_requires_auth(client):
    r = await client.get("/api/threads")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_messages_404_on_missing_thread(client):
    token = await _signup_and_token(client, "th_miss@example.com")
    r = await client.get(
        f"/api/threads/{uuid.uuid4()}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_messages_403_on_other_users_thread(client):
    from app.core.db import get_db
    from app.models.thread import Thread

    token_a = await _signup_and_token(client, "th_ownerA@example.com")
    token_b = await _signup_and_token(client, "th_ownerB@example.com")

    # Create a thread directly via chat (we need graph mock for this)
    from unittest.mock import AsyncMock, MagicMock, patch

    fake_msg = MagicMock()
    fake_msg.content = "Hi"
    mock_result = {"messages": [fake_msg], "chart_json": ""}

    thread_id = str(uuid.uuid4())
    with patch("app.api.chat._get_graph") as mock_get_graph:
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_get_graph.return_value = mock_graph

        await client.post(
            "/api/chat",
            json={"thread_id": thread_id, "message": "Hello"},
            headers={"Authorization": f"Bearer {token_a}"},
        )

    r = await client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_threads_and_messages_flow(client):
    """Creating a chat thread makes it appear in GET /api/threads and its messages loadable."""
    from unittest.mock import AsyncMock, MagicMock, patch

    token = await _signup_and_token(client, "th_flow@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    fake_msg = MagicMock()
    fake_msg.content = "Here is your answer"
    mock_result = {"messages": [fake_msg], "chart_json": ""}

    thread_id = str(uuid.uuid4())
    with patch("app.api.chat._get_graph") as mock_get_graph:
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_get_graph.return_value = mock_graph

        chat_r = await client.post(
            "/api/chat",
            json={"thread_id": thread_id, "message": "Show me total sales"},
            headers=headers,
        )
        assert chat_r.status_code == 200

    threads_r = await client.get("/api/threads", headers=headers)
    assert threads_r.status_code == 200
    thread_ids = [t["id"] for t in threads_r.json()]
    assert thread_id in thread_ids

    msgs_r = await client.get(f"/api/threads/{thread_id}/messages", headers=headers)
    assert msgs_r.status_code == 200
    messages = msgs_r.json()
    assert len(messages) == 2  # user + assistant
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
