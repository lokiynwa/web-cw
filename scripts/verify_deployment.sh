#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/verify_deployment.sh --backend-url "https://backend.example.com" --frontend-url "https://frontend.example.com" [--run]

Purpose:
  Print (and optionally execute) deployment verification checks for:
  - backend health/docs/openapi
  - frontend root page + SPA shell markers

Options:
  --backend-url URL   Backend base domain (without trailing /api/v1).
  --frontend-url URL  Frontend base domain.
  --run               Execute checks immediately instead of only printing commands.
  --help              Show this help text.
USAGE
}

trim_trailing_slash() {
  local value="$1"
  printf '%s' "${value%/}"
}

BACKEND_URL=""
FRONTEND_URL=""
RUN_CHECKS="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-url)
      BACKEND_URL="${2:-}"
      shift 2
      ;;
    --frontend-url)
      FRONTEND_URL="${2:-}"
      shift 2
      ;;
    --run)
      RUN_CHECKS="true"
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

if [[ -z "${BACKEND_URL}" || -z "${FRONTEND_URL}" ]]; then
  echo "ERROR: --backend-url and --frontend-url are required."
  echo
  usage
  exit 1
fi

BACKEND_URL="$(trim_trailing_slash "${BACKEND_URL}")"
FRONTEND_URL="$(trim_trailing_slash "${FRONTEND_URL}")"

echo "Verification commands:"
echo "  curl -sS \"${BACKEND_URL}/api/v1/health\""
echo "  curl -sSI \"${BACKEND_URL}/docs\" | head -n 1"
echo "  curl -sS \"${BACKEND_URL}/openapi.json\" | grep -E '\"title\"|\"version\"' | head -n 2"
echo "  curl -sSI \"${FRONTEND_URL}\" | head -n 1"
echo "  curl -sS \"${FRONTEND_URL}\" | grep -Ei '<!doctype html|<div id=\"root\">' | head -n 2"

if [[ "${RUN_CHECKS}" != "true" ]]; then
  exit 0
fi

echo
echo "Running checks..."

echo "--- Backend: /api/v1/health"
curl -sS "${BACKEND_URL}/api/v1/health"
echo

echo "--- Backend: /docs status line"
curl -sSI "${BACKEND_URL}/docs" | head -n 1

echo "--- Backend: /openapi.json title/version"
curl -sS "${BACKEND_URL}/openapi.json" | grep -E '"title"|"version"' | head -n 2

echo "--- Frontend: root status line"
curl -sSI "${FRONTEND_URL}" | head -n 1

echo "--- Frontend: SPA shell markers"
curl -sS "${FRONTEND_URL}" | grep -Ei '<!doctype html|<div id="root">' | head -n 2

echo "Deployment verification checks completed."
