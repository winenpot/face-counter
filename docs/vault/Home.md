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

`deploy/label-studio/docker-compose.yml` in this repo is a **hardened
reference copy**, downloaded from upstream and edited here (pinned tag,
`LS_BIND_IP`, photo mount, Postgres tuning). It is **not** connected to or
overwriting the production instance on apps server — that instance was
deployed independently, by hand, from its own copy of upstream's compose
file, and is running fine with members addable. Treat this repo's copy as
documentation of what "secured" should look like and a template for a
future redeploy, not as the live config.
