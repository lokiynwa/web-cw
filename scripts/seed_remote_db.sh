#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/seed_remote_db.sh --database-url "<DATABASE_URL>" [options]

Purpose:
  Explicit/manual remote database seeding workflow for Railway/PostgreSQL:
  1) alembic upgrade head
  2) import raw accommodation CSV
  3) transform raw -> cleaned listings

Options:
  --database-url URL        Target database URL. Falls back to DATABASE_URL env var.
  --csv-path PATH           Accommodation CSV path. Default: raw_data/accommodation.csv
  --cleaning-version VALUE  Cleaning version for transform script. Default: v1
  --run-audit               Run CSV audit before import.
  --skip-transform          Stop after raw import.
  --help                    Show this help text.

Examples:
  scripts/seed_remote_db.sh --database-url "$DATABASE_URL"
  scripts/seed_remote_db.sh --database-url "$DATABASE_URL" --csv-path raw_data/accommodation.csv --run-audit
USAGE
}

is_postgres_url() {
  local input="$1"
  local lowered
  lowered="$(printf '%s' "${input}" | tr '[:upper:]' '[:lower:]')"
  [[ "${lowered}" == postgres://* || "${lowered}" == postgresql://* || "${lowered}" == postgresql+*://* ]]
}

DATABASE_URL_INPUT="${DATABASE_URL:-}"
CSV_PATH="raw_data/accommodation.csv"
CLEANING_VERSION="v1"
RUN_AUDIT="false"
SKIP_TRANSFORM="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --database-url)
      DATABASE_URL_INPUT="${2:-}"
      shift 2
      ;;
    --csv-path)
      CSV_PATH="${2:-}"
      shift 2
      ;;
    --cleaning-version)
      CLEANING_VERSION="${2:-}"
      shift 2
      ;;
    --run-audit)
      RUN_AUDIT="true"
      shift
      ;;
    --skip-transform)
      SKIP_TRANSFORM="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1"
      echo
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${DATABASE_URL_INPUT}" ]]; then
  echo "ERROR: Missing target database URL."
  echo "Action: pass --database-url or set DATABASE_URL env var."
  exit 1
fi

if ! is_postgres_url "${DATABASE_URL_INPUT}"; then
  echo "ERROR: This workflow expects a PostgreSQL database URL."
  echo "Received DATABASE_URL='${DATABASE_URL_INPUT}'."
  exit 1
fi

if [[ ! -f "${CSV_PATH}" ]]; then
  echo "ERROR: CSV file not found at '${CSV_PATH}'."
  echo "Action: download/place accommodation.csv locally and retry with --csv-path if needed."
  exit 1
fi

export DATABASE_URL="${DATABASE_URL_INPUT}"

echo "Remote seed workflow started."
echo "CSV path: ${CSV_PATH}"
echo "Cleaning version: ${CLEANING_VERSION}"

echo "Running migrations on target database..."
python -m alembic upgrade head

if [[ "${RUN_AUDIT}" == "true" ]]; then
  echo "Running CSV audit..."
  python scripts/audit_accommodation_csv.py "${CSV_PATH}"
fi

echo "Importing raw listings..."
python scripts/import_accommodation_raw.py "${CSV_PATH}"

if [[ "${SKIP_TRANSFORM}" == "true" ]]; then
  echo "Skipping transform step by request (--skip-transform)."
  echo "Remote seed workflow completed (raw import only)."
  exit 0
fi

echo "Transforming raw listings to cleaned listings..."
python scripts/transform_raw_to_cleaned.py --cleaning-version "${CLEANING_VERSION}"

echo "Remote seed workflow completed."
