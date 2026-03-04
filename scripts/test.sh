#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

run_lint=false

if [[ -f "pyproject.toml" ]] && grep -q "^\[tool\.ruff" pyproject.toml; then
  if command -v ruff >/dev/null 2>&1; then
    echo "Running lint with ruff..."
    ruff check .
    run_lint=true
  else
    echo "Ruff config detected but ruff is not installed. Skipping lint."
  fi
fi

if [[ "${run_lint}" == "false" ]]; then
  if [[ (-f ".flake8" || -f "setup.cfg" || -f "tox.ini") ]] && command -v flake8 >/dev/null 2>&1; then
    echo "Running lint with flake8..."
    flake8 .
    run_lint=true
  elif [[ -f ".pylintrc" ]] && command -v pylint >/dev/null 2>&1; then
    echo "Running lint with pylint..."
    pylint app tests scripts
    run_lint=true
  fi
fi

if [[ "${run_lint}" == "false" ]]; then
  echo "No lint configuration/tool detected. Skipping lint."
fi

echo "Running pytest..."
pytest "$@"
