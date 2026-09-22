# Phase 0 — what is left

From a read-only survey of the live `atpg` database, 2026-09-22. These numbers
supersede `configs/export.yaml`, which was written before anyone looked at the
data. Re-check them any time with:

    uv run python scripts/verify_atpg_claims.py

---

## 1. `configs/export.yaml` maps fields that do not exist

`atpg.photos.files` is self-contained — metadata sits on the GridFS document,
so no join is needed. Actual fields:

| field | type | notes |
| --- | --- | --- |
| `photo_id` | str(36) | UUID, unique per photo |
| `photo_type` | str | `shelf`, `shelf_thumb`, `sardar`, `sardar_thumb`, `contract*` |
| `store_code` | **str OR int** | see the type trap below |
| `filename`, `contentType`, `length`, `chunkSize`, `uploadDate` | — | standard GridFS |

No `visit_id`, no `rep_id`, no `city`, no `created_at`. Region comes from the
`location` join (§3); rep identity is not available at photo level at all.

`store_code` is a string in 21,773 docs and an int in 2,361. **0 stores appear
as both**, so normalising with `str()` is safe — but an equality filter silently
misses the other type.

- [ ] Rewrite the config: `source: gridfs`, `database: atpg`,
      `gridfs_bucket: photos`, `store_id: store_code`, `taken_at: uploadDate`.
      Leave `visit_id`/`rep_id` unmapped rather than inventing paths.
- [ ] Normalise `store_code` to a trimmed string in the manifest.

## 2. Export only `photo_type: shelf`

| photo_type | files | size | |
| --- | --- | --- | --- |
| `shelf` | **9,207** | **28.4 GB** | train on this |
| `shelf_thumb` | 7,750 | 0.2 GB | same photos, downscaled |
| `sardar` | 3,790 | 13.3 GB | different purpose — ask the business |
| `sardar_thumb` / `contract*` | 3,406 | 0.1 GB | ignore |

`shelf` and `shelf_thumb` **share `photo_id`**, so exporting both puts a photo
and its own copy in the dataset — test-set leakage if they land in different
splits. Confirm in mongosh:

    db['photos.files'].aggregate([
      {$group: {_id:'$photo_id', types:{$addToSet:'$photo_type'}}},
      {$match: {types:{$all:['shelf','shelf_thumb']}}},
      {$count: 'duplicated'}
    ])

- [ ] Add `query: {"photo_type": "shelf"}` to the export config.
- [ ] Ask whether `sardar` is shelf photography. If yes the corpus roughly
      doubles; if it is storefront/banner photography it stays out.

Scale is smaller than the roadmap assumed (~20,000 photos, 60–100 GB): budget
**~30 GB**, not 100. Uploads span 2026-07-08 → 09-22 only, so no seasonal
variation — do not claim year-over-year drift.

## 3. Join `location` for the region

`make_splits.diverse_sample()` round-robins on `city`, which photos do not have.
`atpg.location` has it: `code` matches `store_code`, **3,717/3,747 stores
(99.2%)**, 16 regions.

- [ ] Join `location.code → store_code` during export; write `region` into the
      manifest's `city` column. The 30 unmatched stores sample as `""`.

## 4. Fix the test set

- [ ] Run the export, then `uv run shelf-splits`. 3,292 stores in the `shelf`
      subset means a 10% holdout gives ~329 test stores — ample for 30 photos.
- [ ] Label those 30 first, then freeze. Splits hash `store_code`, so
      re-exporting never moves a store.

## 5. Data quality

- [ ] **69 HEIC files** — Pillow drops them silently into `bad_image`. Add
      `pillow-heif` or log the loss explicitly.
- [ ] **432 `(store_code, length)` collisions** — likely re-uploads; confirm the
      existing `sha256` dedupe catches them.
- [ ] **1 photo at 7 KB** (vs 3,231 KB average) — almost certainly truncated.
- [ ] **No index on `photo_type`/`store_code`** — a filtered export
      collection-scans 24k docs. Acceptable once; do not add an index to
      production without asking, and keep `throttle_seconds` on during work hours.

## 6. Blocked on the business

`docs/requests.md` has the messages to send. On the critical path for stage 2.

- [ ] **Class list** — `configs/classes.csv` is still the `Kix-Max` template.
      `prepare_label_studio.py` will generate a config full of fictional
      products if nobody notices.
- [ ] **Packshots**, 2–5 per SKU, for the reference gallery.
- [ ] **Labeling guide examples** — `docs/labeling_guide.md` still asks for
      three annotated screenshots. Labelers calibrate on those.

## 7. Then Phase 1

Do not start until §1–§4 land; every item needs a manifest and a frozen test set.
Full list in `docs/ROADMAP.md` — train YOLO on SKU-110K, 1280px or SAHI tiling,
pre-fill boxes in Label Studio, build the gallery from packshots (never the test
set), embedding matcher with an `other` threshold, evaluation script.

---

## Done

- [x] **Read-only Mongo user.** `.env` now authenticates as `read@atpg` with 0
      mutating actions (was `root` with 136 across all 20 databases). To recreate:

      use admin
      db.createUser({
        user: "shelf_reader",
        pwd: passwordPrompt(),
        roles: [ { role: "read", db: "atpg" } ]
      })

      `read` on `atpg` covers GridFS with no extra grants. The user lives in
      `admin`, so the URI needs `?authSource=admin`. To verify, open a **new**
      mongosh as that user — `use` switches database, not user — and check that
      `db.perm_test.insertOne({x:1})` fails. Never write-test against
      `photos.files`.

- [ ] **Rotate the `root` password.** It sat in a workstation `.env`; treat it
      as exposed.
