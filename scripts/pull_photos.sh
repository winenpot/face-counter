#!/usr/bin/env bash
# Pull ONLY the photos named in a list file (e.g. data/splits/gold_val.txt) from
# Hemin's GPU box into data/raw/images/ here. Additive: rsync without --delete,
# so photos already here are never removed or changed. The full set is ~32 GB;
# a 30-photo list is a few hundred MB.
#
# Usage:
#   scripts/pull_photos.sh data/splits/gold_val.txt            # copy
#   scripts/pull_photos.sh data/splits/gold_val.txt --dry-run  # list what would copy
set -euo pipefail
cd "$(dirname "$0")/.."

LIST="${1:?usage: $0 <list file> [--dry-run]}"
EXTRA="${2:-}"
case "${EXTRA}" in ""|--dry-run) ;; *) echo "Unknown option: ${EXTRA}" >&2; exit 2 ;; esac
[[ -f "${LIST}" ]] || { echo "No such list: ${LIST}" >&2; exit 1; }

HOST="hemin"                                   # ~/.ssh/config alias for the GPU box
REMOTE_DIR="code/face-counter/data/raw/images/"   # relative to the remote home: a quoted ~ is not expanded
LOCAL_DIR="data/raw/images/"
mkdir -p "${LOCAL_DIR}"

# --files-from takes names relative to the source dir, one per line.
rsync -av ${EXTRA:+"${EXTRA}"} --files-from="${LIST}" \
  "${HOST}:${REMOTE_DIR}" "${LOCAL_DIR}"
