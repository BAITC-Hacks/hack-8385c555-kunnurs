#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ -f .venv/Scripts/python.exe ]]; then
  .venv/Scripts/python.exe scripts/check.py "$@"
elif [[ -x .venv/bin/python ]]; then
  .venv/bin/python scripts/check.py "$@"
else
  python scripts/check.py "$@"
fi
