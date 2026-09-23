#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python scripts/check.py --require-frontend
python -m pytest tests/e2e --in-process --expected-ai-mode mock -q -p no:cacheprovider
python -m pytest tests/e2e/test_api.py --in-process --expected-ai-mode fallback -q -p no:cacheprovider
