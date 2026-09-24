#!/usr/bin/env bash
# Push code/config from here to Hemin's GPU training box (~/code/face-counter),
# one-way, only the pieces the training side needs. Never touches Hemin's
# data/raw/ (his in-progress export) or venv/git internals -- those are
# excluded below and rebuilt with `uv sync` / `shelf-export` on his side.
#
# Split into role-owned folders (src/face_counter/training, label_studio,
# serving, utils) so this exclude list can leave out what belongs to this
# machine only: label_studio/ and serving/ never need to exist on the GPU box.
#
# Refuses to run against a dirty tree on either side -- rsync has no merge
# logic, so an uncommitted edit on the receiving end would be silently
# overwritten with no diff and no way back.
#
# Usage:
#   scripts/sync_to_hemin.sh            # sync code/config only (default)
#   scripts/sync_to_hemin.sh --with-data   # also send data/raw/ -- do NOT use
#                                           # this while Hemin's export is running;
#                                           # data should flow FROM his box, not to it
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root, regardless of where this is invoked from

HOST="hemin"                       # ~/.ssh/config alias for the 4060 Ti box
REMOTE_DIR="~/code/face-counter/"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Local tree is dirty. Commit before syncing -- rsync has no merge" >&2
  echo "logic and would push uncommitted local state as-is." >&2
  exit 1
fi
if ! ssh "${HOST}" "cd code/face-counter && [[ -z \"\$(git status --porcelain)\" ]]"; then
  echo "${HOST}'s tree is dirty. Uncommitted changes there would be silently" >&2
  echo "overwritten by this sync -- ssh in and commit/stash first." >&2
  exit 1
fi

EXCLUDES=(
  --exclude .venv
  --exclude .git
  --exclude __pycache__
  --exclude .pytest_cache
  --exclude .ruff_cache
  --exclude '*.egg-info'
  --exclude .env
  --exclude 'data/splits/'
  --exclude 'data/label_studio/'
  # Role folders this side owns; the GPU box only needs training/ + utils/.
  --exclude 'src/face_counter/label_studio/'
  --exclude 'src/face_counter/serving/'
)

if [[ "${1:-}" != "--with-data" ]]; then
  EXCLUDES+=(--exclude 'data/raw/')
fi

echo "Syncing to ${HOST}:${REMOTE_DIR} ..."
rsync -av "${EXCLUDES[@]}" ./ "${HOST}:${REMOTE_DIR}"

echo
echo "Done. To pick up new/changed dependencies on the GPU box, run:"
echo "  ssh ${HOST} 'cd code/face-counter && ~/.local/bin/uv sync --group dev --group analytics'"
