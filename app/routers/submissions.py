"""CRUD endpoints for user cost submissions."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import ApiKey, CostSubmissionType, ModerationStatus, SubmissionModerationLog, UserCostSubmission
from app.services.api_key_auth import (
    require_contributor_api_key,
    require_moderator_api_key,
)
from app.services.submission_protections import (
    build_duplicate_fingerprint,
    find_recent_soft_duplicate,
    run_plausibility_checks,
)
from app.schemas.submissions import (
    SubmissionCreateRequest,
    SubmissionListResponse,
    SubmissionModerationLogEntry,
    SubmissionModerationLogResponse,
    SubmissionModerationRequest,
    SubmissionResponse,
    SubmissionUpdateRequest,
)

router = APIRouter()


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


def _to_response(submission: UserCostSubmission) -> SubmissionResponse:
    return SubmissionResponse(
        id=submission.id,
        city=submission.city,
        area=submission.area,
        submission_type=submission.submission_type.code,
        moderation_status=submission.moderation_status.code,
        amount_gbp=submission.price_gbp,
        is_analytics_eligible=submission.is_analytics_eligible,
        is_suspicious=submission.is_suspicious,
        suspicious_reasons=submission.suspicious_reasons,
        duplicate_fingerprint=submission.duplicate_fingerprint,
        venue_name=submission.venue_name,
        item_name=submission.item_name,
        submission_notes=submission.submission_notes,
        submitted_at=submission.submitted_at,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


def _to_moderation_log_entry(log: SubmissionModerationLog) -> SubmissionModerationLogEntry:
    return SubmissionModerationLogEntry(
        id=log.id,
        submission_id=log.submission_id,
        from_moderation_status=log.from_status.code if log.from_status else None,
        to_moderation_status=log.to_status.code,
        moderator_api_key_id=log.moderated_by_api_key_id,
        moderator_key_name=log.moderator_api_key.key_name if log.moderator_api_key else None,
        moderator_note=log.moderator_note,
        created_at=log.created_at,
    )


@router.get("", response_model=SubmissionListResponse)
def list_submissions(db: Session = Depends(get_db)) -> SubmissionListResponse:
    stmt: Select = (
        select(UserCostSubmission)
        .order_by(UserCostSubmission.id.desc())
        .options(
            joinedload(UserCostSubmission.submission_type),
            joinedload(UserCostSubmission.moderation_status),
        )
    )
    rows = db.execute(stmt).scalars().all()
    items = [_to_response(row) for row in rows]
    return SubmissionListResponse(items=items, total=len(items))


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int, db: Session = Depends(get_db)) -> SubmissionResponse:
    submission = _get_submission_or_404(db, submission_id)
    return _to_response(submission)


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreateRequest,
    contributor_api_key: ApiKey = Depends(require_contributor_api_key),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    submission_type = _get_submission_type(db, payload.submission_type)
    pending_status = _get_pending_status(db)

    plausibility = run_plausibility_checks(submission_type.code, payload.amount_gbp)
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
        city=payload.city,
        area=payload.area,
        submission_type_id=submission_type.id,
        amount_gbp=payload.amount_gbp,
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
        city=payload.city,
        area=payload.area,
        submission_type_code=submission_type.code,
        amount_gbp=payload.amount_gbp,
    )

    suspicious_reasons = list(plausibility.suspicious_reasons)

    submission = UserCostSubmission(
        submission_type_id=submission_type.id,
        moderation_status_id=pending_status.id,
        submitted_via_api_key_id=contributor_api_key.id,
        city=payload.city,
        area=payload.area,
        venue_name=payload.venue_name,
        item_name=payload.item_name,
        price_gbp=payload.amount_gbp,
        submission_notes=payload.submission_notes,
        is_suspicious=bool(suspicious_reasons),
        suspicious_reasons=suspicious_reasons,
        duplicate_fingerprint=duplicate_fingerprint,
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    submission = _get_submission_or_404(db, submission.id)
    return _to_response(submission)


@router.put("/{submission_id}", response_model=SubmissionResponse)
def update_submission(
    submission_id: int,
    payload: SubmissionUpdateRequest,
    contributor_api_key: ApiKey = Depends(require_contributor_api_key),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    submission = _get_submission_or_404(db, submission_id)
    pending_status = _get_pending_status(db)

    if submission.moderation_status_id != pending_status.id:
        raise HTTPException(status_code=409, detail="Only pending submissions can be updated")

    if payload.submission_type is not None:
        submission_type = _get_submission_type(db, payload.submission_type)
        submission.submission_type_id = submission_type.id

    if payload.city is not None:
        submission.city = payload.city
    if payload.area is not None:
        submission.area = payload.area
    if payload.amount_gbp is not None:
        submission.price_gbp = payload.amount_gbp
    if payload.venue_name is not None:
        submission.venue_name = payload.venue_name
    if payload.item_name is not None:
        submission.item_name = payload.item_name
    if payload.submission_notes is not None:
        submission.submission_notes = payload.submission_notes

    # Re-evaluate protections on candidate state.
    active_submission_type = submission.submission_type
    if active_submission_type is None:
        active_submission_type = db.execute(
            select(CostSubmissionType).where(CostSubmissionType.id == submission.submission_type_id)
        ).scalar_one()

    amount_for_checks: Decimal = submission.price_gbp
    plausibility = run_plausibility_checks(active_submission_type.code, amount_for_checks)
    if not plausibility.hard_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Submission amount failed plausibility validation",
                "reasons": plausibility.hard_fail_reasons,
            },
        )

    contributor_id = submission.submitted_via_api_key_id
    if contributor_id is None:
        contributor_id = contributor_api_key.id
        submission.submitted_via_api_key_id = contributor_id

    existing_duplicate = find_recent_soft_duplicate(
        db,
        contributor_api_key_id=contributor_id,
        city=submission.city,
        area=submission.area,
        submission_type_id=submission.submission_type_id,
        amount_gbp=amount_for_checks,
        exclude_submission_id=submission.id,
    )
    if existing_duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Possible duplicate submission in recent window",
                "duplicate_submission_id": existing_duplicate.id,
            },
        )

    suspicious_reasons = list(plausibility.suspicious_reasons)

    submission.is_suspicious = bool(suspicious_reasons)
    submission.suspicious_reasons = sorted(set(suspicious_reasons))
    submission.duplicate_fingerprint = build_duplicate_fingerprint(
        contributor_api_key_id=contributor_id,
        city=submission.city,
        area=submission.area,
        submission_type_code=active_submission_type.code,
        amount_gbp=amount_for_checks,
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    submission = _get_submission_or_404(db, submission.id)
    return _to_response(submission)


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(
    submission_id: int,
    _contributor_api_key: ApiKey = Depends(require_contributor_api_key),
    db: Session = Depends(get_db),
) -> Response:
    submission = _get_submission_or_404(db, submission_id)
    db.delete(submission)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{submission_id}/moderation", response_model=SubmissionModerationLogEntry)
def moderate_submission(
    submission_id: int,
    payload: SubmissionModerationRequest,
    _moderator_key: ApiKey = Depends(require_moderator_api_key),
    db: Session = Depends(get_db),
) -> SubmissionModerationLogEntry:
    submission = _get_submission_or_404(db, submission_id)
    to_status = _get_moderation_status_by_code(db, payload.moderation_status)

    from_status_id = submission.moderation_status_id
    submission.moderation_status_id = to_status.id
    submission.is_analytics_eligible = to_status.code.upper() == "APPROVED"

    moderation_log = SubmissionModerationLog(
        submission_id=submission.id,
        from_moderation_status_id=from_status_id,
        to_moderation_status_id=to_status.id,
        moderated_by_api_key_id=_moderator_key.id,
        moderator_note=payload.moderator_note,
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
    hydrated_log = db.execute(log_stmt).scalar_one()
    return _to_moderation_log_entry(hydrated_log)


@router.get("/{submission_id}/moderation", response_model=SubmissionModerationLogResponse)
def get_submission_moderation_log(
    submission_id: int,
    _moderator_key: ApiKey = Depends(require_moderator_api_key),
    db: Session = Depends(get_db),
) -> SubmissionModerationLogResponse:
    _get_submission_or_404(db, submission_id)

    stmt = (
        select(SubmissionModerationLog)
        .where(SubmissionModerationLog.submission_id == submission_id)
        .order_by(SubmissionModerationLog.id.desc())
        .options(
            joinedload(SubmissionModerationLog.from_status),
            joinedload(SubmissionModerationLog.to_status),
            joinedload(SubmissionModerationLog.moderator_api_key),
        )
    )
    logs = db.execute(stmt).scalars().all()

    items = [_to_moderation_log_entry(log) for log in logs]
    return SubmissionModerationLogResponse(submission_id=submission_id, items=items, total=len(items))
