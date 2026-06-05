from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.user import User


class AthenaConfig(Base):
    __tablename__ = "athena_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # user_id is NULL for the global shared config (is_global=True); proper FK for per-user configs
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    aws_region: Mapped[str] = mapped_column(String, default="us-east-1")
    aws_access_key_id: Mapped[str] = mapped_column(String, nullable=False)
    aws_secret_access_key: Mapped[str] = mapped_column(String, nullable=False)
    athena_workgroup: Mapped[str] = mapped_column(String, default="primary")
    athena_output_bucket: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])
