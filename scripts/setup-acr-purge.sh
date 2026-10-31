#!/usr/bin/env bash
# Keep the registry from growing without bound: a weekly ACR Task runs
# `acr purge` on this project's two image repositories.
#
# Without arguments (the safe default) it:
#   1. locks the SHA tag each container app runs right now, so the purge can
#      never delete an image a replica needs for its next cold start (the
#      Deploy workflow and redeploy.sh keep these locks up to date afterwards);
#   2. runs the purge once as a DRY RUN and prints what it would delete.
#
# With --create it also creates (or replaces) the weekly task
# `purge-podcasts-images`, Sundays 03:00 UTC, with the same command minus
# --dry-run. Read the dry-run output first.
#
# What it deletes: tags that are a full 40-character git SHA, in
# podcasts-agent / podcasts-web only, older than 30 days, but always keeping
# the newest 10 per repository; --untagged also removes the manifests those
# deletions leave behind. `:latest`, other tags, other projects' repositories
# and locked tags are never touched, and --include-locked is never used.
# `acr purge` is a preview feature and deletes permanently.
#
# Auth is the live `az login` session. The task authenticates to the registry
# by itself.
#
# Usage: ./scripts/setup-acr-purge.sh [--create]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

TASK=purge-podcasts-images
SCHEDULE="0 3 * * Sun"
AGO=30d
KEEP=10

create=0
case "${1:-}" in
  "") ;;
  --create) create=1 ;;
  *) echo "usage: $0 [--create]" >&2; exit 2 ;;
esac

# 1. Lock what is running now.
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo app _ <<<"$entry"
  current=$(az containerapp show -n "$app" -g "$RG" \
    --query "properties.template.containers[0].image" -o tsv)
  tag="${current##*:}"
  if is_sha "$tag"; then
    lock_tag "$repo" "$tag"
    echo "locked $repo:$tag (running in $app)"
  else
    echo "not locking $repo: $app runs '$current', not a SHA tag"
  fi
done

# 2. The purge command, one filter per repository.
purge="acr purge"
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ <<<"$entry"
  purge+=" --filter '$repo:^[0-9a-f]{40}\$'"
done
purge+=" --ago $AGO --keep $KEEP --untagged"

echo
echo "Dry run (nothing is deleted):"
az acr run --registry "$ACR" --cmd "$purge --dry-run" /dev/null

if [ "$create" -eq 0 ]; then
  echo
  echo "Review the list above. If it only names old SHA tags of podcasts-* repositories,"
  echo "create the weekly task with: ./scripts/setup-acr-purge.sh --create"
  exit 0
fi

# 3. Create the weekly task (replace it if it exists).
if az acr task show -n "$TASK" -r "$ACR" -o none 2>/dev/null; then
  az acr task delete -n "$TASK" -r "$ACR" --yes
fi
az acr task create -n "$TASK" -r "$ACR" --cmd "$purge" \
  --schedule "$SCHEDULE" --context /dev/null --output none
echo "Task $TASK created: $SCHEDULE UTC, tags older than $AGO, newest $KEEP kept."
