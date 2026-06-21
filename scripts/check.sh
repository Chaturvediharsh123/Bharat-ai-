#!/usr/bin/env bash
# BharatAI quality gate: lint, type-check, architecture contracts, tests + coverage.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv/bin}"

echo "== ruff (lint) =="
"$VENV/ruff" check .

echo "== mypy (strict type-check) =="
"$VENV/mypy" bharatai

echo "== import-linter (architecture contracts) =="
"$VENV/lint-imports"

echo "== pytest + coverage =="
"$VENV/python" -m pytest --cov=bharatai --cov-report=term-missing

echo
echo "✅ All quality gates passed."
