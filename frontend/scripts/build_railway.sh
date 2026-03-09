#!/usr/bin/env bash
set -euo pipefail

is_running_on_railway() {
  [[ -n "${RAILWAY_ENVIRONMENT:-}" || -n "${RAILWAY_PROJECT_ID:-}" || -n "${RAILWAY_SERVICE_ID:-}" ]]
}

if is_running_on_railway; then
  if [[ -z "${VITE_API_BASE_URL:-}" ]]; then
    echo "ERROR: VITE_API_BASE_URL must be set for Railway frontend builds."
    echo "Action: set VITE_API_BASE_URL to your backend /api/v1 URL in Railway service variables."
    exit 1
  fi

  if [[ "${VITE_API_BASE_URL}" == *"<your-backend-domain>"* ]]; then
    echo "ERROR: VITE_API_BASE_URL still contains placeholder text."
    echo "Action: replace <your-backend-domain> with the real backend public domain."
    exit 1
  fi
fi

exec npm run build
