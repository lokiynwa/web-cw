"""Moderation status lookup model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ModerationStatus(Base):
    """Defines moderation states such as PENDING, APPROVED, and REJECTED."""

    __tablename__ = "moderation_statuses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    submissions = relationship("UserCostSubmission", back_populates="moderation_status")
    moderation_log_from = relationship(
        "SubmissionModerationLog",
        foreign_keys="SubmissionModerationLog.from_moderation_status_id",
        back_populates="from_status",
    )
    moderation_log_to = relationship(
        "SubmissionModerationLog",
        foreign_keys="SubmissionModerationLog.to_moderation_status_id",
        back_populates="to_status",
    )
