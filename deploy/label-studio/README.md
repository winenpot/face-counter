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

If images render broken, the mount and the document root disagree: task URLs
are `/data/local-files/?d=raw/images/<file>`, so `SHELF_DATA_DIR` must be the
directory *containing* `raw/`, not `raw/images` itself.

## Network exposure

Docker publishes ports by inserting rules ahead of `ufw`, so **a firewall does
not protect a published port**. What restricts access here is binding to a
single interface:

- `LS_BIND_IP=127.0.0.1` — server-local only; reach it with a tunnel:

      ssh -L 8081:127.0.0.1:8081 user@server     # then http://localhost:8081

- `LS_BIND_IP=<LAN/VPN IP>` — reachable from the office network only.

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
