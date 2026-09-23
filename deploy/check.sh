#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python scripts/check.py --require-frontend
