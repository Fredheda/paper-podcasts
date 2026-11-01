#!/usr/bin/env bash
# One-time (idempotent) setup so GitHub Actions can build and deploy this
# project with no stored secrets, using OpenID Connect (workload identity
# federation).
#
# What it does:
#   1. Creates two user-assigned managed identities in rg-chatbot:
#        id-podcasts-gh-build   pushes images (the Deploy workflow's build step)
#        id-podcasts-gh-deploy  rolls the two container apps (the Deploy
#                               workflow's deploy step)
#   2. Grants each only what it needs:
#        build:  AcrPush + Container Registry Tasks Contributor on the registry
#                (no right to change a container app)
#        deploy: AcrPush on the registry (to lock/unlock deployed tags -- note
#                that this also lets it push images; the registry is in
#                legacy permission mode, which cannot scope pushes by
#                repository), Container Apps Contributor on each of the two
#                apps, and Managed Identity Operator on the apps' AcrPull
#                identity (updating an app that uses it needs assign/action)
#   3. Adds one federated credential to each identity: only the job that runs
#      in the `production` environment of this repo. The build runs inside the
#      Deploy workflow, so it uses the same environment subject.
#   4. Creates the `production` GitHub environment, restricted to jobs running
#      on the main branch (a branch author cannot edit their way around it)
#      and gated by the repo owner as required reviewer (every deploy waits
#      for his approval in GitHub), and stores the Azure IDs the workflow
#      reads as repo SECRETS:
#      AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_BUILD_CLIENT_ID,
#      AZURE_DEPLOY_CLIENT_ID. They are identifiers, not credentials; a secret
#      is used so GitHub masks the value in run logs (this repo is public).
#
# Needs the signed-in user to be able to create identities, assign roles, and
# administer the GitHub repo. Auth is the live `az login` and `gh auth`
# sessions; nothing secret is written anywhere. Federated credentials do not
# expire.
#
# Usage: ./scripts/setup-github-deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

GH_REPO=Fredheda/paper-podcasts
LOCATION=westeurope
BUILD_ID=id-podcasts-gh-build
DEPLOY_ID=id-podcasts-gh-deploy
PULL_ID=id-podcasts-acrpull
ISSUER=https://token.actions.githubusercontent.com

TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Subscription $SUBSCRIPTION_ID, repo $GH_REPO"

ensure_identity() {
  local name=$1
  if az identity show -g "$RG" -n "$name" -o none 2>/dev/null; then
    echo "identity $name: exists" >&2
  else
    az identity create -g "$RG" -n "$name" -l "$LOCATION" -o none
    echo "identity $name: created" >&2
  fi
}

# Role assignment by object id + principal type, so a just-created identity
# does not have to wait for Entra replication before the lookup succeeds.
ensure_role() {
  local principal=$1 role=$2 scope=$3
  az role assignment create --assignee-object-id "$principal" \
    --assignee-principal-type ServicePrincipal \
    --role "$role" --scope "$scope" -o none
  echo "role '$role' on ${scope##*/}: ensured"
}

ensure_federated_credential() {
  local identity=$1 name=$2 subject=$3
  if az identity federated-credential show -g "$RG" --identity-name "$identity" \
    --name "$name" -o none 2>/dev/null; then
    echo "federated credential $identity/$name: exists"
  else
    az identity federated-credential create -g "$RG" --identity-name "$identity" \
      --name "$name" --issuer "$ISSUER" --subject "$subject" \
      --audiences api://AzureADTokenExchange -o none
    echo "federated credential $identity/$name: created ($subject)"
  fi
}

ensure_identity "$BUILD_ID"
ensure_identity "$DEPLOY_ID"
BUILD_PRINCIPAL=$(az identity show -g "$RG" -n "$BUILD_ID" --query principalId -o tsv)
BUILD_CLIENT=$(az identity show -g "$RG" -n "$BUILD_ID" --query clientId -o tsv)
DEPLOY_PRINCIPAL=$(az identity show -g "$RG" -n "$DEPLOY_ID" --query principalId -o tsv)
DEPLOY_CLIENT=$(az identity show -g "$RG" -n "$DEPLOY_ID" --query clientId -o tsv)

ACR_ID=$(az acr show -n "$ACR" --query id -o tsv)
PULL_ID_RESOURCE=$(az identity show -g "$RG" -n "$PULL_ID" --query id -o tsv)

ensure_role "$BUILD_PRINCIPAL" "AcrPush" "$ACR_ID"
ensure_role "$BUILD_PRINCIPAL" "Container Registry Tasks Contributor" "$ACR_ID"

ensure_role "$DEPLOY_PRINCIPAL" "AcrPush" "$ACR_ID"
ensure_role "$DEPLOY_PRINCIPAL" "Managed Identity Operator" "$PULL_ID_RESOURCE"
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r _ app _ <<<"$entry"
  app_id=$(az containerapp show -n "$app" -g "$RG" --query id -o tsv)
  ensure_role "$DEPLOY_PRINCIPAL" "Container Apps Contributor" "$app_id"
done

SUBJECT="repo:$GH_REPO:environment:production"
ensure_federated_credential "$BUILD_ID" github-production "$SUBJECT"
ensure_federated_credential "$DEPLOY_ID" github-production "$SUBJECT"

# Both identities trust any job that runs in the `production` environment,
# whatever branch it runs on, and the `main`-only check inside deploy.yml is in
# a file any branch author can edit. So the environment itself only admits
# jobs from main: GitHub enforces this outside the workflow file. The repo
# owner is its required reviewer, so every deploy waits for his approval in
# GitHub (the run shows `waiting`) and no admin can bypass that. Required
# reviewers need a public repo on the Free plan.
OWNER_ID=$(gh api "users/${GH_REPO%%/*}" --jq .id)
gh api -X PUT "repos/$GH_REPO/environments/production" --input - \
  --jq '"environment " + .name + ": ensured"' <<EOF
{
  "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true},
  "reviewers": [{"type": "User", "id": $OWNER_ID}],
  "prevent_self_review": false,
  "can_admins_bypass": false
}
EOF
policies=$(gh api "repos/$GH_REPO/environments/production/deployment-branch-policies" \
  --jq '.branch_policies[].name')
if grep -qx main <<<"$policies"; then
  echo "environment production: branch policy main exists"
else
  gh api -X POST "repos/$GH_REPO/environments/production/deployment-branch-policies" \
    -f name=main -f type=branch --silent
  echo "environment production: branch policy main created"
fi
while IFS= read -r other; do
  [ -z "$other" ] || [ "$other" = main ] && continue
  echo "WARNING: environment production also admits branch '$other'; remove it in Settings > Environments unless intended." >&2
done <<<"$policies"
gh secret set AZURE_TENANT_ID --body "$TENANT_ID" -R "$GH_REPO"
gh secret set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID" -R "$GH_REPO"
gh secret set AZURE_BUILD_CLIENT_ID --body "$BUILD_CLIENT" -R "$GH_REPO"
gh secret set AZURE_DEPLOY_CLIENT_ID --body "$DEPLOY_CLIENT" -R "$GH_REPO"
echo "repo secrets: set"
echo "Done. Re-running changes nothing."
