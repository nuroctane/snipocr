#!/usr/bin/env bash
# Launch SnipOCR on macOS / Linux (creates venv on first run if missing)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV_PY="$ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r requirements.txt
fi

echo "Starting SnipOCR..."
exec "$VENV_PY" main.py
