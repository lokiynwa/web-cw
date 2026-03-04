"""Raw listing model preserving CSV source rows exactly as imported."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RawListing(Base):
    """Immutable raw listing row tied to an import batch."""

    __tablename__ = "raw_listings"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "source_row_number", name="uq_raw_listings_batch_row"),
        CheckConstraint("source_row_number > 0", name="ck_raw_listings_source_row_number_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_row_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_row_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    import_batch = relationship("ImportBatch", back_populates="raw_listings")
