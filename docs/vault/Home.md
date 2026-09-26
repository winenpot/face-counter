# face-counter — Vault Home

Project-specific architecture, operations, and infrastructure knowledge for
`face-counter`. Linked from the global Hermes vault's Projects index.

## Infrastructure

Two production boxes, **identical specs**: 8 vCPU (Intel Xeon E5-2680 v4 @
2.40GHz, VMware guest), 15GB RAM, 97GB root disk (`/dev/sda2`).

### apps server

SSH access available. Runs ~30 Docker containers, including:
- `label-studio` + `label-studio-db-1` — the labeling web app (see
  `deploy/label-studio/README.md` in this repo; that compose file is a
  reference copy, not what's deployed — production was set up by hand from
  upstream's own compose file, confirmed legitimate 2026-09-22)
- `atpg_flask_app`, `atpgchart`, `atpg-dashboard`, and many unrelated
  internal tools (trade, HR, meeting, tagsystem, etc.)
- `database-mongodb-primary` — production MongoDB (the `atpg` database this
  project reads from; see `docs/PHASE0_REMAINING.md`)

**Disk status (2026-09-22):** root (`/dev/sda2`) at 79% full, only 20GB free.
`docker system df` showed 19.09GB reclaimable in images (85% of 22.29GB) and
13.21GB reclaimable in build cache — over 32GB of dead weight. MongoDB's
actual data volume is on a **separate disk**, not this 79%-full root, so the
`atpg` corpus's growth (~42GB and rising) is not directly constrained by this,
but Label Studio and everything else on the box share this same root.

**RAM status (2026-09-22):** 15Gi total, 11Gi available, no pressure.
`label-studio-db-1` was using 25.57MiB of its 1GiB limit (2.5%) — Postgres
memory is not currently a risk on this box.

### db server

Identical specs to apps server. **No current SSH access** (as of 2026-09-22).
MongoDB's data volume lives here, on a disk separate from apps server's root.

## Label Studio deployment

**This repo is now the actual launchpad for Label Studio, confirmed live
2026-09-24.** The old hand-deployed instance at `/home/data/label-studio/`
(independent compose file, `:latest` image, exposed on `0.0.0.0:7071`, no
photo mount, no Postgres tuning) was torn down entirely — `docker compose
down -v`, all containers/volumes removed. It held only a demo project + 2
demo users, explicitly disposable, so no backup/migration was needed.

`/home/data/label-studio/` was replaced with an rsync of this repo's
`deploy/label-studio/` (`docker-compose.yml` + `README.md`, `.env`
excluded from the sync and hand-written on the server). Now running:
image pinned to `heartexlabs/label-studio:1.23.0` (was `:latest`), same
port `7071` on `0.0.0.0` (kept intentionally open — demo instance for
supervisors, no real data, user's explicit call; **re-confirmed 2026-09-26 to
stay public while real labeling batches are loaded**, see
`deploy/label-studio/README.md` "Network exposure"), Postgres tuning from
the compose file applied, `LABEL_STUDIO_DISABLE_SIGNUP_WITHOUT_LINK=true`
confirmed active. Admin login `admin@atpg.local`, password in
`/home/data/label-studio/.env` on the server (chmod 600), never passed
through chat.

**Known gap:** `SHELF_DATA_DIR` points at `/home/data/label-studio-photos/`,
created empty — no exported photos exist on the apps server (the export
runs on Hemin's GPU box, see below). Manual image upload / demo projects
work fine; the `prepare_label_studio.py` local-files task-import workflow
will show broken images until photos are synced to this path too. Photos go
there **per labeling batch, append-only**, never the whole corpus; the
procedure is `deploy/label-studio/README.md`, "Labeling in batches on the
server".

**Deploy workflow going forward:** edit `deploy/label-studio/docker-compose.yml`
in git -> `rsync -av --exclude .env deploy/label-studio/ atpg:/home/data/label-studio/`
-> `ssh atpg 'cd /home/data/label-studio && docker compose up -d'`. Volumes
(`label-studio_ls-data`, `label-studio_ls-db`) persist across this; editing
compose text does not touch them. `.env` on the server is the one thing
never overwritten by the sync — hand-edit it there directly if it needs to
change.

**Never `docker compose down -v` (or `docker volume rm` / `prune --volumes`)
on the server's Label Studio.** The 2026-09-24 teardown of the old instance
used `down -v` deliberately, because it held only demo data. On the current
instance the same command deletes every real annotation, with no undo. `down`
or `stop` keeps the volumes. Take a JSON export plus `pg_dump` before any
upgrade or cleanup (`deploy/label-studio/README.md`, "Stopping without losing
labels").

## Future: FastAPI inference service (Phase 2)

This repo will also be the launchpad for the model-inference FastAPI app
once Phase 2 starts (`/count`, `/overlay`, `/health` per `docs/ROADMAP.md`).
`src/face_counter/serving/` already exists as the placeholder package for
it (see the 2026-09-24 role-based restructuring: `training/`,
`label_studio/`, `utils/`, `serving/`). Expect a same-shaped deploy/ entry
(e.g. `deploy/serving/`) with its own docker-compose and README when that
phase starts, following the same pattern established for Label Studio:
this repo's compose file as the single source of truth, deployed via
rsync + `docker compose up -d`, never hand-edited live without syncing
the change back into git first.
