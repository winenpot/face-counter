#!/usr/bin/env bash
# =============================================================================
# deploy_label_studio.sh — deploy deploy/label-studio/ to the Label Studio server
# =============================================================================
#
# WHAT IT DOES
#   Copies the git-tracked files in deploy/label-studio/ (docker-compose.yml,
#   .env.example, README.md) to the server and restarts whatever changed with
#   `docker compose up -d`. It is run BY HAND, never automatically: the
#   .githooks/post-commit hook only reminds you to run it. Why no CI/CD:
#   deploy/label-studio/README.md, "Deploying changes".
#
# THE STEPS, IN ORDER (any failure stops the run before the next step)
#   1. Local checks   deploy/label-studio/ has no uncommitted changes, so the
#                     server always matches a real commit.
#   2. Server checks  SSH works, the server folder and its .env exist, and the
#                     compose file validates against the server's .env.
#   3. Show changes   A diff of every file, server vs. git. A change to an
#                     `image:` line (a version upgrade) is flagged loudly: it
#                     runs irreversible database migrations on first start.
#   4. Confirm        You answer y (or type "upgrade" for a version change).
#                     --dry-run stops before this step and changes nothing.
#   5. Back up        pg_dump of the whole Label Studio database, saved on
#                     THIS machine under backups/label-studio/ (gitignored).
#                     No backup, no deploy.
#   6. Sync           rsync of the tracked files only. Never `--delete`,
#                     never the server's .env (secrets live only there).
#   7. Apply          `docker compose up -d`: recreates only the containers
#                     whose configuration changed. Volumes are untouched.
#   8. Health check   Waits for the database to be healthy and the web app to
#                     answer /health, then checks the photo mount.
#   9. Record         Writes DEPLOYED (commit, date, who) into the server
#                     folder, so anyone can see which commit is live.
#
# WHAT IT NEVER DOES (tests/test_deploy_label_studio.py enforces this)
#   No `docker compose down`, no volume or prune commands, no `rm`, no
#   `rsync --delete`. The Docker volumes hold every annotation; deleting them
#   is unrecoverable.
#
# USAGE
#   scripts/deploy_label_studio.sh              # interactive deploy
#   scripts/deploy_label_studio.sh --dry-run    # steps 1-3 only, changes nothing
#   scripts/deploy_label_studio.sh --yes        # skip the y/N question
#                                               # (NOT the upgrade question)
#
# SETTINGS (environment variables; the defaults are the production server)
#   LS_HOST        SSH host alias from ~/.ssh/config. Default: atpg.
#                  `local` runs everything on this machine instead of over SSH;
#                  that is how the script is tested against a throwaway stack.
#   LS_REMOTE_DIR  Folder holding docker-compose.yml and .env on the host.
#                  Default: /home/data/label-studio. Its NAME sets the compose
#                  project name, and so the volume names
#                  (label-studio_ls-data, label-studio_ls-db). Don't change it
#                  for an existing install, or compose starts with empty volumes.
#   LS_BACKUP_DIR  Where database dumps are saved on this machine.
#                  Default: <repo>/backups/label-studio.
#   LS_HEALTH_TIMEOUT  Seconds to wait for the app to come up. Default: 180.
#
# EXIT CODES
#   0 deployed (or nothing to do, or dry run finished)
#   1 a check failed or you declined; the server was not changed unless the
#     message says the sync already happened
# =============================================================================

# -e: stop on any failing command. -u: an unset variable is an error, not "".
# pipefail: a failure anywhere in a pipeline fails the pipeline (matters for
# `ssh ... pg_dump | ...`: without it a failed dump could look like success).
set -euo pipefail

# Every file this script creates (backups contain password hashes) is private.
umask 077

# --- settings ------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/deploy/label-studio"
HOST="${LS_HOST:-atpg}"
REMOTE_DIR="${LS_REMOTE_DIR:-/home/data/label-studio}"
BACKUP_DIR="${LS_BACKUP_DIR:-$REPO_ROOT/backups/label-studio}"
HEALTH_TIMEOUT="${LS_HEALTH_TIMEOUT:-180}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"

DRY_RUN=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes) ASSUME_YES=1 ;;
    # Print this file's header comment (from after the title's closing ====
    # line up to the next ==== line), without the leading "# ".
    -h|--help) awk 'NR>4 && /^# =====/ {exit} NR>4 {sub(/^# ?/, ""); print}' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $arg (see --help)" >&2; exit 1 ;;
  esac
done

# --- helpers -------------------------------------------------------------------

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }          # section heading
say()  { printf '   %s\n' "$*"; }                             # normal message
warn() { printf '\033[33m!! %s\033[0m\n' "$*" >&2; }          # needs attention
die()  { printf '\033[31mxx %s\033[0m\n' "$*" >&2; exit 1; }  # stop the run

