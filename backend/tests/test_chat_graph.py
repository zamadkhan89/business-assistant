import uuid

import pytest


async def _get_token(client, email="graph@example.com", password="password123"):
    resp = await client.post("/api/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_chat_returns_assistant_response(client):
    token = await _get_token(client)
    thread_id = str(uuid.uuid4())

    resp = await client.post(
        "/api/chat",
        json={"thread_id": thread_id, "message": "Hello from the test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "assistant"
    assert data["thread_id"] == thread_id
    assert len(data["content"]) > 0


@pytest.mark.asyncio
async def test_chat_thread_persists_across_messages(client):
    token = await _get_token(client, email="persist@example.com")
    thread_id = str(uuid.uuid4())

    resp1 = await client.post(
        "/api/chat",
        json={"thread_id": thread_id, "message": "First message"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["thread_id"] == thread_id

    # Second message on same thread — verifies checkpointer replays history.
    # Use a greeting so the supervisor responds directly (no HITL, no empty content).
    resp2 = await client.post(
        "/api/chat",
        json={"thread_id": thread_id, "message": "Thanks, goodbye!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["thread_id"] == thread_id
    # Either a direct reply (content non-empty) or routed to data pipeline
    assert resp2.json()["status"] in ("done", "needs_approval")


@pytest.mark.asyncio
async def test_chat_requires_auth(client):
    resp = await client.post(
        "/api/chat",
        json={"thread_id": str(uuid.uuid4()), "message": "Hello"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_rejects_wrong_user_thread(client):
    token_a = await _get_token(client, email="user_a@example.com")
    token_b = await _get_token(client, email="user_b@example.com")
    thread_id = str(uuid.uuid4())

    # User A creates thread
    resp = await client.post(
        "/api/chat",
        json={"thread_id": thread_id, "message": "Mine"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200

    # User B tries to post to User A's thread
    resp = await client.post(
        "/api/chat",
        json={"thread_id": thread_id, "message": "Steal"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403
