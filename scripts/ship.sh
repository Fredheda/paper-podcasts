#!/usr/bin/env bash
# Ship a code change: build+push the images for the current commit, then roll
# both container apps to them.
#
# Use this for CODE changes (backend/, src/, frontend/). For INFRA changes
# (infra/main.bicep, secrets, the OpenAI key) use ./infra/deploy.sh instead.
#
# Usage: ./scripts/ship.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is dirty. Commit (or stash) your changes first, so" >&2
  echo "       the image tag honestly matches the deployed commit." >&2
  git status --short >&2
  exit 1
fi

echo "==> Building and pushing images for $(git rev-parse --short HEAD)..."
./scripts/build-push.sh

echo "==> Rolling apps to the new images..."
./scripts/redeploy.sh
