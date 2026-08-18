#!/usr/bin/env bash
# Approve a user for paper-podcasts: invite them as an Entra B2B guest (if
# external) and assign them to the podcasts-easyauth enterprise app so Easy
# Auth lets them in. Adapted from copilot-kit-exp/scripts/approve-user.sh.
#
# Usage: ./scripts/approve-user.sh person@example.com
#
# To revoke later: Entra portal -> Enterprise applications -> podcasts-easyauth
# -> Users and groups -> remove them.
set -euo pipefail

EMAIL="${1:?usage: approve-user.sh <email>}"
GRAPH="https://graph.microsoft.com/v1.0"

SP_OBJ=$(az ad sp list --display-name "podcasts-easyauth" --query "[0].id" -o tsv)
[ -n "$SP_OBJ" ] || { echo "ERROR: service principal 'podcasts-easyauth' not found" >&2; exit 1; }

FQDN=$(az containerapp show -n ca-podcasts-web -g rg-chatbot \
  --query properties.configuration.ingress.fqdn -o tsv)

USER_ID=$(az ad user list \
  --filter "mail eq '$EMAIL' or userPrincipalName eq '$EMAIL'" \
  --query "[0].id" -o tsv)

if [ -z "$USER_ID" ]; then
  echo "Inviting $EMAIL as a guest..."
  USER_ID=$(az rest --method POST --url "$GRAPH/invitations" \
    --headers "Content-Type=application/json" \
    --body "{\"invitedUserEmailAddress\": \"$EMAIL\", \"inviteRedirectUrl\": \"https://$FQDN\", \"sendInvitationMessage\": true}" \
    --query invitedUser.id -o tsv)
  echo "Guest invited (they'll get an email to accept)."
fi

echo "Assigning $EMAIL to the podcasts app..."
az rest --method POST \
  --url "$GRAPH/servicePrincipals/$SP_OBJ/appRoleAssignedTo" \
  --headers "Content-Type=application/json" \
  --body "{\"principalId\": \"$USER_ID\", \"resourceId\": \"$SP_OBJ\", \"appRoleId\": \"00000000-0000-0000-0000-000000000000\"}" \
  --output none

echo "Done. $EMAIL can access https://$FQDN once they've accepted the invitation."
