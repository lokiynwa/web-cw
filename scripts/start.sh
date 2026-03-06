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

# Railway injects env vars directly, but local parity is useful.
load_env_file ".env.example"
load_env_file ".env"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-true}"
RUN_MIGRATIONS_FLAG="$(printf '%s' "${RUN_MIGRATIONS_ON_START}" | tr '[:upper:]' '[:lower:]')"

case "${RUN_MIGRATIONS_FLAG}" in
  true|1|yes|y|on)
    echo "Running database migrations..."
    python -m alembic upgrade head
    ;;
  *)
    echo "Skipping startup migrations (RUN_MIGRATIONS_ON_START=${RUN_MIGRATIONS_ON_START})."
    ;;
esac

echo "Starting production server on ${HOST}:${PORT} ..."
exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
