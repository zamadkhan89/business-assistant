"""Tests for glossary CRUD endpoints."""
import pytest


async def _signup_and_token(client, email="gloss@example.com", password="password123"):
    r = await client.post("/api/auth/signup", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_list_empty(client):
    token = await _signup_and_token(client, "gl_list@example.com")
    r = await client.get("/api/glossary", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_entry(client):
    token = await _signup_and_token(client, "gl_create@example.com")
    r = await client.post(
        "/api/glossary",
        json={"term": "GMV", "definition": "Gross Merchandise Value"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["term"] == "GMV"
    assert data["definition"] == "Gross Merchandise Value"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_empty_term_rejected(client):
    token = await _signup_and_token(client, "gl_empty@example.com")
    r = await client.post(
        "/api/glossary",
        json={"term": "  ", "definition": "something"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_ordered_by_term(client):
    token = await _signup_and_token(client, "gl_order@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for term, defn in [("Revenue", "Total income"), ("ARR", "Annual Recurring Revenue"), ("Churn", "Lost customers")]:
        await client.post("/api/glossary", json={"term": term, "definition": defn}, headers=headers)

    r = await client.get("/api/glossary", headers=headers)
    terms = [e["term"] for e in r.json()]
    assert terms == sorted(terms)


@pytest.mark.asyncio
async def test_update_entry(client):
    token = await _signup_and_token(client, "gl_update@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/api/glossary",
        json={"term": "LTV", "definition": "Lifetime value"},
        headers=headers,
    )
    entry_id = create_r.json()["id"]

    r = await client.put(
        f"/api/glossary/{entry_id}",
        json={"term": "LTV", "definition": "Customer Lifetime Value"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["definition"] == "Customer Lifetime Value"


@pytest.mark.asyncio
async def test_update_not_found(client):
    token = await _signup_and_token(client, "gl_upd404@example.com")
    r = await client.put(
        "/api/glossary/nonexistent-id",
        json={"term": "X", "definition": "Y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_entry(client):
    token = await _signup_and_token(client, "gl_delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/api/glossary",
        json={"term": "CAC", "definition": "Customer Acquisition Cost"},
        headers=headers,
    )
    entry_id = create_r.json()["id"]

    r = await client.delete(f"/api/glossary/{entry_id}", headers=headers)
    assert r.status_code == 204

    list_r = await client.get("/api/glossary", headers=headers)
    ids = [e["id"] for e in list_r.json()]
    assert entry_id not in ids


@pytest.mark.asyncio
async def test_cannot_access_other_users_entry(client):
    token_a = await _signup_and_token(client, "gl_userA@example.com")
    token_b = await _signup_and_token(client, "gl_userB@example.com")

    r = await client.post(
        "/api/glossary",
        json={"term": "Private", "definition": "Mine"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    entry_id = r.json()["id"]

    r2 = await client.delete(
        f"/api/glossary/{entry_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r2.status_code == 403