# Run a shell command on the Label Studio host: over SSH, or locally when
# LS_HOST=local. BatchMode makes SSH fail instead of prompting for a password.
on_server() {
  if [[ "$HOST" == "local" ]]; then
    bash -c "$1"
  else
    ssh -o BatchMode=yes -o ConnectTimeout=20 "$HOST" "$1"
  fi
}

# rsync destination for the host ("atpg:/dir/" or "/dir/").
dest() {
  if [[ "$HOST" == "local" ]]; then echo "$REMOTE_DIR/"; else echo "$HOST:$REMOTE_DIR/"; fi
}

# The `image:` lines of a compose file, e.g. "heartexlabs/label-studio:1.23.0".
images_of() { grep -E '^\s*image:' | sed -E 's/^\s*image:\s*//' | sort; }

# All server-side commands run from the compose folder. %q quotes the path
# safely for the remote shell, whatever characters it contains.
CD_REMOTE="cd $(printf '%q' "$REMOTE_DIR")"

# --- 1. local checks -----------------------------------------------------------

step "1/9 Local checks"
[[ -f "$SRC_DIR/docker-compose.yml" ]] || die "no $SRC_DIR/docker-compose.yml"

# Only files git tracks are deployed: a stray local .env or scratch file never
# reaches the server. Paths are relative to deploy/label-studio/.
mapfile -t FILES < <(git -C "$SRC_DIR" ls-files .)
[[ ${#FILES[@]} -gt 0 ]] || die "git tracks no files in $SRC_DIR"

# Refuse uncommitted edits: the server must always equal a commit, so that
# "what is live?" has an answer (the DEPLOYED file, step 9).
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- deploy/label-studio)" ]]; then
  git -C "$REPO_ROOT" status --short -- deploy/label-studio >&2
  die "deploy/label-studio/ has uncommitted changes. Commit them first."
fi
COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
say "deploying commit $COMMIT: ${FILES[*]}"

# --- 2. server checks ----------------------------------------------------------

step "2/9 Server checks ($HOST:$REMOTE_DIR)"
on_server "true" || die "cannot reach $HOST over SSH"
on_server "test -d $(printf '%q' "$REMOTE_DIR")" \
  || die "$REMOTE_DIR does not exist on $HOST (first install: see deploy/label-studio/README.md)"
on_server "test -f $(printf '%q' "$REMOTE_DIR/.env")" \
  || die "no .env in $REMOTE_DIR on $HOST: create it from .env.example by hand"

# Validate the NEW compose file against the server's real .env, before anything
# is copied. `-f -` reads the file from stdin; --project-directory makes compose
# pick up the .env in that folder. -q prints nothing unless there is an error.
on_server "$CD_REMOTE && docker compose --project-directory . -f - config -q" \
  < "$SRC_DIR/docker-compose.yml" \
  || die "the new docker-compose.yml does not validate against the server's .env"
say "SSH ok, folder and .env present, new compose file validates"

# --- 3. show changes -----------------------------------------------------------

step "3/9 Changes (server -> git)"
CHANGED=()
for f in "${FILES[@]}"; do
  # The server's copy is streamed straight into diff (process substitution),
  # not stored in a variable: $(...) would strip trailing newlines and make
  # every file look changed. A file missing on the server reads as empty, so
  # it shows up as all-added.
  remote_cat="cat $(printf '%q' "$REMOTE_DIR/$f") 2>/dev/null || true"
  if ! diff -q <(on_server "$remote_cat") "$SRC_DIR/$f" >/dev/null; then
    CHANGED+=("$f")
    diff -u --label "server/$f" --label "git/$f" \
      <(on_server "$remote_cat") "$SRC_DIR/$f" | sed 's/^/   /' || true
  fi
done

# A version change is the one risky kind of deploy: Label Studio and
# pgautoupgrade both migrate the database on first start, and there is no
# downgrade. Compare the image lines explicitly so it can't hide in a big diff.
OLD_IMAGES="$(on_server "cat $(printf '%q' "$REMOTE_DIR/docker-compose.yml")" | images_of)"
NEW_IMAGES="$(images_of < "$SRC_DIR/docker-compose.yml")"
UPGRADE=0
if [[ "$OLD_IMAGES" != "$NEW_IMAGES" ]]; then
  UPGRADE=1
  warn "IMAGE VERSION CHANGE. The database is migrated on first start and cannot be downgraded."
  warn "  server: $(echo "$OLD_IMAGES" | tr '\n' ' ')"
  warn "  git:    $(echo "$NEW_IMAGES" | tr '\n' ' ')"
fi

if [[ ${#CHANGED[@]} -eq 0 ]]; then
  say "no differences: the server already matches $COMMIT"
else
  say "changed: ${CHANGED[*]}"
fi

if [[ $DRY_RUN -eq 1 ]]; then
  step "Dry run: stopping here. Nothing was backed up, copied or restarted."
  exit 0
fi

# --- 4. confirm ----------------------------------------------------------------

step "4/9 Confirm"
if [[ $UPGRADE -eq 1 ]]; then
  # Always asked, even with --yes: an upgrade must be a deliberate human act.
  read -r -p "   Type 'upgrade' to migrate the database to the new versions: " answer
  [[ "$answer" == "upgrade" ]] || die "not confirmed; nothing changed"
elif [[ $ASSUME_YES -eq 0 ]]; then
  read -r -p "   Back up, sync and restart Label Studio on $HOST? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || die "not confirmed; nothing changed"
fi

# --- 5. back up ----------------------------------------------------------------

step "5/9 Database backup"
mkdir -p "$BACKUP_DIR"
BACKUP="$BACKUP_DIR/ls-$STAMP-before-$COMMIT.sql"
# -T: no TTY, otherwise the dump picks up carriage returns. The variables are
# expanded INSIDE the db container (single quotes), where they are set from .env.
on_server "$CD_REMOTE && docker compose exec -T db sh -c 'pg_dump -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\"'" \
  > "$BACKUP" || die "pg_dump failed; nothing changed on the server"
# pg_dump writes this line last; its absence means a truncated dump.
grep -q "PostgreSQL database dump complete" "$BACKUP" \
  || die "backup $BACKUP looks incomplete; nothing changed on the server"
say "saved $BACKUP ($(du -h "$BACKUP" | cut -f1))"

# --- 6. sync -------------------------------------------------------------------

step "6/9 Sync files"
# --files-from: exactly the git-tracked files. --exclude=.env: belt and braces,
# the server's .env holds the passwords and is never overwritten. No --delete:
# files on the server that git doesn't know (DEPLOYED, .env) are left alone.
rsync -av --exclude=.env --files-from=<(printf '%s\n' "${FILES[@]}") "$SRC_DIR/" "$(dest)" \
  | sed 's/^/   /'

# --- 7. apply ------------------------------------------------------------------

step "7/9 Apply (docker compose up -d)"
# Recreates only the containers whose configuration changed; unchanged ones keep
# running. The named volumes (every project, task and annotation) are reused.
on_server "$CD_REMOTE && docker compose up -d" 2>&1 | sed 's/^/   /'

# --- 8. health check -----------------------------------------------------------

step "8/9 Health check (up to ${HEALTH_TIMEOUT}s)"
# Where the app listens, as published by Docker, e.g. "0.0.0.0:7071". 0.0.0.0
# means every interface, so ask it on 127.0.0.1 from the server itself.
ADDR="$(on_server "$CD_REMOTE && docker compose port label-studio 8080" | tail -1)"
ADDR="${ADDR/0.0.0.0/127.0.0.1}"
[[ -n "$ADDR" ]] || die "label-studio publishes no port; check 'docker compose ps' on $HOST"

deadline=$(( SECONDS + HEALTH_TIMEOUT ))
until on_server "curl -fsS -o /dev/null http://$ADDR/health" 2>/dev/null; do
  (( SECONDS < deadline )) || die "Label Studio did not answer http://$ADDR/health in ${HEALTH_TIMEOUT}s. Logs: ssh $HOST 'cd $REMOTE_DIR && docker compose logs --tail 100 label-studio'. Backup: $BACKUP"
  sleep 5
done
say "web app answers /health on $ADDR"

DB_STATE="$(on_server "$CD_REMOTE && docker inspect --format '{{.State.Health.Status}}' \$(docker compose ps -q db)")"
[[ "$DB_STATE" == "healthy" ]] || die "database container is '$DB_STATE', not healthy. Backup: $BACKUP"
say "database healthy"

# The photos must still be mounted where the tasks expect them.
on_server "$CD_REMOTE && docker compose exec -T label-studio test -d /label-studio/files" \
  || die "photo folder /label-studio/files is not mounted in the container"
PHOTOS="$(on_server "$CD_REMOTE && docker compose exec -T label-studio sh -c 'ls /label-studio/files/raw/images 2>/dev/null | wc -l'")"
say "photo mount present (${PHOTOS// /} files under raw/images)"

# --- 9. record -----------------------------------------------------------------

step "9/9 Record"
# One small file on the server answers "which commit is live, and since when".
printf 'commit %s\ndeployed %s\nby %s@%s\nbackup %s\n' \
  "$(git -C "$REPO_ROOT" rev-parse HEAD)" "$(date -Is)" "$(id -un)" "$(hostname)" "$BACKUP" \
  | on_server "cat > $(printf '%q' "$REMOTE_DIR/DEPLOYED")"
say "wrote $REMOTE_DIR/DEPLOYED"

step "Done: $HOST runs deploy/label-studio at $COMMIT"
