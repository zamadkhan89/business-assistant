"""Tests for profile, password change, and forgot/reset password endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_with_name(auth_client):
    client, token = auth_client
    r = await client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Test User"
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_update_profile(auth_client):
    client, token = auth_client
    r = await client.put(
        "/api/auth/profile",
        json={"name": "Updated Name", "email": "test@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_profile_duplicate_email(client: AsyncClient):
    # Create two users
    await client.post("/api/auth/signup", json={"email": "a@test.com", "password": "TestPass123!"})
    r2 = await client.post("/api/auth/signup", json={"email": "b@test.com", "password": "TestPass123!"})
    token2 = r2.json()["access_token"]

    # Try to change b's email to a's email
    r = await client.put(
        "/api/auth/profile",
        json={"name": "", "email": "a@test.com"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r.status_code == 400
    assert "already in use" in r.json()["detail"]


@pytest.mark.asyncio
async def test_change_password(auth_client):
    client, token = auth_client
    r = await client.put(
        "/api/auth/password",
        json={"current_password": "TestPass123!", "new_password": "NewPass456!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    # Can login with new password
    r2 = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "NewPass456!"})
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(auth_client):
    client, token = auth_client
    r = await client.put(
        "/api/auth/password",
        json={"current_password": "WrongPassword!", "new_password": "NewPass456!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_forgot_password_always_200(client: AsyncClient):
    """Returns 200 even for non-existent email (prevents enumeration)."""
    r = await client.post(
        "/api/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert r.status_code == 200
    assert "sent" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_forgot_and_reset_password(client: AsyncClient):
    from sqlalchemy import select

    from app.core.db import get_db
    from app.models.password_reset import PasswordResetToken
    from app.main import app

    # Create user
    await client.post("/api/auth/signup", json={"email": "reset@example.com", "password": "OldPass123!"})

    # Request reset
    r = await client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200

    # Fetch token from DB via override
    db_gen = app.dependency_overrides[get_db]()
    db = await db_gen.__anext__()
    result = await db.execute(select(PasswordResetToken))
    token_row = result.scalars().first()
    assert token_row is not None
    token_str = token_row.token

    # Reset password
    r2 = await client.post(
        "/api/auth/reset-password",
        json={"token": token_str, "new_password": "NewPass789!"},
    )
    assert r2.status_code == 200

    # Can login with new password
    r3 = await client.post("/api/auth/login", json={"email": "reset@example.com", "password": "NewPass789!"})
    assert r3.status_code == 200

    # Token is now used — cannot reset again
    r4 = await client.post(
        "/api/auth/reset-password",
        json={"token": token_str, "new_password": "AnotherPass!"},
    )
    assert r4.status_code == 400


@pytest.mark.asyncio
async def test_reset_invalid_token(client: AsyncClient):
    r = await client.post(
        "/api/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "SomePass123!"},
    )
    assert r.status_code == 400
