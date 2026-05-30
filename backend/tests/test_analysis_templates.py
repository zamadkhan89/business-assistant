"""Tests for /api/analysis endpoints."""
import io
import pytest

_NUMERIC_CSV = (
    b"product,revenue,units,cost\n"
    b"Alpha,1000,10,500\n"
    b"Beta,2000,20,800\n"
    b"Gamma,1500,15,600\n"
    b"Delta,3000,30,1200\n"
    b"Epsilon,500,5,200\n"
)

_DATE_CSV = (
    b"date,revenue,units\n"
    b"2024-01-15,1000,10\n"
    b"2024-02-20,2000,20\n"
    b"2024-03-10,1500,15\n"
    b"2024-04-05,3000,30\n"
)


async def _auth(client, email="analysis@test.com"):
    await client.post("/api/auth/signup", json={"email": email, "password": "pass1234"})
    r = await client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _upload(client, headers, csv_bytes=_NUMERIC_CSV, filename="data.csv"):
    r = await client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["table_name"]


# ── list templates ────────────────────────────────────────────────────────────

async def test_list_templates_returns_all(client):
    r = await client.get("/api/analysis/templates")
    assert r.status_code == 200
    templates = r.json()
    ids = [t["id"] for t in templates]
    assert "quick_eda" in ids
    assert "distribution" in ids
    assert "outliers" in ids
    assert "correlation" in ids
    assert "time_trends" in ids


async def test_list_templates_no_auth_required(client):
    r = await client.get("/api/analysis/templates")
    assert r.status_code == 200


# ── quick_eda ─────────────────────────────────────────────────────────────────

async def test_quick_eda_returns_sections(client):
    headers = await _auth(client, "eda1@test.com")
    table = await _upload(client, headers)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "quick_eda"}, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["template"] == "quick_eda"
    assert data["table_name"] == table
    assert len(data["sections"]) >= 2
    types = [s["type"] for s in data["sections"]]
    assert "stats" in types
    assert "table" in types


async def test_quick_eda_stats_contain_row_count(client):
    headers = await _auth(client, "eda2@test.com")
    table = await _upload(client, headers)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "quick_eda"}, headers=headers)
    overview = next(s for s in r.json()["sections"] if s["type"] == "stats")
    assert "Total rows" in overview["stats"]
    assert overview["stats"]["Total rows"] == "5"


# ── distribution ──────────────────────────────────────────────────────────────

async def test_distribution_returns_numeric_stats(client):
    headers = await _auth(client, "dist1@test.com")
    table = await _upload(client, headers)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "distribution"}, headers=headers)
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    assert len(sections) >= 1
    table_section = next((s for s in sections if s["type"] == "table"), None)
    assert table_section is not None
    cols = list(table_section["data"][0].keys())
    assert "Column" in cols


# ── outliers ─────────────────────────────────────────────────────────────────

async def test_outliers_returns_iqr_summary(client):
    headers = await _auth(client, "out1@test.com")
    table = await _upload(client, headers)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "outliers"}, headers=headers)
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    table_section = next((s for s in sections if s["type"] == "table"), None)
    assert table_section is not None
    row = table_section["data"][0]
    assert "Q1" in row
    assert "Q3" in row
    assert "Outliers" in row


# ── correlation ───────────────────────────────────────────────────────────────

async def test_correlation_returns_pairs(client):
    headers = await _auth(client, "corr1@test.com")
    table = await _upload(client, headers)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "correlation"}, headers=headers)
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    table_section = next((s for s in sections if s["type"] == "table"), None)
    assert table_section is not None
    row = table_section["data"][0]
    assert "Column A" in row
    assert "Column B" in row
    assert "Correlation" in row


# ── time_trends ───────────────────────────────────────────────────────────────

async def test_time_trends_uses_date_column(client):
    headers = await _auth(client, "time1@test.com")
    table = await _upload(client, headers, _DATE_CSV, "sales.csv")
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "time_trends"}, headers=headers)
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    assert len(sections) >= 1


async def test_time_trends_no_date_column_returns_text(client):
    headers = await _auth(client, "time2@test.com")
    table = await _upload(client, headers, _NUMERIC_CSV, "nodate.csv")
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "time_trends"}, headers=headers)
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    assert any(s["type"] == "text" for s in sections)


# ── auth and validation ───────────────────────────────────────────────────────

async def test_run_requires_auth(client):
    r = await client.post("/api/analysis/run", json={"table_name": "anything", "template": "quick_eda"})
    assert r.status_code == 401


async def test_run_invalid_template_returns_400(client):
    headers = await _auth(client, "inv1@test.com")
    table = await _upload(client, headers)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "nonexistent"}, headers=headers)
    assert r.status_code == 400


async def test_run_blocks_other_users_table(client):
    h1 = await _auth(client, "owner@test.com")
    h2 = await _auth(client, "thief@test.com")
    table = await _upload(client, h1)
    r = await client.post("/api/analysis/run", json={"table_name": table, "template": "quick_eda"}, headers=h2)
    assert r.status_code == 404
