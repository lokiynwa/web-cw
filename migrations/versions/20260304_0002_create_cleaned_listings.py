"""Create cleaned_listings table for conservative rule-based cleaning."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260304_0002"
down_revision = "20260304_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cleaned_listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_listing_id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("price_gbp_weekly", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("deposit_gbp", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("listing_type", sa.String(length=50), nullable=True),
        sa.Column("address_normalized", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("area", sa.String(length=120), nullable=True),
        sa.Column("is_ensuite_proxy", sa.Boolean(), nullable=True),
        sa.Column("house_size_bucket", sa.String(length=30), nullable=True),
        sa.Column("valid_price", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_deposit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_bedrooms", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_bathrooms", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_type", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_address", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("exclusion_reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_listing_id"], ["raw_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_listing_id", name="uq_cleaned_listings_raw_listing"),
    )

    op.create_index("ix_cleaned_listings_import_batch_id", "cleaned_listings", ["import_batch_id"], unique=False)
    op.create_index("ix_cleaned_listings_raw_listing_id", "cleaned_listings", ["raw_listing_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cleaned_listings_raw_listing_id", table_name="cleaned_listings")
    op.drop_index("ix_cleaned_listings_import_batch_id", table_name="cleaned_listings")
    op.drop_table("cleaned_listings")
