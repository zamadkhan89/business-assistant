"""Admin-only endpoints — user management, datasets, threads, storage."""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _user_is_admin, get_current_user
from app.core.db import get_db
from app.data.duckdb_connector import drop_uploaded_table, get_conn, list_uploaded_tables
from app.models.audit_log import AdminAuditLog
from app.models.glossary import GlossaryEntry
from app.models.message import Message
from app.models.saved_query import SavedQuery
from app.models.thread import Thread
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


async def _audit(
    db: AsyncSession,
    admin: User,
    action: str,
    target: User | None = None,
    detail: str = "",
) -> None:
    db.add(AdminAuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action=action,
        target_user_id=target.id if target else None,
        target_email=target.email if target else None,
        detail=detail or None,
    ))


async def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not _user_is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _storage_mb_by_user() -> dict[str, float]:
    """Return estimated storage in MB per user using a single DuckDB join."""
    try:
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT o.user_id, COALESCE(SUM(t.estimated_size), 0) AS total_bytes
                FROM _dataset_ownership o
                LEFT JOIN duckdb_tables() t ON t.table_name = o.table_name
                GROUP BY o.user_id
            """).fetchall()
            return {row[0]: round(row[1] / (1024 * 1024), 2) for row in rows}
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
            "streaming_enabled": u.streaming_enabled,
            "sql_approval_required": u.sql_approval_required,
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
    await _audit(db, admin, "block", user)
    await db.commit()
    return {"message": f"{user.email} has been blocked"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_blocked = False
    await _audit(db, admin, "unblock", user)
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
    action = "grant_admin" if user.is_admin else "revoke_admin"
    await _audit(db, admin, action, user)
    await db.commit()
    return {"is_admin": _user_is_admin(user), "message": f"Admin status updated for {user.email}"}


# ── Storage quota ─────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/quota")
async def set_storage_quota(
    user_id: str,
    quota_mb: int | None = Body(default=None, embed=True),
    admin: User = Depends(_require_admin),
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
    detail = f"quota set to {quota_mb} MB" if quota_mb is not None else "quota removed (unlimited)"
    await _audit(db, admin, "set_quota", user, detail)
    await db.commit()
    return {"storage_quota_mb": user.storage_quota_mb, "message": "Quota updated"}


# ── Per-user feature settings ─────────────────────────────────────────────────

@router.patch("/users/{user_id}/settings")
async def update_user_settings(
    user_id: str,
    streaming_enabled: bool | None = Body(default=None, embed=True),
    sql_approval_required: bool | None = Body(default=None, embed=True),
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle streaming and/or SQL approval per user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = []
    if streaming_enabled is not None:
        user.streaming_enabled = streaming_enabled
        changes.append(f"streaming={'on' if streaming_enabled else 'off'}")
    if sql_approval_required is not None:
        user.sql_approval_required = sql_approval_required
        changes.append(f"sql_approval={'on' if sql_approval_required else 'off'}")

    if changes:
        await _audit(db, admin, "update_settings", user, "; ".join(changes))
        await db.commit()

    return {
        "streaming_enabled": user.streaming_enabled,
        "sql_approval_required": user.sql_approval_required,
    }


# ── Delete dataset ─────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}/datasets/{table_name}")
async def delete_user_dataset(
    user_id: str,
    table_name: str,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        drop_uploaded_table(table_name, user_id)
        target_result = await db.execute(select(User).where(User.id == user_id))
        target = target_result.scalar_one_or_none()
        await _audit(db, admin, "delete_dataset", target, f"table: {table_name}")
        await db.commit()
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

    deleted_email = user.email

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

    # Delete in FK dependency order: messages → threads → glossary/saved_queries → user
    thread_ids_result = await db.execute(select(Thread.id).where(Thread.user_id == user_id))
    thread_ids = [row[0] for row in thread_ids_result.all()]
    if thread_ids:
        await db.execute(delete(Message).where(Message.thread_id.in_(thread_ids)))
    await db.execute(delete(Thread).where(Thread.user_id == user_id))
    await db.execute(delete(GlossaryEntry).where(GlossaryEntry.user_id == user_id))
    await db.execute(delete(SavedQuery).where(SavedQuery.user_id == user_id))

    # Audit before deleting the user row so we still have their email
    db.add(AdminAuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action="delete_user",
        target_user_id=user_id,
        target_email=deleted_email,
    ))

    await db.delete(user)
    await db.commit()
    return {"message": f"User {deleted_email} and all their data have been deleted"}


# ── Audit log ──────────────────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    _admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(200)
    )
    return [
        {
            "id": r.id,
            "admin_email": r.admin_email,
            "action": r.action,
            "target_email": r.target_email,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.scalars()
    ]
