#!/usr/bin/env bash
# Provision (or update) the Container Apps environment + both apps from
# infra/main.bicep. Idempotent -- re-run to roll config changes.
#
# Sources the repo-root .env for the OpenAI key. Storage/SQL access is
# passwordless (Entra ID via the identity Bicep creates) -- the storage
# account and SQL server/database names are Bicep param defaults (already
# match the existing fhstorageportfolio/fhdbplayground Playground resources),
# not secrets, so nothing else needs sourcing from .env.
#
# Usage: ./infra/deploy.sh [image-tag]
#   image-tag defaults to the current git HEAD SHA (the tag build-push.sh set).
set -euo pipefail
cd "$(dirname "$0")/.."

RG=rg-chatbot
TAG="${1:-$(git rev-parse HEAD)}"
[ -n "$TAG" ] || { echo "ERROR: could not resolve an image tag" >&2; exit 1; }

[ -f .env ] || { echo "ERROR: .env not found at repo root" >&2; exit 1; }
set -a
source .env
set +a

[ -n "${OPENAI_API_KEY:-}" ] || { echo "ERROR: OPENAI_API_KEY is empty in .env" >&2; exit 1; }

echo "Deploying image tag $TAG to resource group $RG..."
az deployment group create \
  --resource-group "$RG" \
  --template-file infra/main.bicep \
  --parameters imageTag="$TAG" openaiApiKey="$OPENAI_API_KEY" \
  --query "properties.provisioningState" -o tsv

FQDN=$(az containerapp show -n ca-podcasts-web -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Frontend: https://$FQDN"
