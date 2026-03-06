"""Reusable business logic for crowd submission creation and moderation."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import ApiKey, CostSubmissionType, ModerationStatus, SubmissionModerationLog, UserCostSubmission
from app.services.submission_protections import (
    build_duplicate_fingerprint,
    find_recent_soft_duplicate,
    run_plausibility_checks,
)


def _get_submission_type(db: Session, submission_type_code: str) -> CostSubmissionType:
    stmt = select(CostSubmissionType).where(
        func.lower(CostSubmissionType.code) == submission_type_code.strip().lower(),
        CostSubmissionType.is_active.is_(True),
    )
    submission_type = db.execute(stmt).scalar_one_or_none()
    if submission_type is None:
        raise HTTPException(status_code=422, detail="Invalid submission_type")
    return submission_type


def _get_pending_status(db: Session) -> ModerationStatus:
    stmt = select(ModerationStatus).where(func.lower(ModerationStatus.code) == "pending")
    pending_status = db.execute(stmt).scalar_one_or_none()
    if pending_status is None:
        raise HTTPException(status_code=500, detail="Moderation status PENDING not configured")
    return pending_status


def _get_moderation_status_by_code(db: Session, code: str) -> ModerationStatus:
    stmt = select(ModerationStatus).where(func.lower(ModerationStatus.code) == code.strip().lower())
    moderation_status = db.execute(stmt).scalar_one_or_none()
    if moderation_status is None:
        raise HTTPException(status_code=422, detail="Invalid moderation_status")
    return moderation_status


def _get_submission_or_404(db: Session, submission_id: int) -> UserCostSubmission:
    stmt: Select = (
        select(UserCostSubmission)
        .where(UserCostSubmission.id == submission_id)
        .options(
            joinedload(UserCostSubmission.submission_type),
            joinedload(UserCostSubmission.moderation_status),
        )
    )
    submission = db.execute(stmt).scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


def create_submission(
    db: Session,
    *,
    contributor_api_key: ApiKey,
    city: str,
    area: str | None,
    submission_type_code: str,
    amount_gbp: Decimal,
    venue_name: str | None = None,
    item_name: str | None = None,
    submission_notes: str | None = None,
) -> UserCostSubmission:
    """Create a PENDING user submission with protection checks."""

    submission_type = _get_submission_type(db, submission_type_code)
    pending_status = _get_pending_status(db)

    plausibility = run_plausibility_checks(submission_type.code, amount_gbp)
    if not plausibility.hard_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Submission amount failed plausibility validation",
                "reasons": plausibility.hard_fail_reasons,
            },
        )

    existing_duplicate = find_recent_soft_duplicate(
        db,
        contributor_api_key_id=contributor_api_key.id,
        city=city,
        area=area,
        submission_type_id=submission_type.id,
        amount_gbp=amount_gbp,
    )
    if existing_duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Possible duplicate submission in recent window",
                "duplicate_submission_id": existing_duplicate.id,
            },
        )

    duplicate_fingerprint = build_duplicate_fingerprint(
        contributor_api_key_id=contributor_api_key.id,
        city=city,
        area=area,
        submission_type_code=submission_type.code,
        amount_gbp=amount_gbp,
    )

    suspicious_reasons = list(plausibility.suspicious_reasons)
    submission = UserCostSubmission(
        submission_type_id=submission_type.id,
        moderation_status_id=pending_status.id,
        submitted_via_api_key_id=contributor_api_key.id,
        city=city,
        area=area,
        venue_name=venue_name,
        item_name=item_name,
        price_gbp=amount_gbp,
        submission_notes=submission_notes,
        is_suspicious=bool(suspicious_reasons),
        suspicious_reasons=suspicious_reasons,
        duplicate_fingerprint=duplicate_fingerprint,
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return _get_submission_or_404(db, submission.id)


def moderate_submission(
    db: Session,
    *,
    submission_id: int,
    moderation_status_code: str,
    moderator_api_key: ApiKey,
    moderator_note: str | None = None,
) -> SubmissionModerationLog:
    """Apply moderation decision and persist moderation audit log entry."""

    submission = _get_submission_or_404(db, submission_id)
    to_status = _get_moderation_status_by_code(db, moderation_status_code)

    from_status_id = submission.moderation_status_id
    submission.moderation_status_id = to_status.id
    submission.is_analytics_eligible = to_status.code.upper() == "APPROVED"

    moderation_log = SubmissionModerationLog(
        submission_id=submission.id,
        from_moderation_status_id=from_status_id,
        to_moderation_status_id=to_status.id,
        moderated_by_api_key_id=moderator_api_key.id,
        moderator_note=moderator_note,
    )

    db.add(submission)
    db.add(moderation_log)
    db.commit()
    db.refresh(moderation_log)

    log_stmt = (
        select(SubmissionModerationLog)
        .where(SubmissionModerationLog.id == moderation_log.id)
        .options(
            joinedload(SubmissionModerationLog.from_status),
            joinedload(SubmissionModerationLog.to_status),
            joinedload(SubmissionModerationLog.moderator_api_key),
        )
    )
    return db.execute(log_stmt).scalar_one()

