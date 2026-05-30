"""Tests for routines CRUD and run endpoint."""
import pytest


async def _token(client, email="rt@example.com", password="TestPass123!"):
    r = await client.post("/api/auth/signup", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_list_empty(client):
    token = await _token(client, "rt_list@example.com")
    r = await client.get("/api/routines", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_returns_201(client):
    token = await _token(client, "rt_create@example.com")
    r = await client.post(
        "/api/routines",
        json={"name": "Morning Briefing", "questions": ["How many orders today?", "Top 3 products?"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Morning Briefing"
    assert data["questions"] == ["How many orders today?", "Top 3 products?"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_returns_routines(client):
    token = await _token(client, "rt_listfull@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for name in ["Daily", "Weekly", "Monthly"]:
        await client.post(
            "/api/routines",
            json={"name": name, "questions": ["Total revenue?"]},
            headers=headers,
        )
    r = await client.get("/api/routines", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


@pytest.mark.asyncio
async def test_update_routine(client):
    token = await _token(client, "rt_update@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/api/routines",
        json={"name": "Old Name", "questions": ["Q1"]},
        headers=headers,
    )
    rid = create_r.json()["id"]

    r = await client.put(
        f"/api/routines/{rid}",
        json={"name": "New Name", "questions": ["Q1", "Q2"]},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "New Name"
    assert data["questions"] == ["Q1", "Q2"]


@pytest.mark.asyncio
async def test_update_not_found(client):
    token = await _token(client, "rt_upd404@example.com")
    r = await client.put(
        "/api/routines/nonexistent-id",
        json={"name": "X", "questions": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_routine(client):
    token = await _token(client, "rt_del@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/api/routines",
        json={"name": "Delete me", "questions": ["Q"]},
        headers=headers,
    )
    rid = create_r.json()["id"]

    r = await client.delete(f"/api/routines/{rid}", headers=headers)
    assert r.status_code == 204

    list_r = await client.get("/api/routines", headers=headers)
    assert all(rt["id"] != rid for rt in list_r.json())


@pytest.mark.asyncio
async def test_run_requires_auth(client):
    r = await client.post("/api/routines/some-id/run")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_run_not_found(client):
    token = await _token(client, "rt_run404@example.com")
    r = await client.post(
        "/api/routines/nonexistent-id/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_update_rejected(client):
    token_a = await _token(client, "rt_userA@example.com")
    token_b = await _token(client, "rt_userB@example.com")

    create_r = await client.post(
        "/api/routines",
        json={"name": "UserA routine", "questions": ["Q"]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    rid = create_r.json()["id"]

    r = await client.put(
        f"/api/routines/{rid}",
        json={"name": "Hijacked", "questions": []},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_delete_rejected(client):
    token_a = await _token(client, "rt_delA@example.com")
    token_b = await _token(client, "rt_delB@example.com")

    create_r = await client.post(
        "/api/routines",
        json={"name": "UserA routine", "questions": ["Q"]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    rid = create_r.json()["id"]

    r = await client.delete(
        f"/api/routines/{rid}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    r = await client.get("/api/routines")
    assert r.status_code == 401
