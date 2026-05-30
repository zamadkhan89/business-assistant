"""Tests for CSV upload, list, and export endpoints."""
import io
import pytest

_CSV = b"name,revenue\nAlpha,100\nBeta,200\nGamma,150\n"


async def _auth(client, email="ds@test.com"):
    await client.post("/api/auth/signup", json={"email": email, "password": "pass1234"})
    r = await client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── upload ───────────────────────────────────────────────────────────────────

async def test_upload_csv_returns_metadata(client):
    headers = await _auth(client)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", io.BytesIO(_CSV), "text/csv")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # table name is prefixed with user ID fragment: u{user_prefix}_{filename_stem}
    assert data["table_name"].startswith("u")
    assert data["row_count"] == 3
    assert any(c["column"] == "name" for c in data["columns"])


async def test_upload_rejects_non_csv(client):
    headers = await _auth(client, "ds2@test.com")
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("data.xlsx", io.BytesIO(b"junk"), "application/octet-stream")},
        headers=headers,
    )
    assert r.status_code == 400


async def test_upload_rejects_empty_file(client):
    headers = await _auth(client, "ds3@test.com")
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        headers=headers,
    )
    assert r.status_code == 400


async def test_upload_requires_auth(client):
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", io.BytesIO(_CSV), "text/csv")},
    )
    assert r.status_code == 401


# ── list ─────────────────────────────────────────────────────────────────────

async def test_list_datasets_returns_uploaded_tables(client):
    headers = await _auth(client, "ds4@test.com")
    # Upload first
    await client.post(
        "/api/datasets/upload",
        files={"file": ("mydata.csv", io.BytesIO(_CSV), "text/csv")},
        headers=headers,
    )
    r = await client.get("/api/datasets", headers=headers)
    assert r.status_code == 200
    tables = r.json()
    assert isinstance(tables, list)
    names = [t["table_name"] for t in tables]
    assert any("mydata" in n for n in names)


async def test_list_requires_auth(client):
    r = await client.get("/api/datasets")
    assert r.status_code == 401


# ── export ───────────────────────────────────────────────────────────────────

async def test_export_returns_csv(client):
    headers = await _auth(client, "ds5@test.com")
    # Upload a table
    up = await client.post(
        "/api/datasets/upload",
        files={"file": ("export_test.csv", io.BytesIO(_CSV), "text/csv")},
        headers=headers,
    )
    table = up.json()["table_name"]

    r = await client.post(
        "/api/datasets/export",
        json={"sql": f"SELECT * FROM {table}"},
        headers=headers,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    text = r.text
    assert "name" in text
    assert "Alpha" in text


async def test_export_blocks_drop(client):
    headers = await _auth(client, "ds6@test.com")
    r = await client.post(
        "/api/datasets/export",
        json={"sql": "DROP TABLE customers"},
        headers=headers,
    )
    assert r.status_code == 400


async def test_export_requires_auth(client):
    r = await client.post("/api/datasets/export", json={"sql": "SELECT 1"})
    assert r.status_code == 401
