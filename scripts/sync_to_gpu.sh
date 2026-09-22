#!/usr/bin/env bash
# Sync this repo's code/config to the GPU training box (~/code/face-counter),
# without the venv, git internals, caches, or exported photos -- those either
# don't belong there or are rebuilt with `uv sync` / `shelf-export` on that
# side. Mirrors the exclusions in .gitignore.
#
# Usage:
#   scripts/sync_to_gpu.sh            # sync code/config only (default)
#   scripts/sync_to_gpu.sh --with-data   # also send data/raw/ (the exported photos)
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root, regardless of where this is invoked from

HOST="hemin"                       # ~/.ssh/config alias for the 4060 Ti box
REMOTE_DIR="~/code/face-counter/"

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
)

if [[ "${1:-}" != "--with-data" ]]; then
  EXCLUDES+=(--exclude 'data/raw/')
fi

echo "Syncing to ${HOST}:${REMOTE_DIR} ..."
rsync -av "${EXCLUDES[@]}" ./ "${HOST}:${REMOTE_DIR}"

echo
echo "Done. To pick up new/changed dependencies on the GPU box, run:"
echo "  ssh ${HOST} 'cd code/face-counter && ~/.local/bin/uv sync --group dev --group analytics'"
