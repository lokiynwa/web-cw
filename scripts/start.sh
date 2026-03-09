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

is_truthy() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_running_on_railway() {
  [[ -n "${RAILWAY_ENVIRONMENT:-}" || -n "${RAILWAY_PROJECT_ID:-}" || -n "${RAILWAY_SERVICE_ID:-}" ]]
}

# Railway injects env vars directly. For non-Railway local parity, load env files.
if ! is_running_on_railway; then
  load_env_file ".env.example"
  load_env_file ".env"
fi

if is_running_on_railway; then
  if [[ -z "${PORT:-}" ]]; then
    echo "ERROR: Railway deployment missing PORT env var."
    echo "Action: confirm Railway runtime provided PORT and start command uses scripts/start.sh."
    exit 1
  fi

  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: Railway deployment missing DATABASE_URL env var."
    echo "Action: link PostgreSQL service and map DATABASE_URL in Railway variables."
    exit 1
  fi

  if [[ -z "${AUTH_JWT_SECRET:-}" || "${AUTH_JWT_SECRET}" == "change-me-in-production" ]]; then
    echo "ERROR: AUTH_JWT_SECRET must be set to a secure non-default value on Railway."
    echo "Action: set AUTH_JWT_SECRET in Railway variables and redeploy."
    exit 1
  fi
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-true}"

if is_truthy "${RUN_MIGRATIONS_ON_START}"; then
    echo "Running database migrations..."
    python -m alembic upgrade head
else
    echo "Skipping startup migrations (RUN_MIGRATIONS_ON_START=${RUN_MIGRATIONS_ON_START})."
fi

echo "Starting production server on ${HOST}:${PORT} (mode=${APP_RUNTIME_MODE:-rest})..."
exec uvicorn app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips="*" \
  --log-level info
