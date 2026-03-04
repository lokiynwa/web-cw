"""Add duplicate fingerprint and suspicious-flag fields to submissions."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260304_0006"
down_revision = "20260304_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.add_column(sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(
            sa.Column("suspicious_reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch_op.add_column(sa.Column("duplicate_fingerprint", sa.String(length=64), nullable=True))
        batch_op.create_index(
            "ix_user_cost_submissions_duplicate_fingerprint", ["duplicate_fingerprint"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("user_cost_submissions") as batch_op:
        batch_op.drop_index("ix_user_cost_submissions_duplicate_fingerprint")
        batch_op.drop_column("duplicate_fingerprint")
        batch_op.drop_column("suspicious_reasons")
        batch_op.drop_column("is_suspicious")
