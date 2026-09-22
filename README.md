# face-counter (Shelf Detector)

Counts visible product faces on retail shelf photographs and computes share of
shelf. A field rep photographs a shelf; the service returns counts per
`BRAND_CATEGORY_SKU`, grouped by brand, plus share of shelf per category.

Two stages, so that adding a product does not mean retraining a detector:

    shelf photo -> detector (finds every product) -> crops
                -> identifier (names each crop)   -> counts + share of shelf

See `docs/ROADMAP.md` for the full plan and `docs/PROPOSAL.md` for the original
proposal.

## Status: Phase 0 (foundations)

The inference API does not exist yet. What works today is the data pipeline:
export photos out of MongoDB, fix a leakage-free test set, and prepare Label
Studio for labelers.

| Phase | What | State |
| --- | --- | --- |
| 0 | Export, manifest, fixed test set, labeling setup | **in progress** — see `docs/PHASE0_REMAINING.md` |
| 1 | SKU-110K detector, reference gallery, embedding matcher | not started |
| 2 | FastAPI `/count`, `/overlay`, `/health` in Docker | not started |
| 3 | Pre-labeling loop, fine-tuning, MLflow, DVC remote | not started |

The Phase 0 tooling below runs, but it has not yet been pointed at the real
database: `configs/export.yaml` still describes a schema the production data
does not use, so no manifest and no fixed test set exist yet.
`docs/PHASE0_REMAINING.md` has the actual schema and what is left.

## Setup

Python 3.14, managed with [uv](https://docs.astral.sh/uv/).

    uv sync --group dev          # runtime + test dependencies
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
`deploy/label-studio/README.md`.

Label the **test set first** (`test_labeling.txt`, 30 photos); it must stay
fixed. Splits are a stable hash of `store_id`, so re-running after new exports
never moves a store between train and test.

Labelers follow `docs/labeling_guide.md`. `docs/requests.md` holds the messages
to send for the class list and packshots.

## Layout

    configs/        export.yaml (EDIT FIRST), classes.csv (class list template)
    src/face_counter/
      config.py             paths, config loading, Mongo connection
      export_photos.py      GridFS -> data/raw/images + manifest.csv
      make_splits.py        train/val/test by store + photo lists to label first
      prepare_label_studio.py   labeling config XML + task JSON
    deploy/label-studio/    Label Studio (third-party labeling app) deployment
    docs/           ROADMAP, PROPOSAL, DATASET_PREPARATION, labeling_guide, requests
    scripts/        scan_images.py, a standalone image audit helper
    tests/          end-to-end tests on a fake MongoDB
    data/           git-ignored; DVC owns dataset versioning

## Data

`data/raw/` is git-ignored and versioned with DVC (`.dvc/`). No DVC remote is
configured yet, so data is local-only yet.
