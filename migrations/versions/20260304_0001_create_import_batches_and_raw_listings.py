"""Create import_batches and raw_listings tables."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260304_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("imported_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "raw_listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("source_row_data", sa.JSON(), nullable=False),
        sa.Column("source_row_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_row_number > 0", name="ck_raw_listings_source_row_number_positive"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "source_row_number", name="uq_raw_listings_batch_row"),
    )

    op.create_index("ix_raw_listings_import_batch_id", "raw_listings", ["import_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_raw_listings_import_batch_id", table_name="raw_listings")
    op.drop_table("raw_listings")
    op.drop_table("import_batches")
