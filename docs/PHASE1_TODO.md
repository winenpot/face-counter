# Phase 1 TODO — from a read-only survey of `atpg`

Written after probing the live database on 2026-09-22. Every number here came
from a read-only query; nothing was written. Supersedes the guesses in
`configs/export.yaml`, which was authored before anyone had looked at the data.

Phase 1 target (from `docs/ROADMAP.md`): a script that turns a photo into SKU
counts end to end, with accuracy measured on a fixed test set.

---

## 0. BLOCKER — the credential in `.env` is a `root` superuser

The connection string works, but it authenticates as **`root` on `admin`**: 136
privilege actions including `insert`, `update`, `remove`, `dropDatabase`,
`dropCollection`, `shutdown`, `createUser` and `grantRole`, across **every**
database on the server (20 of them, including unrelated apps — `atp_hr`,
`atp_trade`, `sitedb`, `okala`).

The roadmap's day-1 rule is that the export "only ever reads", and the export
code is written for a user that *cannot* write. Right now that guarantee is
enforced by nothing but the code being careful. One bad filter in a future
script, or this string reaching a container that gets compromised, is a
server-wide incident rather than a bad export.

- [ ] **Create the read-only user the export was designed for** and put that in
      `.env` instead. It only needs `atpg`:

      use admin
      db.createUser({
        user: "shelf_reader",
        pwd: "<long random>",
        roles: [ { role: "read", db: "atpg" } ]
      })

- [ ] **Rotate the `root` password.** It has been sitting in a `.env` on a
      developer workstation; treat it as exposed.
- [ ] Verify the replacement is read-only before using it: re-run
      `connectionStatus` and confirm no mutating actions are granted.

Do this before the full export. A 28 GB read is exactly the kind of long job you
do not want running as `root` against production.

---

## 1. Correct `configs/export.yaml` to the real schema

The shipped config is wrong in every field — it assumes a separate metadata
collection referencing GridFS by `file_id`. The reality:

**`atpg.photos.files` is self-contained.** Metadata is flattened onto the GridFS
file document itself, so `source: gridfs` is correct and no join is needed:

| field | type | notes |
| --- | --- | --- |
| `_id` | ObjectId | the GridFS file id |
| `filename` | str | e.g. `368267b6-….jpg` |
| `photo_id` | str(36) | UUID, unique per photo (0 duplicates among `shelf`) |
| `photo_type` | str | `shelf`, `shelf_thumb`, `sardar`, `sardar_thumb`, `contract*` |
| `store_code` | **str OR int** | the store; see the type trap below |
| `contentType` | str | `image/jpeg` 24,069 · `image/heic` 69 · `png` 13 · `webp` 2 |
| `length`, `chunkSize`, `uploadDate` | — | standard GridFS |

There is **no** `visit_id`, **no** `rep_id`, **no** `city`, and **no**
`created_at` on the photo. `city`/`region` must come from the `location` join
(§3); rep identity is not available at photo level at all.

- [ ] Rewrite `configs/export.yaml`: `source: gridfs`, `database: atpg`,
      `gridfs_bucket: photos`, and map only the fields that exist
      (`store_id: store_code`, `taken_at: uploadDate`). Drop `visit_id`/`rep_id`
      or leave them unmapped rather than inventing paths.
- [ ] Update `_parse_date`/manifest handling if `rep_id`/`city` become empty
      columns — `make_splits.py` already falls back from `store_id` to
      `visit_id` to per-photo, and with no `visit_id` the store is the only
      grouping key that matters.

### `store_code` type trap

`store_code` is a **string in 21,773 docs and an int in 2,361**. Checked
explicitly: **0 stores appear as both types**, so normalising with `str()` does
not merge two distinct stores, and the split stays sound. But a Mongo query
filtering `{"store_code": "1939"}` silently misses the int-typed docs.

- [ ] Normalise `store_code` to a trimmed string when writing the manifest.
- [ ] Never filter on `store_code` by equality in a query without covering both
      types (`$in: ["1939", 1939]`).

---

## 2. Export only `photo_type: shelf` — the thumbnails are the same photos

| photo_type | files | size | what it is |
| --- | --- | --- | --- |
| `shelf` | **9,207** | **28.4 GB** | full-size shelf photography ← train on this |
| `shelf_thumb` | 7,750 | 0.2 GB | ~27 KB thumbnails of the same photos |
| `sardar` | 3,790 | 13.3 GB | full-size, different purpose — ask the business |
| `sardar_thumb` | 3,388 | 0.1 GB | thumbnails |
| `contract`(+thumb) | 18 | ~0 | ignore |

