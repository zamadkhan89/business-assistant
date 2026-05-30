"""Admin-only endpoints — user management, datasets, threads, storage."""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _user_is_admin, get_current_user
from app.core.db import get_db
from app.data.duckdb_connector import drop_uploaded_table, get_conn, list_uploaded_tables
from app.models.thread import Thread
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


async def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not _user_is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _storage_mb_by_user() -> dict[str, float]:
    """Return estimated storage in MB per user using DuckDB's estimated_size."""
    try:
        with get_conn() as conn:
            # Get all user tables from ownership table
            rows = conn.execute(
                "SELECT table_name, user_id FROM _dataset_ownership"
            ).fetchall()
            usage: dict[str, float] = {}
            for table_name, user_id in rows:
                try:
                    result = conn.execute(
                        "SELECT estimated_size FROM duckdb_tables() WHERE table_name = ?",
                        [table_name],
                    ).fetchone()
                    size_bytes = result[0] if result and result[0] else 0
                except Exception:
                    # Fallback: count rows and estimate 1 KB each
                    try:
                        cnt = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                        size_bytes = cnt * 1024
                    except Exception:
                        size_bytes = 0
                usage[user_id] = usage.get(user_id, 0.0) + size_bytes / (1024 * 1024)
            return {k: round(v, 2) for k, v in usage.items()}
    except Exception:
        return {}


def _dataset_counts_by_user() -> dict[str, int]:
    try:
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _dataset_ownership (
                    table_name        VARCHAR PRIMARY KEY,
                    user_id           VARCHAR NOT NULL,
                    original_filename VARCHAR NOT NULL,
                    uploaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            rows = conn.execute(
                "SELECT user_id, COUNT(*) FROM _dataset_ownership GROUP BY user_id"
            ).fetchall()
            return {r[0]: int(r[1]) for r in rows}
    except Exception:
        return {}


# ── User list ──────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    _admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    users_result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = users_result.scalars().all()

    thread_result = await db.execute(
        select(Thread.user_id, func.count(Thread.id)).group_by(Thread.user_id)
    )
    thread_counts: dict[str, int] = {row[0]: row[1] for row in thread_result.all()}
    dataset_counts = _dataset_counts_by_user()
    storage_mb     = _storage_mb_by_user()

    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "is_verified": u.is_verified,
            "is_admin": _user_is_admin(u),
            "is_blocked": u.is_blocked,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "thread_count": thread_counts.get(u.id, 0),
            "dataset_count": dataset_counts.get(u.id, 0),
            "storage_used_mb": storage_mb.get(u.id, 0.0),
            "storage_quota_mb": u.storage_quota_mb,
        }
        for u in users
    ]


# ── Per-user details ───────────────────────────────────────────────────────────

@router.get("/users/{user_id}/datasets")
async def get_user_datasets(
    user_id: str,
    _admin: User = Depends(_require_admin),
):
    try:
        return list_uploaded_tables(user_id)
    except Exception:
        return []


@router.get("/users/{user_id}/threads")
async def get_user_threads(
    user_id: str,
    _admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread)
        .where(Thread.user_id == user_id)
        .order_by(Thread.updated_at.desc())
        .limit(20)
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in result.scalars().all()
    ]


# ── Block / Unblock ────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/block")
async def block_user(
    user_id: str,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot block your own account")
    user.is_blocked = True
    await db.commit()
    return {"message": f"{user.email} has been blocked"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    _admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_blocked = False
    await db.commit()
    return {"message": f"{user.email} has been unblocked"}


# ── Toggle admin ───────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/toggle-admin")
async def toggle_admin(
    user_id: str,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own admin status")
    user.is_admin = not user.is_admin
    await db.commit()
    return {"is_admin": _user_is_admin(user), "message": f"Admin status updated for {user.email}"}


# ── Storage quota ─────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/quota")
async def set_storage_quota(
    user_id: str,
    quota_mb: int | None = Body(default=None, embed=True),
    _admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set storage quota in MB for a user. Pass null to remove limit."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if quota_mb is not None and quota_mb < 0:
        raise HTTPException(status_code=400, detail="Quota must be positive")
    user.storage_quota_mb = quota_mb
    await db.commit()
    return {"storage_quota_mb": user.storage_quota_mb, "message": "Quota updated"}


# ── Delete dataset ─────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}/datasets/{table_name}")
async def delete_user_dataset(
    user_id: str,
    table_name: str,
    _admin: User = Depends(_require_admin),
):
    try:
        drop_uploaded_table(table_name, user_id)
        return {"message": f"Dataset '{table_name}' deleted"}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not delete dataset: {exc}")


# ── Delete user ────────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Drop all DuckDB tables owned by this user
    try:
        tables = list_uploaded_tables(user_id)
        for tbl in tables:
            try:
                drop_uploaded_table(tbl["table_name"], user_id)
            except Exception:
                pass
    except Exception:
        pass

    # Delete from PostgreSQL — threads/messages cascade via FK
    await db.delete(user)
    await db.commit()
    return {"message": f"User {user.email} and all their data have been deleted"}
