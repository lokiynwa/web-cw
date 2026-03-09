"""Add user ownership and moderator-user audit linkage for submissions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260309_0009"
down_revision = "20260309_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_user_cost_submissions_created_by_user_id", ["created_by_user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_user_cost_submissions_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("submission_moderation_log") as batch_op:
        batch_op.add_column(sa.Column("moderated_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_submission_moderation_log_moderated_by_user_id", ["moderated_by_user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_submission_moderation_log_moderated_by_user_id_users",
            "users",
            ["moderated_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("submission_moderation_log") as batch_op:
        batch_op.drop_constraint("fk_submission_moderation_log_moderated_by_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_submission_moderation_log_moderated_by_user_id")
        batch_op.drop_column("moderated_by_user_id")

    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.drop_constraint("fk_user_cost_submissions_created_by_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_user_cost_submissions_created_by_user_id")
        batch_op.drop_column("created_by_user_id")
