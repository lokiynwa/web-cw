"""Moderation audit log for user submissions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SubmissionModerationLog(Base):
    """Records each moderation decision and actor for a submission."""

    __tablename__ = "submission_moderation_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("user_cost_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_moderation_status_id: Mapped[int | None] = mapped_column(
        ForeignKey("moderation_statuses.id", ondelete="RESTRICT"), nullable=True
    )
    to_moderation_status_id: Mapped[int] = mapped_column(
        ForeignKey("moderation_statuses.id", ondelete="RESTRICT"), nullable=False
    )
    moderated_by_api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True
    )
    moderator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    submission = relationship("UserCostSubmission", back_populates="moderation_logs")
    from_status = relationship(
        "ModerationStatus",
        foreign_keys=[from_moderation_status_id],
        back_populates="moderation_log_from",
    )
    to_status = relationship(
        "ModerationStatus",
        foreign_keys=[to_moderation_status_id],
        back_populates="moderation_log_to",
    )
    moderator_api_key = relationship("ApiKey", back_populates="moderation_logs")
