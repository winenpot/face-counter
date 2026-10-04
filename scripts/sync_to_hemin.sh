#!/usr/bin/env bash
# RETIRED 2026-10-04. Hemin's ~/code/face-counter is a git checkout now; rsyncing code
# over it would bypass history and hide what changed there. Code goes through git:
#
#   here:    git push origin master
#   hemin:   git fetch origin && git merge --ff-only origin/master
#
# (If that merge refuses, hemin has commits of its own on `hemin`: merge them into
# master HERE first, see scripts/sync_from_hemin.sh.)
#
# Gitignored files git cannot carry (model weights such as models/yolo26l-sku110k.pt,
# data/label_studio/exports/*.json) go by hand, one named file at a time:
#   scp <file> hemin:code/face-counter/<same relative path>
# and check the sha256 on both ends.
echo "sync_to_hemin.sh is retired: push to git, then 'git merge --ff-only origin/master' on hemin." >&2
echo "Weights/exports that git ignores: scp the named file (see the comment in this script)." >&2
exit 1
