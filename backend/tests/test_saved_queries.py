"""Tests for saved-queries CRUD and inline run endpoints."""
import pytest


async def _token(client, email="sq@example.com", password="TestPass123!"):
    r = await client.post("/api/auth/signup", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_list_empty(client):
    token = await _token(client, "sq_list@example.com")
    r = await client.get("/api/saved-queries", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_returns_201(client):
    token = await _token(client, "sq_create@example.com")
    r = await client.post(
        "/api/saved-queries",
        json={
            "name": "Top products",
            "question": "Show top 5 products by revenue",
            "sql": "SELECT product_name, SUM(quantity) as total FROM order_items GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
            "datasets": ["order_items", "products"],
            "results": [{"product_name": "Widget", "total": 100}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Top products"
    assert data["sql"].startswith("SELECT")
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_returns_saved_queries(client):
    token = await _token(client, "sq_listfull@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/saved-queries",
        json={"name": "Q1", "question": "first", "sql": "SELECT 1", "datasets": [], "results": []},
        headers=headers,
    )
    await client.post(
        "/api/saved-queries",
        json={"name": "Q2", "question": "second", "sql": "SELECT 2", "datasets": [], "results": []},
        headers=headers,
    )
    r = await client.get("/api/saved-queries", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_delete_removes_query(client):
    token = await _token(client, "sq_del@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/api/saved-queries",
        json={"name": "Delete me", "question": "q", "sql": "SELECT 1", "datasets": [], "results": []},
        headers=headers,
    )
    qid = create_r.json()["id"]

    r = await client.delete(f"/api/saved-queries/{qid}", headers=headers)
    assert r.status_code == 204

    list_r = await client.get("/api/saved-queries", headers=headers)
    assert all(q["id"] != qid for q in list_r.json())


@pytest.mark.asyncio
async def test_delete_requires_auth(client):
    r = await client.delete("/api/saved-queries/some-id")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_run_requires_auth(client):
    r = await client.post("/api/saved-queries/some-id/run")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_run_not_found(client):
    token = await _token(client, "sq_run404@example.com")
    r = await client.post(
        "/api/saved-queries/nonexistent-id/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_run_rejects_query_with_no_sql(client):
    token = await _token(client, "sq_nosql@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/api/saved-queries",
        json={"name": "No SQL query", "question": "q", "sql": "", "datasets": [], "results": []},
        headers=headers,
    )
    qid = create_r.json()["id"]
    r = await client.post(f"/api/saved-queries/{qid}/run", headers=headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_cross_user_delete_rejected(client):
    token_a = await _token(client, "sq_userA@example.com")
    token_b = await _token(client, "sq_userB@example.com")

    create_r = await client.post(
        "/api/saved-queries",
        json={"name": "UserA query", "question": "q", "sql": "SELECT 1", "datasets": [], "results": []},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    qid = create_r.json()["id"]

    r = await client.delete(
        f"/api/saved-queries/{qid}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    r = await client.get("/api/saved-queries")
    assert r.status_code == 401
