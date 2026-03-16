#!/usr/bin/env bash
set -euo pipefail

if [[ -x ".venv/bin/python" ]]; then
  DEFAULT_PYTHON=".venv/bin/python"
else
  DEFAULT_PYTHON="$(command -v python3.12 || command -v python3)"
fi

PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON}"

echo "Using ${PYTHON_BIN}"
"${PYTHON_BIN}" scripts/smoke_test.py
"${PYTHON_BIN}" -m pytest tests/regressions -q
