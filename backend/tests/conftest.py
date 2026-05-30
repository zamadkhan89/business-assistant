import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.graph import build_graph
from app.core.config import settings
from app.core.db import Base, get_db
from app.main import app

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Redirect DuckDB to a temp file so tests never touch business_assistant.db
# (which may be locked by Google Drive or other processes on dev machines).
_tmp_dir = tempfile.mkdtemp(prefix="ba_test_duckdb_")
settings.DUCKDB_PATH = os.path.join(_tmp_dir, "test.db")

# Seed the temp DB with Northwind tables so sql_agent tests can validate SQL.
from app.data.sample_data import load_sample_data  # noqa: E402
load_sample_data()


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.state.graph = build_graph(MemorySaver())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient):
    """Return (client, token) for a freshly created test user."""
    r = await client.post(
        "/api/auth/signup",
        json={"email": "test@example.com", "password": "TestPass123!", "name": "Test User"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    return client, token
