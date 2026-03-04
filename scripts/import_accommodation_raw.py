#!/usr/bin/env python3
"""Import accommodation CSV rows into immutable raw tables.

- Creates a new import_batches record
- Inserts raw CSV rows into raw_listings without cleaning/transformation
- Records source row numbers
- Skips duplicate source row numbers within the same batch
- Prints a short import summary
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect

from app.db import SessionLocal, engine
from app.models import ImportBatch, RawListing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import accommodation CSV into raw_listings.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="raw_data/accommodation.csv",
        help="Path to source CSV (default: raw_data/accommodation.csv)",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def row_sha256(row: dict[str, str | None]) -> str:
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def count_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        # Subtract one header row if file is not empty.
        total_lines = sum(1 for _ in handle)
    return max(total_lines - 1, 0)


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    inspector = inspect(engine)
    required_tables = {"import_batches", "raw_listings"}
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        missing_str = ", ".join(missing_tables)
        raise RuntimeError(
            f"Missing required tables: {missing_str}. "
            "Run database migrations first with: alembic upgrade head"
        )

    source_sha = file_sha256(csv_path)
    source_row_count = count_data_rows(csv_path)

    session = SessionLocal()

    batch = ImportBatch(
        source_filename=csv_path.name,
        source_file_sha256=source_sha,
        source_row_count=source_row_count,
        imported_row_count=0,
        status="processing",
    )

    inserted_count = 0
    skipped_duplicate_row_numbers = 0
    summary_batch_id: int | None = None
    summary_status = "unknown"

    try:
        session.add(batch)
        session.flush()  # Ensure batch.id is available.

        seen_row_numbers: set[int] = set()

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)

            for source_row_number, row in enumerate(reader, start=1):
                if source_row_number in seen_row_numbers:
                    skipped_duplicate_row_numbers += 1
                    continue

                seen_row_numbers.add(source_row_number)

                # Preserve source values exactly as parsed from CSV (no cleaning/transformation).
                raw_row: dict[str, str | None] = dict(row)

                raw_listing = RawListing(
                    import_batch_id=batch.id,
                    source_row_number=source_row_number,
                    source_row_data=raw_row,
                    source_row_hash=row_sha256(raw_row),
                )
                session.add(raw_listing)
                inserted_count += 1

        batch.imported_row_count = inserted_count
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)

        session.commit()
        summary_batch_id = batch.id
        summary_status = batch.status

    except Exception as exc:
        session.rollback()

        # Best-effort failure tracking on the batch record.
        try:
            session.add(batch)
            batch.status = "failed"
            batch.error_message = str(exc)
            batch.completed_at = datetime.now(timezone.utc)
            session.commit()
        except Exception:
            session.rollback()

        raise

    finally:
        session.close()

    print("Import Summary")
    print("--------------")
    print(f"batch_id: {summary_batch_id}")
    print(f"source_file: {csv_path}")
    print(f"source_sha256: {source_sha}")
    print(f"source_rows_detected: {source_row_count}")
    print(f"rows_inserted: {inserted_count}")
    print(f"rows_skipped_duplicate_row_numbers: {skipped_duplicate_row_numbers}")
    print(f"status: {summary_status}")


if __name__ == "__main__":
    main()
