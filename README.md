# face-counter (Shelf Detector)

Counts visible product faces on retail shelf photographs and computes share of
shelf. A field rep photographs a shelf; the service returns counts per
`BRAND_CATEGORY_SKU`, grouped by brand, plus share of shelf per category.

Two stages, so that adding a product does not mean retraining a detector:

    shelf photo -> detector (finds every face)    -> crops
                -> identifier (names each crop)   -> counts + share of shelf

A **face** is the frontmost unit of a lane (a line of units going back into the
shelf), one per lane. Units behind it are not counted, even when clearly
visible: the BI analyst reads faces. This is a standing issue, see
`docs/ISSUE_FACES_NOT_OBJECTS.md`.

See `docs/ROADMAP.md` for the full plan, `docs/PROPOSAL.md` for the original
proposal, and `LOGS.md` for a human-readable timeline of what's happened.

## Status: Phase 1 pilot under way, a detection-only demo API is running

The data pipeline works end to end: export photos out of MongoDB, fix a
leakage-free test set, and prepare Label Studio for labelers. Since
2026-10-10, a **detection-only demo API** also runs (see [Serving](#serving-demo-api)).
It counts products and draws boxes; it does not yet name brands or split
cans from glass by default.

| Phase | What | State |
| --- | --- | --- |
| 0 | Export, manifest, fixed test set, labeling setup | **done** 2026-09-27 — findings in `docs/PHASE0_REMAINING.md` |
| 1 | SKU-110K detector, reference gallery, embedding matcher | **under way** as a two-brand drinks pilot — see `docs/PILOT.md` |
| 2 | FastAPI `/count`, `/overlay`, `/health` in Docker | **demo running** (detection only, localhost on the apps server); production deploy and async intake not started — `docs/SERVING_STRATEGY.md` |
| 3 | Pre-labeling loop, fine-tuning, MLflow, DVC remote | not started |

The Phase 0 tooling below has run against production: 9,704 photos exported
(on the GPU box), a manifest, store-level splits, and a frozen 30-photo test
set (`data/splits/test_labeling.txt`, tracked in git). `docs/PHASE0_REMAINING.md`
records the real schema and what the survey found. Start from `docs/PILOT.md`.

## Setup

Python 3.14, managed with [uv](https://docs.astral.sh/uv/).

    uv sync --group dev          # runtime + test dependencies
    git config --local core.hooksPath .githooks   # commit-msg check + post-commit deploy reminder
    uv run pytest                # end-to-end checks on a fake MongoDB, no server needed

Copy `.env.example` to `.env` and set `MONGO_URI`. Use a **read-only** Mongo
user — the export only ever reads:

```js
use admin
db.createUser({ user: "shelf_reader", pwd: "<long random>",
                roles: [{ role: "read", db: "<your app db>" }] })
```

## Phase 0 workflow

Edit `configs/export.yaml` first (database, collection, field paths); the export
refuses to run while it still holds `CHANGE_ME` placeholders.

    uv run shelf-export --limit 20    # small test export, then check data/raw/manifest.csv
    uv run shelf-export               # full export; resumable, run after hours

    uv run shelf-splits               # -> data/splits/

    uv run shelf-label-prep --list data/splits/test_labeling.txt  --level sku
    uv run shelf-label-prep --list data/splits/label_batch_01.txt --level brand

`configs/classes.csv` drives the labeling config; `shelf-label-prep` refuses
to run meaningfully without a real one. Import products from a sales/export
invoice (never committed -- see `.gitignore`):

    uv run python scripts/build_classes.py <path-to-invoice.xlsm>

The import **merges**: rows marked `source=manual` (competitors,
`out_of_scope`, products no invoice lists) are never touched, so add those by
hand. Which pack types count toward which share-of-shelf category is
`configs/reporting.yaml`, owned by the business; labels never name a category,
so editing it never invalidates an annotation. `uv run pytest` checks the two
files stay consistent.

**Empty `store_id` values in the manifest mean the field mapping is wrong.**
Fix it before splitting: without a store, photos of the same shelf can land on
both sides of the train/test line and the accuracy numbers will lie. The split
script warns about this too.

### Finding your field paths

Open one metadata document and copy the paths into `configs/export.yaml`, using
dot notation for nested fields (`store.id`):

```js
db.<collection>.findOne({}, {_id: 0})
```

If the metadata lives inside `fs.files.metadata` rather than its own
collection, set `source: gridfs` and use paths like `metadata.store_id`.

### Disk

A full export of ~20k phone photos is roughly **60–100 GB**. Check `df -h`
first; if space is tight, point `export.out_dir` at an absolute path on another
disk. `throttle_seconds` and the batched cursor keep load off MongoDB, but the
full run still belongs outside working hours.

## Serving (demo API)

A FastAPI service in `src/face_counter/serving/`. It runs the detector through
**ONNX Runtime on CPU only**; `ultralytics` and torch are never imported in the
served process. Install only what it needs:

    uv sync --group serve                    # + base deps; never needs `analytics`
    uv run shelf-serve                       # 127.0.0.1:8000, docs at /docs

It needs `models/yolo26l-sku110k.onnx`, which is gitignored. Export it once,
on a machine with the `analytics` group (hemin), then copy it with a sha256
check:

    uv run python scripts/export_onnx.py models/yolo26l-sku110k.pt models/yolo26l-sku110k.onnx --imgsz 1280

| Endpoint | Auth | Returns |
| --- | --- | --- |
| `GET /health` | none | status, detector, pack classifier (`null` when off), version |
| `POST /count` (multipart `file`, optional `?debug=true`) | `X-API-Key` | `units_detected`, `categories`, boxes, timings, caveats |
| `POST /overlay` (multipart `file`) | `X-API-Key` | JPEG with one box per detected unit |

| Env var | Default | Meaning |
| --- | --- | --- |
| `FACE_COUNTER_API_KEY` | placeholder | **Set a real secret before any non-local use**; startup logs a warning while the placeholder is in effect |
| `FACE_COUNTER_CLASSIFY` | `0` | `1` turns on the CLIP canned/glass stage: ~15 s and ~2 GB per process on CPU, see `docs/PACK_TYPE_ALTERNATIVES.md` |
| `FACE_COUNTER_ORT_THREADS` | `0` (onnxruntime default) | Cap intra-op threads to the container's CPU allowance |
| `FACE_COUNTER_CONF` / `FACE_COUNTER_IMGSZ` | `0.25` / `1280` | Detector confidence and input size |
| `FACE_COUNTER_HOST` / `FACE_COUNTER_PORT` | `127.0.0.1` / `8000` | Bind address |
| `FACE_COUNTER_MATCH_THRESHOLD`, `FACE_COUNTER_DEVICE`, `FACE_COUNTER_CLASSES`, `FACE_COUNTER_REPORTING`, `FACE_COUNTER_SCOPE`, `FACE_COUNTER_BAKEOFF_CONFIG`, `FACE_COUNTER_DETECTOR_MODEL` | see `serving/pipeline.py` | Debug path and config locations |

`debug=true` adds the experimental brand matcher and share-of-shelf, heavily
caveated (identity accuracy 65.3%). It loads DINOv2 and CLIP even when
`FACE_COUNTER_CLASSIFY=0`.

**Docker image:** `deploy/serve.Dockerfile` builds a detection-only image
(no torch inside). The model is mounted read-only, not baked in. The running
demo on the apps server, with its exact `docker run` flags, measurements and
removal command, is documented in the project vault
(`docs/vault/DevOps/Demo API on the apps server.md`). Blockers before anyone
else can reach it are tracked in issue #6. Why this is a demo shape and not
the production one (async intake, pull workers, queues):
`docs/SERVING_STRATEGY.md`.

## Labeling (Label Studio)

Label Studio is a **separate web app** used by labelers — not part of this
service. Its deployment lives in `deploy/label-studio/` and is documented in
`deploy/label-studio/README.md`. This repo is the single source of truth for
it. Two commands keep the server in line with git, each explained step by step
in its own file header:

    scripts/deploy_label_studio.sh     # the APP: compose file, versions, settings
    uv run shelf-ls-setup --title <project> --tasks <tasks.json> --config <config.xml>   # a PROJECT

`deploy_label_studio.sh` backs the database up, shows the changes, asks, syncs,
restarts and health-checks; `.githooks/post-commit` reminds you to run it when a
commit touches `deploy/label-studio/`. `shelf-ls-setup` creates or updates the
labeling project over Label Studio's API. Never hand-edit the live config
without putting the change into git first. The demo inference API does not
follow this pattern yet: it was started by hand from `deploy/serve.Dockerfile`.
A compose file and a deploy script in the same shape are still to do (#6).

Label the **test set first** (`test_labeling.txt`, 30 photos); it must stay
fixed. Splits are a stable hash of `store_id`, so re-running after new exports
never moves a store between train and test.

Labelers follow `docs/labeling-guide/README.md`. `docs/requests.md` holds the messages
to send for the class list and packshots.

## Commit messages

Every commit subject must carry one or more gitmoji, then a Conventional
Commit:

```text
<gitmoji> [<gitmoji> ...] <type>[(scope)][!]: <description>

✨ feat(export): add HEIC decoding
🐛 🔧 fix(splits)!: change the store hash salt
📝 docs(vault): record the Label Studio migration
```

Approved gitmojis (mirrors gitmoji.dev's common subset, extend in
`.githooks/commit-msg`'s `GITMOJIS` list if you need another one):

| | | | | |
|---|---|---|---|---|
| ✨ new feature | 🐛 bug fix | ♻️ refactor | 📝 docs | ✅ tests |
| 👷 CI | 🔥 remove code/files | 🎨 style/format | ⚡ performance | 🔒 security |
| 🚧 WIP | ⬆️ deps up | 🔧 config | ⏪ revert | 🎉 milestone |
| 🚀 deploy | 💚 fix CI | 📦 build/deps | 🧪 experiments | 🛠️ tooling |
| 💄 UI/style | 🌐 i18n | 🗑️ deprecate | 🩹 minor fix | 🔐 secrets |

Allowed lowercase types: `feat`, `fix`, `refactor`, `docs`, `test`, `ci`,
`chore`, `style`, `build`, `perf`, `security`, `wip`, `deps`, `config`,
`revert`. The optional scope starts with a lowercase letter or digit and may
also contain `.`, `_`, `/`, and `-`. A description is required; the body is
unrestricted in content but capped in length (below). Gitmoji is required
going forward — the project's earlier history (before 2026-09-24) used
plain Conventional Commits without it, is not revalidated or rewritten.

**Length caps, against AI-generated "slop" messages** (a multi-paragraph
essay with a dozen bullet points for a one-line change): subject max 72
chars (git's own convention — fits one line in `git log --oneline`), body
max 20 non-blank lines, each body line max 100 chars. A commit message is a
pointer for a human skimming `git log`, not a design doc — put real detail
in code comments, `docs/`, or the PR description instead. The rare commit
that genuinely needs more: `git commit --no-verify` bypasses the hook
deliberately; don't loosen the caps for everyone to fit one long commit.

The versioned `.githooks/commit-msg` hook rejects invalid subjects without
changing them. It requires `python3` on PATH, no third-party packages. Enable
it once per clone with the setup command above. If you already use a custom
`core.hooksPath`, integrate this validator into your existing hook chain
instead of replacing that setting. Git does not install hooks automatically
on clone. Existing history (including the project's earlier gitmoji-prefixed
commits) is not revalidated or rewritten.

## Layout

    configs/        export.yaml (EDIT FIRST), classes.csv (class list), reporting.yaml (share-of-shelf categories)
    src/face_counter/
      utils/config.py               paths, config loading, Mongo connection
      training/export_photos.py     GridFS -> data/raw/images + manifest.csv
      label_studio/make_splits.py            train/val/test by store + photo lists to label first
      label_studio/prepare_label_studio.py   labeling config XML + task JSON (+ pre-drawn boxes, staged photos)
      label_studio/setup_project.py          shelf-ls-setup: create/update the Label Studio project over the API
      serving/                      demo inference API: ONNX detector, pipeline, FastAPI app (shelf-serve)
    deploy/label-studio/    Label Studio (third-party labeling app) deployment
    deploy/serve.Dockerfile detection-only serving image (no torch)
    docs/           ROADMAP, PROPOSAL, PILOT, PILOT_LABELING, DATASET_PREPARATION, labeling-guide/ (guide + examples), requests
    scripts/        deploy_label_studio.sh (deploy the app); build_classes.py; scan_images.py; sync_from_hemin.sh (results back; code travels by git, branch `hemin`), pull_photos.sh, contact_sheet.py
    .githooks/      commit-msg (message format), post-commit (deploy reminder)
    tests/          end-to-end tests on a fake MongoDB
    investigations/ one-off probes kept for the record; nothing depends on them
    data/           git-ignored; DVC owns dataset versioning

## Data

`data/raw/` is git-ignored and versioned with DVC (`.dvc/`). No DVC remote is
configured yet, so data is local-only yet.
