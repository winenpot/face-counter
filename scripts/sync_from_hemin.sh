#!/usr/bin/env bash
# Pull results from Hemin's GPU training box (~/code/face-counter) back here,
# one-way. This is for RESULTS only (trained weights, run artifacts) -- never
# code. Code changes on Hemin's side belong in git: he commits on the `hemin`
# branch and pushes it, we merge it into master HERE (where the tests run and
# conflicts get resolved), push master, and he fast-forwards. rsync has no
# merge logic, so it never carries code. If his box has edits or commits git
# doesn't have, this script stops (see the checks below).
#
# Split into role-owned folders (src/face_counter/training, label_studio,
# serving, utils) so this exclude list can leave out what belongs to his
# machine only: this side never needs training/'s bulk data, just outputs.
#
# Usage:
#   scripts/sync_from_hemin.sh                  # runs/ (trained weights) only
#   scripts/sync_from_hemin.sh --with-manifest  # also pull data/raw/manifest.csv
#                                                # (~2 MB; this is what splits need)
#   scripts/sync_from_hemin.sh --with-data      # also pull his whole data/raw/
#                                                # export (~32 GB; only when you
#                                                # actually need his photos here)
#
# --with-manifest is the common case: make_splits.py reads manifest.csv and
# writes lists of paths, it never opens an image, so this side needs the CSV
# and not the ~32 GB of photos behind it. Note the paths inside the manifest
# refer to Hemin's disk -- the split files inherit that, which is intended
# (labeling reads the photos from there, not from here).
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root, regardless of where this is invoked from

MODE="${1:-}"
case "${MODE}" in
  ""|--with-manifest|--with-data) ;;
  *)
    echo "Unknown option: ${MODE}" >&2
    echo "Usage: $0 [--with-manifest | --with-data]" >&2
    exit 2
    ;;
esac

HOST="hemin"                       # ~/.ssh/config alias for the 4060 Ti box
REMOTE_DIR="~/code/face-counter/"

# No local clean-tree check: this script only writes runs/ and data/raw/, both
# gitignored, so nothing tracked here can be overwritten.
#
# Hemin's side must have nothing git doesn't know about: no edited tracked file and
# no commit that is on no origin branch (the `hemin` branch counts). Otherwise the
# results were produced by code that exists nowhere else; push it first (hemin
# branch), merge it into master here, then pull results.
if ! ssh "${HOST}" 'cd code/face-counter && git fetch -q origin'; then
  echo "Could not fetch origin on ${HOST}; cannot verify its code is in git." >&2
  exit 1
fi
if [[ -n "$(ssh "${HOST}" 'cd code/face-counter && git status --porcelain')" ]]; then
  echo "${HOST} has uncommitted changes to tracked files. Commit them on its" >&2
  echo "'hemin' branch and push, or revert them. Code travels by git only." >&2
  exit 1
fi
UNPUSHED="$(ssh "${HOST}" 'cd code/face-counter && git rev-list --count HEAD --not --remotes=origin')"
if [[ "${UNPUSHED}" != "0" ]]; then
  echo "${HOST} has ${UNPUSHED} commit(s) that are on no origin branch. Push them" >&2
  echo "(git push on hemin, to origin/hemin) before pulling results from them." >&2
  exit 1
fi
echo "${HOST}: $(ssh "${HOST}" 'cd code/face-counter && git branch --show-current'), clean," \
     "$(ssh "${HOST}" 'cd code/face-counter && git rev-list --count HEAD..origin/master') commit(s) behind origin/master."

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

case "${MODE}" in
  --with-data)
    # Everything under data/raw/: the ~32 GB of photos plus the manifest.
    # 'data/' itself must be included or the trailing --exclude '*' stops
    # rsync descending into it and nothing transfers at all.
    INCLUDES_ONLY+=(--include 'data/' --include 'data/raw/' --include 'data/raw/**')
    ;;
  --with-manifest)
    # Just the inventory CSV. Include the parent dirs so rsync can descend,
    # but exclude everything else under data/raw/ so no image comes across.
    INCLUDES_ONLY+=(
      --include 'data/'
      --include 'data/raw/'
      --include 'data/raw/manifest.csv'
      --exclude 'data/raw/**'
    )
    ;;
  "")
    INCLUDES_ONLY+=(--exclude 'data/raw/')
    ;;
esac
INCLUDES_ONLY+=(--exclude '*')  # default-deny anything not explicitly included above

echo "Pulling from ${HOST}:${REMOTE_DIR} ..."
rsync -av "${INCLUDES_ONLY[@]}" "${HOST}:${REMOTE_DIR}" ./

echo
echo "Done."
