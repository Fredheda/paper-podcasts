#!/usr/bin/env bash
# Build both images natively on linux/amd64 with ACR Tasks and push
# :latest + :<git-sha>. Auth: the caller's live `az login` session (or the
# GitHub build identity) -- no stored credentials. The upload honors
# .dockerignore, so .env stays out.
#
# An image that already exists for the commit is skipped, so building a commit
# twice (a second Deploy of the same SHA, or ship.sh after a Deploy) is a
# no-op, and rolling back to an already-built commit builds nothing.
#
# The images are built from `git archive <sha>` in a temporary directory, never
# from the working tree, so the :<git-sha> tag is honest for any commit,
# including one that is not checked out. The backend context is the repo root
# because it imports the sibling `src/` and `prompts/` directories.
#
# Usage: ./scripts/build-push.sh [full-commit-sha]   (default: HEAD)
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

SHA=${1-$(git rev-parse HEAD)}  # an explicit empty argument is rejected, not HEAD
if ! is_sha "$SHA"; then
  echo "ERROR: '$SHA' is not a full 40-character lowercase commit SHA." >&2
  exit 1
fi
if ! git cat-file -e "$SHA^{commit}" 2>/dev/null; then
  echo "ERROR: $SHA is not a commit in this repository." >&2
  exit 1
fi

missing=()
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ <<<"$entry"
  if image_exists "$repo" "$SHA"; then
    echo "Skipping $repo: $SHA already built."
  else
    missing+=("$entry")
  fi
done

built=()
if [ "${#missing[@]}" -gt 0 ]; then
  src=$(mktemp -d)
  trap 'rm -rf "$src"' EXIT
  git archive "$SHA" | tar -x -C "$src"
  cd "$src"
  for entry in "${missing[@]}"; do
    IFS='|' read -r repo _ dockerfile context <<<"$entry"
    az acr build --registry "$ACR" --file "$dockerfile" \
      --image "$repo:latest" --image "$repo:$SHA" "$context"
    built+=("$repo")
  done
fi

if [ "${#built[@]}" -eq 0 ]; then
  echo "Nothing to build: all images already exist at $SHA"
else
  echo "Pushed ${built[*]} at $SHA"
fi
