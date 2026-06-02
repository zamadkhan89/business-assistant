import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Additive ALTER TABLE migrations for columns added after initial create_all.
# Safe to run on every startup — IF NOT EXISTS is idempotent.
_MIGRATIONS = [
    "ALTER TABLE saved_queries ADD COLUMN IF NOT EXISTS question VARCHAR",
    "ALTER TABLE saved_queries ADD COLUMN IF NOT EXISTS datasets TEXT",
    "ALTER TABLE saved_queries ADD COLUMN IF NOT EXISTS results TEXT",
    "ALTER TABLE saved_queries ALTER COLUMN sql DROP NOT NULL",
    "ALTER TABLE table_metadata ADD COLUMN IF NOT EXISTS source_type VARCHAR DEFAULT 'csv'",
    "ALTER TABLE table_metadata ADD COLUMN IF NOT EXISTS athena_source VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS storage_quota_mb BIGINT",
    # Backfill 200 MB default for all users that have no quota set yet
    "UPDATE users SET storage_quota_mb = 200 WHERE storage_quota_mb IS NULL",
]


async def create_all_tables() -> None:
    import app.models.audit_log  # noqa: F401
    import app.models.athena_config  # noqa: F401
    import app.models.email_verification  # noqa: F401
    import app.models.glossary  # noqa: F401
    import app.models.message  # noqa: F401
    import app.models.password_reset  # noqa: F401
    import app.models.routine  # noqa: F401
    import app.models.saved_query  # noqa: F401
    import app.models.table_metadata  # noqa: F401
    import app.models.thread  # noqa: F401
    import app.models.user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            try:
                await conn.execute(text(sql))
            except Exception as exc:
                logger.debug("Migration skipped (%s): %s", sql[:60], exc)
