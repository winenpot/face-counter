# Label Studio deployment

**This is not the shelf-detector service.** Label Studio is a separate,
third-party web app where labelers draw boxes in the browser. The inference API
(Phase 2) will be its own deployment; nothing here runs a model.

It holds company shelf photos and it is reachable over the network, so it gets
locked down before any photos go into it.

## First run

    cp .env.example .env     # fill in every value
    docker compose up -d

The compose file refuses to start if a required value is missing, rather than
booting a passwordless database. Then in the UI:

1. **Organization > Members** — remove any account you do not recognize.
2. Add labelers with **invite links** only. Self-signup is disabled
   (`LABEL_STUDIO_DISABLE_SIGNUP_WITHOUT_LINK=true`).

## Loading photos

1. Create a project, and paste `data/label_studio/labeling_config_<level>.xml`
   into **Settings > Labeling Interface > Code**.
2. **Settings > Cloud Storage > Add Source Storage > Local files**, with
   Absolute local path:

       /label-studio/files/raw/images

   This is the path *inside the container*; it is `$SHELF_DATA_DIR/raw/images`
   on the host, mounted read-only. Label Studio only serves local files that a
   storage entry covers.
3. **Import** `data/label_studio/tasks_<list>.json`. Do **not** click "Sync" —
   the tasks come from the JSON import, and the storage entry exists only to
   authorize serving the files.

If images render broken ("There was an issue loading URL from $image value"),
the server log shows `404` on `/data/local-files/`. Two causes, and both must
be right:

- **The mount.** Task URLs are `/data/local-files/?d=raw/images/<file>`, so
  `SHELF_DATA_DIR` must be the directory *containing* `raw/`, not `raw/images`
  itself. Check what the container sees:

      docker compose exec label-studio ls /label-studio/files/raw/images | head

- **The storage entry** from step 2 is missing. Without it Label Studio
  refuses to serve the file even when it is mounted.

**Local trial on a workstation:** the server's `.env` values do not fit a
laptop. Override them for one run instead of editing them, choosing a port not
already taken (`ss -ltn`):

    LS_PORT=7072 SHELF_DATA_DIR=$HOME/code/face-counter/data docker compose up -d

A later plain `docker compose up -d` recreates the container with the `.env`
values again. The labels survive, since they are in the volumes, but images break
until the mount is right. Put the local values in the local `.env` if this
machine keeps labeling.

## Labeling in batches on the server

The server never holds the whole corpus, and doesn't need to. Only photos that
humans actually label go to Label Studio: the 30-photo test set, the detector
corrections that active learning selects, and the cluster contact sheets
(`docs/LABELING_STRATEGY.md` §1). That is on the order of 500–1,000 photos,
roughly 1.5–3 GB at the corpus average of ~3 MB, against ~20 GB free on the
apps server's root disk (2026-09-22). The other ~9,000 photos are read by the
models on the GPU box and never come here.

Server layout (see `docs/vault/Home.md`):

| What | Where |
| --- | --- |
| Compose file + `.env` | `atpg:/home/data/label-studio/` |
| Photos (`SHELF_DATA_DIR`) | `atpg:/home/data/label-studio-photos/`, images under `raw/images/` |
| Projects, tasks, annotations | Docker volumes `label-studio_ls-data`, `label-studio_ls-db` |

### Rules

- **Append-only photos. Never delete a labeled batch's images.** Tasks point
  at the files, so removing them breaks every finished task: no reopening, no
  review, no second-labeler comparison.
- **Only list-selected photos go up**, never the whole of `data/raw/images/`.
  Test-set photos go up only after the test set is frozen.
- **Back up before touching the stack**, and after every labeling session.

### One batch, start to finish

1. **Pick the list** on this machine: `data/splits/label_batch_NN.txt`,
   `test_labeling.txt` once frozen, or a later active-learning pick. Check that
   it holds only file names, one per line.

2. **Check free space** on the server before copying:

       ssh atpg 'df -h / && du -sh /home/data/label-studio-photos'

3. **Copy just that batch's photos.** The photos live on the GPU box, so
   stage them here first, then push them to the server. Both steps only add
   files:

       rsync -av --files-from=data/splits/label_batch_NN.txt \
           hemin:code/face-counter/data/raw/images/ data/raw/images/
       rsync -av --files-from=data/splits/label_batch_NN.txt \
           data/raw/images/ atpg:/home/data/label-studio-photos/raw/images/

   Never add `--delete`. The folder is a bind mount, so new files are visible
   to the container at once, with no restart.

4. **Build the tasks** on this machine:

       uv run shelf-label-prep --list data/splits/label_batch_NN.txt --level brand

