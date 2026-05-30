import pytest


async def _signup_and_token(client, email="chat@example.com", password="password123"):
    resp = await client.post("/api/auth/signup", json={"email": email, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_echo(client):
    token = await _signup_and_token(client)
    response = await client.post(
        "/api/chat/echo",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "hello" in data["content"]


@pytest.mark.asyncio
async def test_echo_requires_auth(client):
    response = await client.post("/api/chat/echo", json={"message": "hello"})
    assert response.status_code == 401
