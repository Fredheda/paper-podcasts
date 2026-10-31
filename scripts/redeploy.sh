#!/usr/bin/env bash
# Roll both container apps to the images built from a given commit.
# Usage: ./scripts/redeploy.sh [git-sha]   (defaults to current HEAD). The SHA
# must be the full 40-character commit hash.
#
# Image-only: no Bicep re-run, no OpenAI-key prompt, so secrets and storage
# access stay as `infra/deploy.sh` set them. Use after build-push.sh to promote
# built images. SHA tags (not `latest`) so every deploy creates a distinct
# revision; rollback is `./scripts/redeploy.sh <old-sha>`.
#
# Order of work:
#   1. Refuse a malformed SHA, then refuse unless BOTH images exist, so a
#      half-built commit can never leave the apps on mixed versions.
#   2. Roll the apps.
#   3. Lock the deployed tags (`acr purge` skips locked tags, so the image a
#      replica needs for its next cold start is never deleted) and unlock the
#      SHA tags the apps ran before. Nothing is locked or unlocked if a
#      rollout fails.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

SHA="${1-$(git rev-parse HEAD)}"  # an explicit empty argument is rejected, not HEAD
if ! is_sha "$SHA"; then
  echo "ERROR: '$SHA' is not a full 40-character commit SHA." >&2
  exit 2
fi
echo "Deploying images for commit $SHA"

missing=0
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ <<<"$entry"
  if ! image_exists "$repo" "$SHA"; then
    echo "ERROR: image $repo:$SHA is not in $ACR (build for this commit missing or unfinished)." >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1

# The tag each app runs now, read before anything changes.
old_tags=()
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r _ app _ <<<"$entry"
  current=$(az containerapp show -n "$app" -g "$RG" \
    --query "properties.template.containers[0].image" -o tsv)
  old_tags+=("${current##*:}")
done

for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo app _ <<<"$entry"
  az containerapp update -n "$app" -g "$RG" \
    --image "$ACR.azurecr.io/$repo:$SHA" --output none
done

status=0
i=0
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ <<<"$entry"
  lock_tag "$repo" "$SHA" || { echo "ERROR: could not lock $repo:$SHA" >&2; status=1; }
  old="${old_tags[$i]}"
  if is_sha "$old" && [ "$old" != "$SHA" ]; then
    unlock_tag "$repo" "$old" || { echo "ERROR: could not unlock $repo:$old" >&2; status=1; }
  fi
  i=$((i + 1))
done
if [ "$status" -ne 0 ]; then
  echo "The apps ARE rolled to $SHA; only the tag locking failed. Fix it with" >&2
  echo "az acr repository update --image <repo>:<tag> --delete-enabled false." >&2
  exit "$status"
fi

FQDN=$(az containerapp show -n ca-podcasts-web -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Deployed. https://$FQDN"
