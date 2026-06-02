import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AthenaConfig(Base):
    __tablename__ = "athena_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # No FK constraint by design: user_id is either a real UUID or the sentinel
    # string "__global__" for shared admin credentials. A FK would reject "__global__".
    user_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    aws_region: Mapped[str] = mapped_column(String, default="us-east-1")
    aws_access_key_id: Mapped[str] = mapped_column(String, nullable=False)
    aws_secret_access_key: Mapped[str] = mapped_column(String, nullable=False)
    athena_workgroup: Mapped[str] = mapped_column(String, default="primary")
    athena_output_bucket: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
