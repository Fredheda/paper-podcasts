#!/usr/bin/env bash
# Run every check .github/workflows/ci.yml runs, in the same order, stopping at
# the first failure. Run it before `gh pr ready`, so CI is a formality.
#
# Usage: ./scripts/ci-local.sh   (from anywhere; it cd's to the repo root)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> backend"
poetry install --with backend,dev --no-interaction
poetry run ruff check .
poetry run ruff format --check .
poetry run pyright
poetry run pytest -v

echo "==> frontend"
cd frontend
npm ci --ignore-scripts
npm run lint
npm test

echo "==> frontend-build"
npm run build

echo "All CI checks passed."
