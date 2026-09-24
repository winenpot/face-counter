# face-counter (Shelf Detector)

Counts visible product faces on retail shelf photographs and computes share of
shelf. A field rep photographs a shelf; the service returns counts per
`BRAND_CATEGORY_SKU`, grouped by brand, plus share of shelf per category.

Two stages, so that adding a product does not mean retraining a detector:

    shelf photo -> detector (finds every product) -> crops
                -> identifier (names each crop)   -> counts + share of shelf

See `docs/ROADMAP.md` for the full plan, `docs/PROPOSAL.md` for the original
proposal, and `LOGS.md` for a human-readable timeline of what's happened.

## Status: Phase 0 (foundations)

The inference API does not exist yet. What works today is the data pipeline:
export photos out of MongoDB, fix a leakage-free test set, and prepare Label
Studio for labelers.

| Phase | What | State |
| --- | --- | --- |
| 0 | Export, manifest, fixed test set, labeling setup | **in progress** — see `docs/PHASE0_REMAINING.md` |
| 1 | SKU-110K detector, reference gallery, embedding matcher | not started |
| 2 | FastAPI `/count`, `/overlay`, `/health` in Docker | not started — this repo will be its launchpad too, same as Label Studio: `deploy/serving/` (planned), compose-driven, `src/face_counter/serving/` already reserved |
| 3 | Pre-labeling loop, fine-tuning, MLflow, DVC remote | not started |

The Phase 0 tooling below runs, but it has not yet been pointed at the real
database: `configs/export.yaml` still describes a schema the production data
does not use, so no manifest and no fixed test set exist yet.
`docs/PHASE0_REMAINING.md` has the actual schema and what is left.

## Setup

Python 3.14, managed with [uv](https://docs.astral.sh/uv/).

    uv sync --group dev          # runtime + test dependencies
    git config --local core.hooksPath .githooks   # enable the commit-msg hook
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
to run meaningfully without a real one. Build it from a sales/export invoice
(never committed -- see `.gitignore`) rather than hand-editing:

    uv run python scripts/build_classes.py <path-to-invoice.xlsm>

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

## Labeling (Label Studio)

Label Studio is a **separate web app** used by labelers — not part of this
service. Its deployment lives in `deploy/label-studio/` and is documented in
`deploy/label-studio/README.md`. This repo is the single source of truth for
it: edit the compose file here, `rsync` to the server, `docker compose up -d`
there — never hand-edit the live config without syncing the change back into
git first. The same pattern is planned for the Phase 2 FastAPI inference
service once it exists (`deploy/serving/`, not built yet).

Label the **test set first** (`test_labeling.txt`, 30 photos); it must stay
fixed. Splits are a stable hash of `store_id`, so re-running after new exports
never moves a store between train and test.

Labelers follow `docs/labeling_guide.md`. `docs/requests.md` holds the messages
to send for the class list and packshots.

## Commit messages

Every commit subject must be a Conventional Commit:

```text
<type>[(scope)][!]: <description>

feat(export): add HEIC decoding
fix(splits)!: change the store hash salt
docs(vault): record the Label Studio migration
```

Allowed lowercase types: `feat`, `fix`, `refactor`, `docs`, `test`, `ci`,
`chore`, `style`, `build`, `perf`, `security`, `wip`, `deps`, `config`,
`revert`. The optional scope starts with a lowercase letter or digit and may
also contain `.`, `_`, `/`, and `-`. A description is required; the body is
unrestricted in content but capped in length (below). No gitmoji prefix is
required (unlike the sibling `merchant` repo's hook this one is adapted
from) — this repo's own history is plain Conventional Commits, so the hook
enforces what's already the convention here.

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

    configs/        export.yaml (EDIT FIRST), classes.csv (class list template)
    src/face_counter/
      utils/config.py               paths, config loading, Mongo connection
      training/export_photos.py     GridFS -> data/raw/images + manifest.csv
      label_studio/make_splits.py            train/val/test by store + photo lists to label first
      label_studio/prepare_label_studio.py   labeling config XML + task JSON
      serving/                      placeholder for the future inference API (Phase 2)
    deploy/label-studio/    Label Studio (third-party labeling app) deployment
    docs/           ROADMAP, PROPOSAL, DATASET_PREPARATION, labeling_guide, requests
    scripts/        scan_images.py, a standalone image audit helper; sync_to_hemin.sh, sync_from_hemin.sh
    tests/          end-to-end tests on a fake MongoDB
    data/           git-ignored; DVC owns dataset versioning

## Data

`data/raw/` is git-ignored and versioned with DVC (`.dvc/`). No DVC remote is
configured yet, so data is local-only yet.
