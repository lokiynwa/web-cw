"""Moderation queue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import ApiKey, ModerationStatus, UserCostSubmission
from app.schemas.submissions import SubmissionListResponse, SubmissionResponse
from app.services.api_key_auth import require_moderator_api_key

router = APIRouter()


def _status_by_code_or_422(db: Session, code: str) -> ModerationStatus:
    stmt = select(ModerationStatus).where(func.lower(ModerationStatus.code) == code.strip().lower())
    status_obj = db.execute(stmt).scalar_one_or_none()
    if status_obj is None:
        raise HTTPException(status_code=422, detail="Invalid moderation status filter")
    return status_obj


def _to_submission_response(row: UserCostSubmission) -> SubmissionResponse:
    return SubmissionResponse(
        id=row.id,
        city=row.city,
        area=row.area,
        submission_type=row.submission_type.code,
        moderation_status=row.moderation_status.code,
        amount_gbp=row.price_gbp,
        is_analytics_eligible=row.is_analytics_eligible,
        is_suspicious=row.is_suspicious,
        suspicious_reasons=row.suspicious_reasons,
        duplicate_fingerprint=row.duplicate_fingerprint,
        venue_name=row.venue_name,
        item_name=row.item_name,
        submission_notes=row.submission_notes,
        submitted_at=row.submitted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "/submissions",
    summary="Moderation Queue",
    description="Return submissions filtered by moderation status for moderator workflow screens.",
    response_model=SubmissionListResponse,
    responses={
        401: {"description": "Missing or invalid API key."},
        403: {"description": "Moderator API key required."},
        422: {"description": "Invalid moderation status filter."},
    },
)
def list_submissions_for_moderation(
    moderation_status: str = Query(default="PENDING"),
    _moderator_key: ApiKey = Depends(require_moderator_api_key),
    db: Session = Depends(get_db),
) -> SubmissionListResponse:
    status_obj = _status_by_code_or_422(db, moderation_status)

    stmt: Select = (
        select(UserCostSubmission)
        .where(UserCostSubmission.moderation_status_id == status_obj.id)
        .order_by(UserCostSubmission.submitted_at.asc(), UserCostSubmission.id.asc())
        .options(
            joinedload(UserCostSubmission.submission_type),
            joinedload(UserCostSubmission.moderation_status),
        )
    )
    rows = db.execute(stmt).scalars().all()
    items = [_to_submission_response(row) for row in rows]

    return SubmissionListResponse(items=items, total=len(items))
