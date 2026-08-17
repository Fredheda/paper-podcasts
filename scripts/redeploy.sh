#!/usr/bin/env bash
# Roll both container apps to the images built from a given commit.
# Usage: ./scripts/redeploy.sh [git-sha]   (defaults to current HEAD)
set -euo pipefail

RG=rg-chatbot
SHA="${1:-$(git rev-parse HEAD)}"
[ -n "$SHA" ] || { echo "ERROR: could not resolve a SHA" >&2; exit 1; }
echo "Deploying images for commit $SHA"

az containerapp update -n ca-podcasts-agent -g "$RG" \
  --image "acrchatbotfredheda.azurecr.io/podcasts-agent:$SHA" --output none
az containerapp update -n ca-podcasts-web -g "$RG" \
  --image "acrchatbotfredheda.azurecr.io/podcasts-web:$SHA" --output none

FQDN=$(az containerapp show -n ca-podcasts-web -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Deployed. https://$FQDN"
