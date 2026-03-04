#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

load_env_file() {
  local env_file="$1"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
  fi
}

load_env_file ".env.example"
load_env_file ".env"

echo "Running database migrations..."
python -m alembic upgrade head

SEED_CSV_PATH="raw_data/accommodation.csv"
if [[ -f "${SEED_CSV_PATH}" ]]; then
  echo "Seed CSV found at ${SEED_CSV_PATH}. Importing raw listings..."
  python scripts/import_accommodation_raw.py "${SEED_CSV_PATH}"
else
  echo "No seed CSV found at ${SEED_CSV_PATH}. Skipping seed import."
fi

echo "Starting API server at http://127.0.0.1:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
