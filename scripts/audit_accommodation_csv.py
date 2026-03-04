#!/usr/bin/env python3
"""Standalone CSV audit script for accommodation datasets.

Reports:
- row count and column names
- missing-value counts per column
- numeric summaries for Price, Bedrooms, Bathrooms, and Deposit
- preview of city/sub-area extraction candidates from address field
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

POSTCODE_PATTERN = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE)
NON_NUMERIC_CHARS = re.compile(r"[^0-9.+-]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit an accommodation CSV file.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        help="Path to CSV file. Defaults to raw_data/accommodation.csv if present, otherwise first CSV in raw_data/.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=12,
        help="Number of address preview rows to print (default: 12).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top candidate city/sub-area values to print (default: 10).",
    )
    return parser.parse_args()


def resolve_csv_path(requested_path: str | None) -> Path:
    if requested_path:
        path = Path(requested_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        return path

    preferred = Path("raw_data/accommodation.csv").resolve()
    if preferred.exists():
        return preferred

    candidates = sorted(Path("raw_data").glob("*.csv"))
    if candidates:
        return candidates[0].resolve()

    raise FileNotFoundError(
        "No CSV file found. Put one in raw_data/ or pass a file path."
    )


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def find_column(columns: Sequence[str], target: str) -> str | None:
    target_norm = normalize_name(target)
    col_norms = {col: normalize_name(col) for col in columns}

    for col, norm in col_norms.items():
        if norm == target_norm:
            return col

    for col, norm in col_norms.items():
        if target_norm in norm:
            return col

    return None


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None

    cleaned = NON_NUMERIC_CHARS.sub("", stripped)
    if cleaned in {"", "+", "-", ".", "+.", "-."}:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def missing_count(values: Iterable[str | None]) -> int:
    count = 0
    for value in values:
        if value is None or not value.strip():
            count += 1
    return count


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
        }

    std_value = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "std": std_value,
    }


def format_float(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    if math.isfinite(value):
        return f"{value:,.2f}"
    return "n/a"


def infer_city_and_sub_area(address: str | None) -> tuple[str | None, str | None]:
    if not address or not address.strip():
        return None, None

    raw_parts = [part.strip() for part in address.split(",") if part.strip()]
    if not raw_parts:
        return None, None

    cleaned_parts: list[str] = []
    for part in raw_parts:
        no_postcode = POSTCODE_PATTERN.sub("", part).strip(" ,")
        if no_postcode and no_postcode.lower() not in {
            "uk",
            "united kingdom",
            "england",
        }:
            cleaned_parts.append(no_postcode)

    if not cleaned_parts:
        return None, None

    city = cleaned_parts[-1]
    sub_area = cleaned_parts[-2] if len(cleaned_parts) >= 2 else None
    return city, sub_area


def print_header(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main() -> None:
    args = parse_args()
    csv_path = resolve_csv_path(args.csv_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        raw_fieldnames = reader.fieldnames or []
        columns = [col.strip() for col in raw_fieldnames if col and col.strip()]
        rows = list(reader)

    if not columns:
        raise ValueError(f"No columns found in {csv_path}")

    total_rows = len(rows)
    total_columns = len(columns)

    print("Accommodation CSV Audit Report")
    print("==============================")
    print(f"File: {csv_path}")

    print_header("Dataset Overview")
    print(f"Total rows: {total_rows}")
    print(f"Total columns: {total_columns}")
    print("Column names:")
    for idx, col in enumerate(columns, start=1):
        print(f"  {idx:>2}. {col}")

    print_header("Missing Values by Column")
    for col in columns:
        col_missing = missing_count(row.get(col) for row in rows)
        pct = (col_missing / total_rows * 100) if total_rows else 0
        print(f"- {col}: {col_missing} missing ({pct:.1f}%)")

    print_header("Numeric Summaries")
    target_fields = ["Price", "Bedrooms", "Bathrooms", "Deposit"]

    for target in target_fields:
        actual_col = find_column(columns, target)
        if not actual_col:
            print(f"\n{target}: column not found")
            continue

        raw_values = [row.get(actual_col) for row in rows]
        parsed_values = [
            num for num in (parse_number(v) for v in raw_values) if num is not None
        ]
        field_missing = missing_count(raw_values)
        summary = numeric_summary(parsed_values)

        print(f"\n{target} (source column: {actual_col})")
        print(f"  missing: {field_missing}")
        print(f"  numeric parsed: {summary['count']}")
        print(f"  mean: {format_float(summary['mean'])}")
        print(f"  median: {format_float(summary['median'])}")
        print(f"  min: {format_float(summary['min'])}")
        print(f"  max: {format_float(summary['max'])}")
        print(f"  std dev: {format_float(summary['std'])}")

    print_header("Address Extraction Candidate Preview")
    address_col = find_column(columns, "Address")
    if not address_col:
        print("Address column not found (looked for names containing 'address').")
        return

    print(f"Using address source column: {address_col}")

    preview_rows = 0
    city_counter: Counter[str] = Counter()
    sub_area_counter: Counter[str] = Counter()
    city_sub_area_counter: Counter[str] = Counter()

    for row in rows:
        address = row.get(address_col)
        city, sub_area = infer_city_and_sub_area(address)

        if city:
            city_counter[city] += 1
        if sub_area:
            sub_area_counter[sub_area] += 1
        if city and sub_area:
            city_sub_area_counter[f"{city} - {sub_area}"] += 1

        if preview_rows < args.preview_rows and address and address.strip():
            preview_rows += 1
            print(f"\n[{preview_rows}] address: {address}")
            print(f"    city_candidate: {city or 'n/a'}")
            print(f"    sub_area_candidate: {sub_area or 'n/a'}")

    print("\nTop city candidates:")
    if city_counter:
        for city, count in city_counter.most_common(args.top_n):
            print(f"- {city}: {count}")
    else:
        print("- n/a")

    print("\nTop sub-area candidates:")
    if sub_area_counter:
        for area, count in sub_area_counter.most_common(args.top_n):
            print(f"- {area}: {count}")
    else:
        print("- n/a")

    print("\nTop city-sub-area combinations:")
    if city_sub_area_counter:
        for pair, count in city_sub_area_counter.most_common(args.top_n):
            print(f"- {pair}: {count}")
    else:
        print("- n/a")


if __name__ == "__main__":
    main()