5. **Import in the UI.** The first time only: create the project, paste the
   label config, and add the Local files storage entry
   (`/label-studio/files/raw/images`, don't click Sync), as in "Loading
   photos" above. After that, every batch is just **Import** of
   `data/label_studio/tasks_label_batch_NN.json` into the same project. Use a
   separate project only when the label config differs (brand vs. sku, geometry
   vs. identity pass).

6. **Spot-check** that one task from the new batch shows its image. A broken
   image means the file didn't arrive: repeat step 3 for the file.

7. **Label.** Labelers need the **Show labels inside the regions** setting on
   (`docs/labeling_guide.md`).

8. **Export after each session:** project → Export → JSON, saved with a date in
   its name, e.g. `exports/<project>-2026-09-26.json`. Keep every export and
   never overwrite one. Exports belong with the dataset, not in git (they are
   derived from company photos).

9. **Dump the database** now and then, and always before upgrades:

       ssh atpg 'cd /home/data/label-studio && docker compose exec -T db sh -c '\''pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"'\''' \
           > ls-backup-$(date +%F).sql

   The dump contains every user and annotation: store it like the photos, not
   in the repo.

Only if `docker-compose.yml` changed: `rsync -av --exclude .env
deploy/label-studio/ atpg:/home/data/label-studio/`, then `docker compose up
-d` on the server. **Never `down -v`** (next section).

### Later: serving from GridFS instead of copies

Every photo already lives in MongoDB GridFS, so copying is a stopgap, not the
end state. The natural replacement is a read-only `GET /photo/<photo_id>`
endpoint on the Phase 2 FastAPI service, which has to read photos by id for
`/count` anyway. Tasks would then point at that endpoint and no copies would be
needed. Not before then: it puts every image a labeler opens onto production
MongoDB, and it is a new service to secure. Copying is cheap at a few thousand
photos.

## Stopping without losing labels

> **Never run `docker compose down -v` here.** `-v` deletes the named volumes
> `ls-data` and `ls-db`, which hold **every project, task, and annotation**.
> There is no undo and no recycle bin; the labelers' hours are gone.

| Command | Containers | Labels (volumes) |
| --- | --- | --- |
| `docker compose stop` | stopped, kept | **kept** |
| `docker compose down` | removed | **kept**: the next `up -d` finds them again |
| `docker compose down -v` | removed | **DELETED** |
| `docker volume rm label-studio_ls-db` / `docker volume prune` / `docker system prune --volumes` | n/a | **DELETED** (prune removes every volume no container uses, so after a plain `down` it takes ours too) |

The volume names come from the compose *project* name, which defaults to the
folder name: `label-studio_ls-data` and `label-studio_ls-db` when run from
`deploy/label-studio/` here, and the same on the server's
`/home/data/label-studio/`. Running compose from a different folder silently
creates a **new, empty** pair; the old labels are not lost, but they are not
where you are looking.

**Back up before anything risky** (version upgrade, migration, cleanup),
and on a schedule once real labeling starts:

1. **Export from the UI:** project → Export → JSON (the full-fidelity format;
   COCO drops notes and metadata). Keep every export, dated; never overwrite one.
2. **Dump the database**, which covers all projects and users at once:

       docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > ls-backup-$(date +%F).sql

   `-T` matters: without it, compose allocates a TTY and the dump file picks
   up carriage returns.

Photos are never at risk from any of these commands: they are mounted
read-only from `$SHELF_DATA_DIR` and live outside Docker.

## Network exposure

Docker publishes ports by inserting rules ahead of `ufw`, so **a firewall does
not protect a published port**. What restricts access here is binding to a
single interface:

- `LS_BIND_IP=127.0.0.1` — server-local only; reach it with a tunnel:

      ssh -L 8081:127.0.0.1:8081 user@server     # then http://localhost:8081

- `LS_BIND_IP=<LAN/VPN IP>` — reachable from the office network only.

**Current state of the server instance (decided 2026-09-26): public.** It
listens on `0.0.0.0:7071` and stays that way while real batches are labeled,
by owner decision. What protects it is only the application layer:
self-signup disabled, invite links only, strong passwords, no reverse proxy or
TLS. So:

- Re-check **Organization > Members** before each new batch goes up, and
  remove anyone unrecognized.
- Remove a labeler's account the day they stop labeling.
- Traffic, including logins, is plain HTTP until the Phase 4 reverse proxy.
- This is a revisitable decision, not a default. Moving to a LAN/VPN IP is a
  one-line `.env` change plus `docker compose up -d`, with no data loss.

Putting it behind a reverse proxy with TLS is Phase 4 in the roadmap.

## Migrating an existing instance

If you already run Label Studio and want to keep its projects and annotations,
do not let this stack create empty volumes alongside it.

1. **Find the current data volume**, and keep a note of the Postgres details if
   it uses one:

       docker inspect <current-container> --format '{{json .Mounts}}' | python3 -m json.tool
       docker inspect <current-container> --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -i postgre

2. **Back up before touching anything.** For a container using SQLite, copying
   the data volume is enough; for Postgres, dump it:

       docker exec <db-container> pg_dump -U <user> <db> > ls-backup-$(date +%F).sql

3. **Point this stack at the existing data**, either by declaring the current
   volume as external in `docker-compose.yml`:

       volumes:
         ls-data:
           external: true
           name: <existing-volume-name>

   or by replacing the `ls-data:` entry with a bind mount to the host path.

4. **Stop the old container first** (`docker stop <name>`), then
   `docker compose up -d`. Two Label Studio instances must not write to one
   database.

5. Check the version gap before starting: this stack pins `1.23.0`, and Label
   Studio applies irreversible schema migrations on first boot. Restoring the
   backup into the older version will not work after that.

`LS_ADMIN_EMAIL` / `LS_ADMIN_PASSWORD` create an admin **only on an empty
database** — an existing install keeps its current users, so use the password
reset flow there instead.
