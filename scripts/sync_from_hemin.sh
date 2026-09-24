#!/usr/bin/env bash
# Pull results from Hemin's GPU training box (~/code/face-counter) back here,
# one-way. This is for RESULTS only (trained weights, run artifacts) -- never
# code. Code changes on Hemin's side belong in git (commit + push there,
# pull here); rsync has no merge logic, so pulling his code over ours would
# silently clobber whatever's uncommitted on this side with no diff and no
# way back. If his tree isn't clean, stop and sort that out with git first,
# don't rsync around it.
#
# Split into role-owned folders (src/face_counter/training, label_studio,
# serving, utils) so this exclude list can leave out what belongs to his
# machine only: this side never needs training/'s bulk data, just outputs.
#
# Usage:
#   scripts/sync_from_hemin.sh              # pull runs/ (trained weights) only
#   scripts/sync_from_hemin.sh --with-data  # also pull his data/raw/ export
#                                            # (large; only when you actually
#                                            # need his photos on this machine)
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root, regardless of where this is invoked from

HOST="hemin"                       # ~/.ssh/config alias for the 4060 Ti box
REMOTE_DIR="~/code/face-counter/"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Local tree is dirty. Commit or stash before pulling -- an incoming" >&2
  echo "runs/ sync could still collide with local uncommitted state." >&2
  exit 1
fi
if ! ssh "${HOST}" "cd code/face-counter && [[ -z \"\$(git status --porcelain)\" ]]"; then
  echo "${HOST}'s tree is dirty. Pull results only after Hemin commits --" >&2
  echo "code should never travel by rsync, only by git." >&2
  exit 1
fi

INCLUDES_ONLY=(
  # Only pull training results, never code (code -> git) and never his
  # working data unless explicitly asked for with --with-data.
  --include 'runs/'
  --include 'runs/**'
  --exclude '.venv/'
  --exclude '.git/'
  --exclude '__pycache__/'
  --exclude '*.egg-info/'
  --exclude '.env'
  --exclude 'src/'
  --exclude 'scripts/'
  --exclude 'tests/'
  --exclude 'configs/'
  --exclude 'data/splits/'
  --exclude 'data/label_studio/'
)

if [[ "${1:-}" != "--with-data" ]]; then
  INCLUDES_ONLY+=(--exclude 'data/raw/')
else
  INCLUDES_ONLY+=(--include 'data/raw/' --include 'data/raw/**')
fi
INCLUDES_ONLY+=(--exclude '*')  # default-deny anything not explicitly included above

echo "Pulling from ${HOST}:${REMOTE_DIR} ..."
rsync -av "${INCLUDES_ONLY[@]}" "${HOST}:${REMOTE_DIR}" ./

echo
echo "Done."
