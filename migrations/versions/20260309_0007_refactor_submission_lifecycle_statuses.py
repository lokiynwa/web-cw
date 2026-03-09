"""Refactor submission lifecycle statuses to ACTIVE/FLAGGED/REMOVED."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260309_0007"
down_revision = "20260304_0006"
branch_labels = None
depends_on = None


def _status_id_by_code(conn: sa.Connection, code: str) -> int | None:
    result = conn.execute(
        sa.text("SELECT id FROM moderation_statuses WHERE lower(code) = lower(:code)"),
        {"code": code},
    ).scalar_one_or_none()
    return int(result) if result is not None else None


def _ensure_status(
    conn: sa.Connection,
    *,
    code: str,
    label: str,
    description: str,
    is_terminal: bool,
) -> int:
    status_id = _status_id_by_code(conn, code)
    if status_id is None:
        conn.execute(
            sa.text(
                """
                INSERT INTO moderation_statuses (code, label, description, is_terminal)
                VALUES (:code, :label, :description, :is_terminal)
                """
            ),
            {
                "code": code,
                "label": label,
                "description": description,
                "is_terminal": is_terminal,
            },
        )
        status_id = _status_id_by_code(conn, code)
    else:
        conn.execute(
            sa.text(
                """
                UPDATE moderation_statuses
                SET label = :label, description = :description, is_terminal = :is_terminal
                WHERE id = :id
                """
            ),
            {
                "id": status_id,
                "label": label,
                "description": description,
                "is_terminal": is_terminal,
            },
        )

    if status_id is None:
        raise RuntimeError(f"Failed to ensure moderation status {code}")
    return status_id


def _remap_submission_statuses(conn: sa.Connection, source_id: int | None, target_id: int) -> None:
    if source_id is None:
        return
    conn.execute(
        sa.text(
            """
            UPDATE user_cost_submissions
            SET moderation_status_id = :target_id
            WHERE moderation_status_id = :source_id
            """
        ),
        {"source_id": source_id, "target_id": target_id},
    )


def _delete_status_if_present(conn: sa.Connection, code: str) -> None:
    conn.execute(
        sa.text("DELETE FROM moderation_statuses WHERE lower(code) = lower(:code)"),
        {"code": code},
    )


def upgrade() -> None:
    conn = op.get_bind()

    active_id = _ensure_status(
        conn,
        code="ACTIVE",
        label="Active",
        description="Published and included in analytics.",
        is_terminal=False,
    )
    flagged_id = _ensure_status(
        conn,
        code="FLAGGED",
        label="Flagged",
        description="Published but flagged for moderator follow-up.",
        is_terminal=False,
    )
    removed_id = _ensure_status(
        conn,
        code="REMOVED",
        label="Removed",
        description="Removed from live analytics.",
        is_terminal=False,
    )

    pending_id = _status_id_by_code(conn, "PENDING")
    approved_id = _status_id_by_code(conn, "APPROVED")
    rejected_id = _status_id_by_code(conn, "REJECTED")

    _remap_submission_statuses(conn, pending_id, active_id)
    _remap_submission_statuses(conn, approved_id, active_id)
    _remap_submission_statuses(conn, rejected_id, removed_id)

    conn.execute(
        sa.text(
            """
            UPDATE user_cost_submissions
            SET is_analytics_eligible = CASE
                WHEN moderation_status_id = :active_id THEN TRUE
                ELSE FALSE
            END
            """
        ),
        {"active_id": active_id},
    )

    _delete_status_if_present(conn, "PENDING")
    _delete_status_if_present(conn, "APPROVED")
    _delete_status_if_present(conn, "REJECTED")

    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.alter_column("is_analytics_eligible", server_default=sa.true())


def downgrade() -> None:
    conn = op.get_bind()

    pending_id = _ensure_status(
        conn,
        code="PENDING",
        label="Pending",
        description="Awaiting moderation decision.",
        is_terminal=False,
    )
    approved_id = _ensure_status(
        conn,
        code="APPROVED",
        label="Approved",
        description="Accepted for downstream analytics.",
        is_terminal=True,
    )
    rejected_id = _ensure_status(
        conn,
        code="REJECTED",
        label="Rejected",
        description="Rejected during moderation.",
        is_terminal=True,
    )

    active_id = _status_id_by_code(conn, "ACTIVE")
    flagged_id = _status_id_by_code(conn, "FLAGGED")
    removed_id = _status_id_by_code(conn, "REMOVED")

    _remap_submission_statuses(conn, active_id, approved_id)
    _remap_submission_statuses(conn, flagged_id, pending_id)
    _remap_submission_statuses(conn, removed_id, rejected_id)

    conn.execute(
        sa.text(
            """
            UPDATE user_cost_submissions
            SET is_analytics_eligible = CASE
                WHEN moderation_status_id = :approved_id THEN TRUE
                ELSE FALSE
            END
            """
        ),
        {"approved_id": approved_id},
    )

    _delete_status_if_present(conn, "ACTIVE")
    _delete_status_if_present(conn, "FLAGGED")
    _delete_status_if_present(conn, "REMOVED")

    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.alter_column("is_analytics_eligible", server_default=sa.false())