`shelf` and `shelf_thumb` **share `photo_id`** (1,543 overlaps in a 3,000-doc
sample), confirming the thumb is a derivative, not a separate photo. Training on
both would put a photo and its own downscaled copy in the dataset — and, if they
landed in different splits, would leak the test set into training.

- [ ] Add `query: {"photo_type": "shelf"}` to the export config.
- [ ] Decide with the business whether `sardar` (13.3 GB, 3,790 photos) is also
      shelf photography. If yes it roughly doubles the corpus; if it is
      storefront/banner photography it must stay out.

### Revised scale — the roadmap's numbers were optimistic

The roadmap assumed "~20,000 photos, 60–100 GB". Actual: **24,147 files / 42.0 GB
total**, but only **9,207 usable shelf photos / 28.4 GB**. The 20k figure counts
thumbnails and non-shelf types.

- [ ] Re-budget the disk: ~30 GB for the `shelf` export, not 100 GB. The extra
      500 GB–1 TB drive is still right for Phase 3 artifacts, but Phase 1 fits
      on what exists.
- [ ] Note the corpus is **younger than assumed**: uploads span 2026-07-08 →
      2026-09-22 only (Jul 2,671 · Aug 3,830 · Sep 2,706). No seasonal variation,
      and any claim about year-over-year drift is unsupportable.

---

## 3. Enrich stores from `location` for diverse sampling

`make_splits.diverse_sample()` round-robins across `city` to spread the test set
— but `city` does not exist on the photo. It does exist one join away:

`atpg.location` (4,866 docs) has `code` (matches `store_code`), `name`, and
`region` (e.g. `تهران منطقه 3`). Join quality is good: **3,717 of 3,747 photo
stores match (99.2%)**, codes are unique (0 map to multiple locations), covering
**16 distinct regions**.

- [ ] Join `location.code → store_code` during export and write `region` into
      the manifest's `city` column (or rename the column to `region`).
- [ ] Note the 30 unmatched stores; they still split fine, they just sample as
      region `""`.

---

## 4. Fix the test set before any training

- [ ] Run the export, then `uv run shelf-splits`. With 3,292 stores in the
      `shelf` subset, a 10% store holdout gives ~329 test stores — far more than
      the 30 photos needed, so the fixed test set is comfortably feasible.
- [ ] Label those 30 photos first. They must stay frozen: splits are a stable
      hash of `store_code`, so re-exporting never moves a store.
- [ ] Check the store-size distribution when sampling: most stores have few
      photos (1,583 stores have ≥2, only 10 have ≥25; the largest has 40). The
      existing `max_per_group=2` cap for the test set is well matched to this.

---

## 5. Data-quality issues to handle in the export

- [ ] **HEIC (69 files).** Pillow cannot open HEIC without `pillow-heif`. Today
      `export_photos.py` catches the failure and counts it under `bad_image`, so
      they would be silently dropped. Either add `pillow-heif` or accept and log
      the loss explicitly.
- [ ] **432 `(store_code, length)` collisions** among `shelf` photos — likely
      genuine re-uploads of the same image. `make_splits.py` already drops exact
      duplicates by `sha256`, which is the right guard; confirm it catches these.
- [ ] **1 shelf photo under 20 KB** (min 7 KB vs 3,231 KB average) — almost
      certainly truncated. The existing image-decode check should reject it.
- [ ] **No index on `photo_type` or `store_code`.** `photos.files` has only
      `_id_` and `filename_1_uploadDate_1`. A filtered export will collection-scan
      24k docs — acceptable once, but do not add an index to production without
      asking, and keep `throttle_seconds` on during working hours.

---

## 6. Then the actual Phase 1 modelling work

Unchanged from the roadmap, unblocked once the above lands:

- [ ] Train YOLO on SKU-110K (or licensed published weights); eyeball recall on
      10 of our photos.
- [ ] Large input size (1280) or SAHI tiling — with 3.2 MB average photos of
      whole aisles, products are small in frame.
- [ ] Pre-fill the test set's boxes in Label Studio; correct and assign classes.
- [ ] Reference gallery from packshots + crops (never from the test set).
- [ ] Embedding matcher (DINOv2/CLIP) with an `other` threshold.
- [ ] Evaluation script: per-brand count error, share-of-shelf error, detector
      recall.

**Still missing from the business** (Phase 0 items never closed): the real
`configs/classes.csv` — it is still the `Kix-Max` template — and the packshots.
Stage 2 cannot be built without them. `docs/requests.md` has the messages to send.
