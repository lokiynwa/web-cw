"""Import batch model for immutable raw source ingestion."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ImportBatch(Base):
    """Tracks each CSV import operation and its metadata."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_listings = relationship("RawListing", back_populates="import_batch")
    cleaned_listings = relationship("CleanedListing", back_populates="import_batch")
