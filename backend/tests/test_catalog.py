"""Tests for the Data Catalog API."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_catalog_empty(auth_client):
    client, token = auth_client
    r = await client.get("/api/catalog", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_upsert_and_get_table_meta(auth_client):
    client, token = auth_client
    headers = {"Authorization": f"Bearer {token}"}

    # Create metadata
    r = await client.put(
        "/api/catalog/my_table",
        json={
            "display_name": "My Table",
            "description": "Contains sales data",
            "business_context": "Used by finance team",
            "join_hints": [
                {
                    "left_table": "my_table",
                    "left_col": "customer_id",
                    "right_table": "customers",
                    "right_col": "id",
                    "description": "customer lookup",
                }
            ],
        },
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "My Table"
    assert data["description"] == "Contains sales data"
    assert len(data["join_hints"]) == 1
    assert data["join_hints"][0]["left_col"] == "customer_id"

    # GET should return same
    r2 = await client.get("/api/catalog/my_table", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["description"] == "Contains sales data"

    # Should appear in list
    r3 = await client.get("/api/catalog", headers=headers)
    assert any(m["table_key"] == "my_table" for m in r3.json())


@pytest.mark.asyncio
async def test_upsert_column_meta(auth_client):
    client, token = auth_client
    headers = {"Authorization": f"Bearer {token}"}

    # Ensure table metadata exists first
    r0 = await client.put("/api/catalog/sales", json={"display_name": "Sales"}, headers=headers)
    assert r0.status_code == 200

    r = await client.put(
        "/api/catalog/sales/columns/revenue",
        json={
            "display_name": "Revenue",
            "description": "Total revenue per order",
            "is_kpi": True,
            "kpi_definition": "SUM of unit_price * quantity",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["column_name"] == "revenue"
    assert data["is_kpi"] is True
    assert data["kpi_definition"] == "SUM of unit_price * quantity"


@pytest.mark.asyncio
async def test_get_missing_table_meta_404(auth_client):
    client, token = auth_client
    r = await client.get(
        "/api/catalog/nonexistent_table",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_athena_status_unconfigured(auth_client):
    client, token = auth_client
    r = await client.get("/api/athena/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "configured" in data
    # Expect unconfigured since no AWS env vars in test
    assert data["configured"] is False


@pytest.mark.asyncio
async def test_athena_databases_unconfigured_503(auth_client):
    client, token = auth_client
    r = await client.get("/api/athena/databases", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503
    assert "credentials" in r.json()["detail"].lower()
