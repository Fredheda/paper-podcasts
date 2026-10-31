# Shared by build-push.sh, redeploy.sh, wait-healthy.sh, setup-github-deploy.sh
# and setup-acr-purge.sh: the one list of images and container apps, so
# building, deploying, locking and purging can never disagree about what this
# project ships. Sourced, not executed.

ACR=acrchatbotfredheda
RG=rg-chatbot

# "<acr repository>|<container app>|<dockerfile>|<build context>", in the
# order the apps are built and rolled. The backend context is the repo root
# because it imports the sibling `src/` and `prompts/` directories.
IMAGES=(
  "podcasts-agent|ca-podcasts-agent|backend/Dockerfile|."
  "podcasts-web|ca-podcasts-web|frontend/Dockerfile|frontend"
)

# True for a full 40-character lowercase hex git SHA, the only tag the
# deploy pipeline builds, deploys, locks or purges.
is_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]]
}

# True if <repo>:<tag> exists in the registry.
image_exists() {
  az acr repository show -n "$ACR" --image "$1:$2" -o none >/dev/null 2>&1
}

# Protect a deployed tag from `acr purge` (it can still be re-pushed).
lock_tag() {
  az acr repository update -n "$ACR" --image "$1:$2" \
    --delete-enabled false --write-enabled true --output none
}

# Make a tag purgeable again once no app runs it.
unlock_tag() {
  az acr repository update -n "$ACR" --image "$1:$2" \
    --delete-enabled true --write-enabled true --output none
}
