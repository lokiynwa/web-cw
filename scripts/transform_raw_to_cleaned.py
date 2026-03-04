#!/usr/bin/env python3
"""Transform raw_listings into cleaned_listings using rule-based cleaning policy.

Properties:
- Reads immutable source rows from raw_listings
- Applies conservative cleaning rules
- Writes one cleaned row per (raw_listing_id, cleaning_version)
- Safe to rerun: skips existing cleaned rows for the same version
- Preserves linkage to raw row and import batch
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.db import SessionLocal, engine
from app.models import CleanedListing, RawListing
from app.services.cleaning import clean_listing_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform raw_listings into cleaned_listings.")
    parser.add_argument(
        "--batch-id",
        type=int,
        default=None,
        help="Optional import_batch_id filter. If omitted, transform all raw rows.",
    )
    parser.add_argument(
        "--cleaning-version",
        default="v1",
        help="Cleaning policy version label stored on cleaned rows (default: v1).",
    )
    return parser.parse_args()


def ensure_required_tables() -> None:
    inspector = inspect(engine)
    required_tables = {"raw_listings", "cleaned_listings", "import_batches"}
    existing_tables = set(inspector.get_table_names())
    missing = sorted(required_tables - existing_tables)
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(
            f"Missing required tables: {missing_str}. "
            "Run database migrations first with: python -m alembic upgrade head"
        )


def main() -> None:
    args = parse_args()
    cleaning_version = args.cleaning_version.strip()
    if not cleaning_version:
        raise ValueError("--cleaning-version must not be empty")

    ensure_required_tables()

    session = SessionLocal()

    inserted = 0
    skipped_existing = 0
    excluded_count = 0

    started_at = datetime.now(timezone.utc)

    try:
        raw_stmt = select(RawListing)
        if args.batch_id is not None:
            raw_stmt = raw_stmt.where(RawListing.import_batch_id == args.batch_id)
        raw_stmt = raw_stmt.order_by(RawListing.id)

        raw_rows = session.execute(raw_stmt).scalars().all()

        if not raw_rows:
            print("Transform Summary")
            print("-----------------")
            print("raw_rows_seen: 0")
            print("rows_inserted: 0")
            print("rows_skipped_existing_version: 0")
            print("rows_marked_excluded: 0")
            print(f"cleaning_version: {cleaning_version}")
            print(f"batch_filter: {args.batch_id}")
            return

        raw_ids = [row.id for row in raw_rows]
        existing_stmt = select(CleanedListing.raw_listing_id).where(
            CleanedListing.cleaning_version == cleaning_version,
            CleanedListing.raw_listing_id.in_(raw_ids),
        )
        existing_ids = set(session.execute(existing_stmt).scalars().all())

        for raw in raw_rows:
            if raw.id in existing_ids:
                skipped_existing += 1
                continue

            cleaned = clean_listing_row(raw.source_row_data)
            if cleaned.is_excluded:
                excluded_count += 1

            row = CleanedListing(
                raw_listing_id=raw.id,
                import_batch_id=raw.import_batch_id,
                cleaning_version=cleaning_version,
                price_gbp_weekly=cleaned.price_gbp_weekly,
                deposit_gbp=cleaned.deposit_gbp,
                bedrooms=cleaned.bedrooms,
                bathrooms=cleaned.bathrooms,
                listing_type=cleaned.listing_type,
                address_normalized=cleaned.address_normalized,
                city=cleaned.city,
                area=cleaned.area,
                is_ensuite_proxy=cleaned.is_ensuite_proxy,
                house_size_bucket=cleaned.house_size_bucket,
                valid_price=cleaned.valid_price,
                valid_deposit=cleaned.valid_deposit,
                valid_bedrooms=cleaned.valid_bedrooms,
                valid_bathrooms=cleaned.valid_bathrooms,
                valid_type=cleaned.valid_type,
                valid_address=cleaned.valid_address,
                is_excluded=cleaned.is_excluded,
                exclusion_reasons=cleaned.exclusion_reasons,
            )

            session.add(row)
            inserted += 1

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()

    finished_at = datetime.now(timezone.utc)
    elapsed_seconds = (finished_at - started_at).total_seconds()

    print("Transform Summary")
    print("-----------------")
    print(f"raw_rows_seen: {len(raw_rows)}")
    print(f"rows_inserted: {inserted}")
    print(f"rows_skipped_existing_version: {skipped_existing}")
    print(f"rows_marked_excluded: {excluded_count}")
    print(f"cleaning_version: {cleaning_version}")
    print(f"batch_filter: {args.batch_id}")
    print(f"duration_seconds: {elapsed_seconds:.2f}")


if __name__ == "__main__":
    main()
