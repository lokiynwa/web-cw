"""Add moderation workflow columns and audit log table."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260304_0005"
down_revision = "20260304_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.add_column(
            sa.Column("is_moderator", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.add_column(
            sa.Column("is_analytics_eligible", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "submission_moderation_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("from_moderation_status_id", sa.Integer(), nullable=True),
        sa.Column("to_moderation_status_id", sa.Integer(), nullable=False),
        sa.Column("moderated_by_api_key_id", sa.Integer(), nullable=True),
        sa.Column("moderator_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["from_moderation_status_id"], ["moderation_statuses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["moderated_by_api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submission_id"], ["user_cost_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_moderation_status_id"], ["moderation_statuses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_submission_moderation_log_submission_id", "submission_moderation_log", ["submission_id"], unique=False
    )
    op.create_index(
        "ix_submission_moderation_log_moderated_by_api_key_id",
        "submission_moderation_log",
        ["moderated_by_api_key_id"],
        unique=False,
    )

    # Backfill eligibility based on existing moderation status values.
    op.execute(
        sa.text(
            """
            UPDATE user_cost_submissions
            SET is_analytics_eligible = CASE
                WHEN moderation_status_id = (
                    SELECT id FROM moderation_statuses WHERE code = 'APPROVED'
                ) THEN TRUE
                ELSE FALSE
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_submission_moderation_log_moderated_by_api_key_id", table_name="submission_moderation_log")
    op.drop_index("ix_submission_moderation_log_submission_id", table_name="submission_moderation_log")
    op.drop_table("submission_moderation_log")

    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.drop_column("is_analytics_eligible")

    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.drop_column("is_moderator")
