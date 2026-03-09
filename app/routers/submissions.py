"""CRUD endpoints for user cost submissions."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import CostSubmissionType, ModerationStatus, SubmissionModerationLog, UserCostSubmission
from app.services.principal_auth import (
    AuthPrincipal,
    require_moderation_principal,
    require_submission_writer_principal,
)
from app.services.submissions_service import (
    create_submission as create_submission_service,
    moderate_submission as moderate_submission_service,
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


def _get_active_status(db: Session) -> ModerationStatus:
    stmt = select(ModerationStatus).where(func.lower(ModerationStatus.code) == "active")
    active_status = db.execute(stmt).scalar_one_or_none()
    if active_status is None:
        raise HTTPException(status_code=500, detail="Moderation status ACTIVE not configured")
    return active_status


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
        created_by_user_id=submission.created_by_user_id,
        submitted_via_api_key_id=submission.submitted_via_api_key_id,
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
        moderator_user_id=log.moderated_by_user_id,
        moderator_display_name=log.moderator_user.display_name if log.moderator_user else None,
        moderator_api_key_id=log.moderated_by_api_key_id,
        moderator_key_name=log.moderator_api_key.key_name if log.moderator_api_key else None,
        moderator_note=log.moderator_note,
        created_at=log.created_at,
    )


def _can_manage_submission(submission: UserCostSubmission, principal: AuthPrincipal) -> bool:
    if principal.is_moderator:
        return True
    if principal.user_id is not None and submission.created_by_user_id == principal.user_id:
        return True
    if principal.api_key_id is not None and submission.submitted_via_api_key_id == principal.api_key_id:
        return True
    return False


@router.get(
    "",
    summary="List Submissions",
    description=(
        "Return crowd submissions (live and reviewed states), newest first. "
        "New submissions are ACTIVE immediately."
    ),
    response_model=SubmissionListResponse,
    responses={200: {"description": "Submission list returned successfully."}},
)
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


@router.get(
    "/{submission_id}",
    summary="Get Submission",
    description="Return a single submission by ID.",
    response_model=SubmissionResponse,
    responses={404: {"description": "Submission not found."}},
)
def get_submission(submission_id: int, db: Session = Depends(get_db)) -> SubmissionResponse:
    submission = _get_submission_or_404(db, submission_id)
    return _to_response(submission)


@router.post(
    "",
    summary="Create Submission",
    description=(
        "Create a new crowd-sourced cost submission. "
        "Primary auth is bearer token from account login; legacy contributor API keys are also supported. "
        "New records are ACTIVE immediately and available in analytics."
    ),
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Submission created."},
        401: {"description": "Missing or invalid authentication credentials."},
        403: {"description": "Authenticated actor is not allowed to submit."},
        409: {"description": "Possible duplicate submission detected."},
        422: {"description": "Validation or plausibility check failed."},
    },
)
def create_submission(
    payload: SubmissionCreateRequest = Body(..., description="Submission payload."),
    principal: AuthPrincipal = Depends(require_submission_writer_principal),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    submission = create_submission_service(
        db,
        contributor_api_key=principal.api_key,
        created_by_user=principal.user,
        city=payload.city,
        area=payload.area,
        submission_type_code=payload.submission_type,
        amount_gbp=payload.amount_gbp,
        venue_name=payload.venue_name,
        item_name=payload.item_name,
        submission_notes=payload.submission_notes,
    )
    return _to_response(submission)


@router.put(
    "/{submission_id}",
    summary="Update Submission",
    description=(
        "Update an existing submission while status is ACTIVE. "
        "Users can update only their own submissions unless moderator."
    ),
    response_model=SubmissionResponse,
    responses={
        401: {"description": "Missing or invalid authentication credentials."},
        403: {"description": "Not allowed to update this submission."},
        404: {"description": "Submission not found."},
        409: {"description": "Submission is not active or duplicate detected."},
        422: {"description": "Validation or plausibility check failed."},
    },
)
def update_submission(
    submission_id: int,
    payload: SubmissionUpdateRequest = Body(..., description="Partial submission update payload."),
    principal: AuthPrincipal = Depends(require_submission_writer_principal),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    submission = _get_submission_or_404(db, submission_id)
    active_status = _get_active_status(db)

    if not _can_manage_submission(submission, principal):
        raise HTTPException(status_code=403, detail="Not allowed to update this submission")

    if submission.moderation_status_id != active_status.id:
        raise HTTPException(status_code=409, detail="Only active submissions can be updated")

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

    actor_user_id = principal.user_id or submission.created_by_user_id
    actor_api_key_id = principal.api_key_id or submission.submitted_via_api_key_id
    if submission.created_by_user_id is None and principal.user_id is not None:
        submission.created_by_user_id = principal.user_id
    if submission.submitted_via_api_key_id is None and principal.api_key_id is not None:
        submission.submitted_via_api_key_id = principal.api_key_id

    existing_duplicate = find_recent_soft_duplicate(
        db,
        contributor_user_id=actor_user_id,
        contributor_api_key_id=actor_api_key_id,
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
        contributor_user_id=actor_user_id,
        contributor_api_key_id=actor_api_key_id,
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


@router.delete(
    "/{submission_id}",
    summary="Delete Submission",
    description=(
        "Delete a submission by ID. Users can delete only their own submissions unless moderator. "
        "Legacy contributor API keys remain supported."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Submission deleted."},
        401: {"description": "Missing or invalid authentication credentials."},
        403: {"description": "Not allowed to delete this submission."},
        404: {"description": "Submission not found."},
    },
)
def delete_submission(
    submission_id: int,
    principal: AuthPrincipal = Depends(require_submission_writer_principal),
    db: Session = Depends(get_db),
) -> Response:
    submission = _get_submission_or_404(db, submission_id)
    if not _can_manage_submission(submission, principal):
        raise HTTPException(status_code=403, detail="Not allowed to delete this submission")
    db.delete(submission)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{submission_id}/moderation",
    summary="Moderate Submission",
    description=(
        "Apply a post-publication moderation decision to a submission. "
        "Supported transitions: ACTIVE->FLAGGED, ACTIVE->REMOVED, FLAGGED->ACTIVE, "
        "FLAGGED->REMOVED, REMOVED->ACTIVE. Requires moderator role or moderator API key."
    ),
    response_model=SubmissionModerationLogEntry,
    responses={
        401: {"description": "Missing or invalid authentication credentials."},
        403: {"description": "Moderator access required."},
        404: {"description": "Submission not found."},
        409: {"description": "Invalid moderation state transition."},
        422: {"description": "Invalid moderation status payload."},
    },
)
def moderate_submission(
    submission_id: int,
    payload: SubmissionModerationRequest = Body(..., description="Moderation decision payload."),
    principal: AuthPrincipal = Depends(require_moderation_principal),
    db: Session = Depends(get_db),
) -> SubmissionModerationLogEntry:
    moderation_log = moderate_submission_service(
        db,
        submission_id=submission_id,
        moderation_status_code=payload.moderation_status,
        moderator_api_key=principal.api_key if principal.api_key is not None and principal.api_key.is_moderator else None,
        moderator_user=principal.user if principal.user is not None and principal.user.role.upper() == "MODERATOR" else None,
        moderator_note=payload.moderator_note,
    )
    return _to_moderation_log_entry(moderation_log)


@router.get(
    "/{submission_id}/moderation",
    summary="Get Submission Moderation History",
    description=(
        "Return moderation decision log entries for a submission. "
        "Requires moderator role or moderator API key."
    ),
    response_model=SubmissionModerationLogResponse,
    responses={
        401: {"description": "Missing or invalid authentication credentials."},
        403: {"description": "Moderator access required."},
        404: {"description": "Submission not found."},
    },
)
def get_submission_moderation_log(
    submission_id: int,
    _principal: AuthPrincipal = Depends(require_moderation_principal),
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
            joinedload(SubmissionModerationLog.moderator_user),
        )
    )
    logs = db.execute(stmt).scalars().all()

    items = [_to_moderation_log_entry(log) for log in logs]
    return SubmissionModerationLogResponse(submission_id=submission_id, items=items, total=len(items))
