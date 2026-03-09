"""User-submitted cost observations model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserCostSubmission(Base):
    """Stores crowd-sourced cost submissions with post-publication moderation states."""

    __tablename__ = "user_cost_submissions"
    __table_args__ = (CheckConstraint("price_gbp > 0", name="ck_user_cost_submissions_price_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_type_id: Mapped[int] = mapped_column(
        ForeignKey("cost_submission_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    moderation_status_id: Mapped[int] = mapped_column(
        ForeignKey("moderation_statuses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    submitted_via_api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    city: Mapped[str] = mapped_column(String(120), nullable=False)
    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price_gbp: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    submission_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_analytics_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suspicious_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    duplicate_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    submission_type = relationship("CostSubmissionType", back_populates="submissions")
    moderation_status = relationship("ModerationStatus", back_populates="submissions")
    submitted_via_api_key = relationship("ApiKey", back_populates="submissions")
    created_by_user = relationship("UserAccount", back_populates="submissions")
    moderation_logs = relationship("SubmissionModerationLog", back_populates="submission")
