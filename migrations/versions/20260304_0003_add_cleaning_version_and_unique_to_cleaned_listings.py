"""Add cleaning_version and composite uniqueness to cleaned_listings."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260304_0003"
down_revision = "20260304_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cleaned_listings") as batch_op:
        batch_op.add_column(
            sa.Column("cleaning_version", sa.String(length=30), nullable=False, server_default="v1")
        )
        batch_op.drop_constraint("uq_cleaned_listings_raw_listing", type_="unique")
        batch_op.create_unique_constraint(
            "uq_cleaned_listings_raw_version", ["raw_listing_id", "cleaning_version"]
        )


def downgrade() -> None:
    with op.batch_alter_table("cleaned_listings") as batch_op:
        batch_op.drop_constraint("uq_cleaned_listings_raw_version", type_="unique")
        batch_op.create_unique_constraint("uq_cleaned_listings_raw_listing", ["raw_listing_id"])
        batch_op.drop_column("cleaning_version")
