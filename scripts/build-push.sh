#!/usr/bin/env bash
# Build both images natively on linux/amd64 with ACR Tasks and push
# :latest + :<git-sha>. Adapted from copilot-kit-exp/scripts/build-push.sh.
#
# Backend build context is the REPO ROOT (not backend/), same reason as
# copilot-kit-exp's agent/Dockerfile: the backend imports sibling `src/` and
# `prompts/` directories that live outside backend/.
#
# NOTE: az acr build builds the WORKING TREE, not the committed SHA. Run it
# with a clean tree so the :<git-sha> tag is honest.
#
# Usage: ./scripts/build-push.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ACR=acrchatbotfredheda
SHA=$(git rev-parse HEAD)

az acr build --registry "$ACR" --file backend/Dockerfile \
  --image podcasts-agent:latest --image "podcasts-agent:$SHA" .

az acr build --registry "$ACR" --file frontend/Dockerfile \
  --image podcasts-web:latest --image "podcasts-web:$SHA" frontend

echo "Pushed podcasts-agent and podcasts-web at $SHA"
