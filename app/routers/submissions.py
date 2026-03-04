"""CRUD endpoints for user cost submissions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import CostSubmissionType, ModerationStatus, UserCostSubmission
from app.schemas.submissions import (
    SubmissionCreateRequest,
    SubmissionListResponse,
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
        venue_name=submission.venue_name,
        item_name=submission.item_name,
        submission_notes=submission.submission_notes,
        submitted_at=submission.submitted_at,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
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
def create_submission(payload: SubmissionCreateRequest, db: Session = Depends(get_db)) -> SubmissionResponse:
    submission_type = _get_submission_type(db, payload.submission_type)
    pending_status = _get_pending_status(db)

    submission = UserCostSubmission(
        submission_type_id=submission_type.id,
        moderation_status_id=pending_status.id,
        city=payload.city,
        area=payload.area,
        venue_name=payload.venue_name,
        item_name=payload.item_name,
        price_gbp=payload.amount_gbp,
        submission_notes=payload.submission_notes,
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

    db.add(submission)
    db.commit()
    db.refresh(submission)

    submission = _get_submission_or_404(db, submission.id)
    return _to_response(submission)


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(submission_id: int, db: Session = Depends(get_db)) -> Response:
    submission = _get_submission_or_404(db, submission_id)
    db.delete(submission)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
