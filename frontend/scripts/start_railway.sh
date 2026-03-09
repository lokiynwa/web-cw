#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-4173}"

echo "Starting frontend preview server on 0.0.0.0:${PORT} ..."
exec ./node_modules/.bin/vite preview --host 0.0.0.0 --port "${PORT}" --strictPort
