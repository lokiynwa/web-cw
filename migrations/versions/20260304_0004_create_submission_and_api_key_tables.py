"""Create submission lookup, user submissions, and API key tables."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260304_0004"
down_revision = "20260304_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_submission_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_cost_submission_types_code"),
    )

    op.create_table(
        "moderation_statuses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_moderation_statuses_code"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key_name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_hash"),
        sa.UniqueConstraint("key_name", name="uq_api_keys_name"),
    )

    op.create_table(
        "user_cost_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_type_id", sa.Integer(), nullable=False),
        sa.Column("moderation_status_id", sa.Integer(), nullable=False),
        sa.Column("submitted_via_api_key_id", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("area", sa.String(length=120), nullable=True),
        sa.Column("venue_name", sa.String(length=200), nullable=True),
        sa.Column("item_name", sa.String(length=200), nullable=True),
        sa.Column("price_gbp", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("submission_notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price_gbp > 0", name="ck_user_cost_submissions_price_positive"),
        sa.ForeignKeyConstraint(["submission_type_id"], ["cost_submission_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["moderation_status_id"], ["moderation_statuses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_via_api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_user_cost_submissions_submission_type_id",
        "user_cost_submissions",
        ["submission_type_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_cost_submissions_moderation_status_id",
        "user_cost_submissions",
        ["moderation_status_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_cost_submissions_submitted_via_api_key_id",
        "user_cost_submissions",
        ["submitted_via_api_key_id"],
        unique=False,
    )

    cost_submission_types = sa.table(
        "cost_submission_types",
        sa.column("code", sa.String(length=50)),
        sa.column("label", sa.String(length=120)),
        sa.column("description", sa.Text()),
        sa.column("is_active", sa.Boolean()),
    )
    moderation_statuses = sa.table(
        "moderation_statuses",
        sa.column("code", sa.String(length=50)),
        sa.column("label", sa.String(length=120)),
        sa.column("description", sa.Text()),
        sa.column("is_terminal", sa.Boolean()),
    )

    op.bulk_insert(
        cost_submission_types,
        [
            {
                "code": "PINT",
                "label": "Pint",
                "description": "Price observation for a pint in a venue.",
                "is_active": True,
            },
            {
                "code": "TAKEAWAY",
                "label": "Takeaway",
                "description": "Price observation for a takeaway item.",
                "is_active": True,
            },
        ],
    )

    op.bulk_insert(
        moderation_statuses,
        [
            {
                "code": "PENDING",
                "label": "Pending",
                "description": "Awaiting moderation decision.",
                "is_terminal": False,
            },
            {
                "code": "APPROVED",
                "label": "Approved",
                "description": "Accepted for downstream analytics.",
                "is_terminal": True,
            },
            {
                "code": "REJECTED",
                "label": "Rejected",
                "description": "Rejected during moderation.",
                "is_terminal": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_user_cost_submissions_submitted_via_api_key_id", table_name="user_cost_submissions")
    op.drop_index("ix_user_cost_submissions_moderation_status_id", table_name="user_cost_submissions")
    op.drop_index("ix_user_cost_submissions_submission_type_id", table_name="user_cost_submissions")

    op.drop_table("user_cost_submissions")
    op.drop_table("api_keys")
    op.drop_table("moderation_statuses")
    op.drop_table("cost_submission_types")
