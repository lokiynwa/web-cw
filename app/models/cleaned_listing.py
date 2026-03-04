"""Cleaned listing model for conservative rule-based normalization."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CleanedListing(Base):
    """Stores normalized fields and validation outcomes for a raw listing."""

    __tablename__ = "cleaned_listings"
    __table_args__ = (
        UniqueConstraint("raw_listing_id", "cleaning_version", name="uq_cleaned_listings_raw_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    raw_listing_id: Mapped[int] = mapped_column(
        ForeignKey("raw_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cleaning_version: Mapped[str] = mapped_column(String(30), nullable=False, default="v1")

    price_gbp_weekly: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    deposit_gbp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_ensuite_proxy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    house_size_bucket: Mapped[str | None] = mapped_column(String(30), nullable=True)

    valid_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_deposit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_bedrooms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_bathrooms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_type: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_address: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    import_batch = relationship("ImportBatch", back_populates="cleaned_listings")
    raw_listing = relationship("RawListing", back_populates="cleaned_listing")
