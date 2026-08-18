#!/usr/bin/env bash
# Lock the frontend (ca-podcasts-web) behind Entra Easy Auth so ONLY the
# owner and explicitly-approved users can reach it. Idempotent -- safe to
# re-run. Adapted from copilot-kit-exp/scripts/setup-easyauth.sh -- registers
# BOTH the default FQDN and podcasts.frederikheda.com from the start (no
# retrofit needed, unlike the agent app's history).
#
# What it does:
#   1. Creates (or reuses) an Entra app registration `podcasts-easyauth` with
#      both redirect URIs + a 2-year client secret + a service principal.
#   2. Enables Easy Auth on the frontend app: unauthenticated requests are
#      redirected to the Microsoft login page before they ever reach the app.
#   3. Sets appRoleAssignmentRequired=true and assigns the signed-in owner, so
#      only assigned users get in. Add more users with scripts/approve-user.sh.
#
# No secret is written to disk or git: the client secret only ever lives in a
# runtime variable and is stored by Azure as a container-app secret. Auth for
# every command is the live `az login` session.
#
# The client secret expires in 2 YEARS. To rotate: re-run this script.
#
# Usage: ./scripts/setup-easyauth.sh
set -euo pipefail
cd "$(dirname "$0")/.."

RG=rg-chatbot
WEB_APP=ca-podcasts-web
APP_NAME=podcasts-easyauth

FQDN=$(az containerapp show -n "$WEB_APP" -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
CUSTOM_DOMAIN=podcasts.frederikheda.com
TENANT_ID=$(az account show --query tenantId -o tsv)
REDIRECT_URIS="https://$FQDN/.auth/login/aad/callback https://$CUSTOM_DOMAIN/.auth/login/aad/callback"
echo "Frontend FQDN: $FQDN"
echo "Custom domain: $CUSTOM_DOMAIN"

# --- Step 1: app registration (create or reuse) + secret + service principal ---
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ]; then
  echo "Creating app registration '$APP_NAME'..."
  APP_ID=$(az ad app create \
    --display-name "$APP_NAME" \
    --sign-in-audience AzureADMyOrg \
    --web-redirect-uris $REDIRECT_URIS \
    --enable-id-token-issuance true \
    --query appId -o tsv)
else
  echo "Reusing existing app registration '$APP_NAME' ($APP_ID); ensuring redirect URIs..."
  az ad app update --id "$APP_ID" \
    --web-redirect-uris $REDIRECT_URIS \
    --enable-id-token-issuance true --output none
fi
echo "APP_ID=$APP_ID"

CLIENT_SECRET=$(az ad app credential reset --id "$APP_ID" \
  --display-name easyauth --years 2 --query password -o tsv)
[ -n "$CLIENT_SECRET" ] && echo "client secret generated (hidden)"

if [ -z "$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv)" ]; then
  az ad sp create --id "$APP_ID" --output none
  echo "service principal created"
  sleep 15
else
  echo "service principal already exists"
fi

# --- Step 2: enable Easy Auth on the frontend ---
az containerapp auth microsoft update \
  --name "$WEB_APP" --resource-group "$RG" \
  --client-id "$APP_ID" --client-secret "$CLIENT_SECRET" \
  --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" \
  --yes --output none
echo "microsoft identity provider configured"

az containerapp auth update \
  --name "$WEB_APP" --resource-group "$RG" \
  --enabled true --action RedirectToLoginPage \
  --redirect-provider azureactivedirectory --require-https true --output none
echo "easy auth enabled (unauthenticated -> RedirectToLoginPage)"

# --- Step 3: require assignment + assign the signed-in owner ---
SP_OBJ=$(az ad sp show --id "$APP_ID" --query id -o tsv)
az ad sp update --id "$APP_ID" --set appRoleAssignmentRequired=true
echo "appRoleAssignmentRequired=true"

ME=$(az ad signed-in-user show --query id -o tsv)
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_OBJ/appRoleAssignedTo" \
  --headers "Content-Type=application/json" \
  --body "{\"principalId\": \"$ME\", \"resourceId\": \"$SP_OBJ\", \"appRoleId\": \"00000000-0000-0000-0000-000000000000\"}" \
  --output none 2>/dev/null \
  && echo "owner assigned" \
  || echo "owner already assigned (ok)"

echo
echo "DONE. Only assigned users can reach https://$FQDN or https://$CUSTOM_DOMAIN"
echo "Add more users with: ./scripts/approve-user.sh <email>"
