import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TableMetadata(Base):
    """Business context and structural metadata for a user's table (CSV or Athena)."""
    __tablename__ = "table_metadata"
    __table_args__ = (
        UniqueConstraint("user_id", "table_key", name="uq_table_metadata_user_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Unique identifier: for CSV = duckdb table name; for Athena = "glue_db.table_name"
    table_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="csv")  # "csv" | "athena"
    athena_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "personal"|"global"|"env"
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: [{"left_table": ..., "left_col": ..., "right_table": ..., "right_col": ..., "description": ...}]
    join_hints: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    columns: Mapped[list["ColumnMetadata"]] = relationship(
        "ColumnMetadata", back_populates="table", cascade="all, delete-orphan",
        lazy="selectin",
    )


class ColumnMetadata(Base):
    """Per-column business descriptions, KPI flags, and sample values."""
    __tablename__ = "column_metadata"
    __table_args__ = (
        UniqueConstraint("table_metadata_id", "column_name", name="uq_col_metadata_table_col"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    table_metadata_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("table_metadata.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # JSON array of up to 5 sample values as strings
    sample_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_kpi: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kpi_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    table: Mapped["TableMetadata"] = relationship("TableMetadata", back_populates="columns")
