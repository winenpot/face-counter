# Phase 0 — what is left, from a read-only survey of `atpg`

Written after probing the live database on 2026-09-22. Every number here came
from a read-only query; nothing was written. Supersedes the guesses in
`configs/export.yaml`, which was authored before anyone had looked at the data.

**Do not take these numbers on trust** — `docs/VERIFY.md` has a read-only
command for every claim below, and `uv run python scripts/verify_atpg_claims.py`
re-checks them all in one go. Counts drift upward as photos arrive; the
verifier allows growth and flags a drop.

**Phase 0 is not finished.** Its exit criteria (`docs/ROADMAP.md`) are "data is
exportable, the test set is fixed, labeling is secured, and the business side is
gathering classes and packshots". None of the first three hold: the export
config maps fields that do not exist in this database, no manifest has been
built, and no test set has been fixed. Sections 0–5 below are the remaining
Phase 0 work. Section 6 is the Phase 1 hand-off, listed only so the ordering is
visible — do not start it until §1–§4 land, because every item in it depends on
a manifest and a frozen test set.

---

## 0. BLOCKER — the credential in `.env` is a `root` superuser

_Verify this section yourself: `docs/VERIFY.md` §4._

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
        pwd: passwordPrompt(),               // prompts; keeps it out of history
        roles: [ { role: "read", db: "atpg" } ]
      })

      `read` on `atpg` covers every collection in that database, GridFS
      included — `photos.files`, `photos.chunks` and `location` all work with
      no extra grants. The user lives in `admin`, so the connection string
      needs `?authSource=admin` (as in `.env.example`).

      Then confirm it is actually read-only. Do this in a **new shell**,
      logged in as the new user — `use` switches database, not user, so
      there is no way to become `shelf_reader` from an existing session:

      mongosh -u shelf_reader -p --authenticationDatabase admin
      use atpg                                   // the DATABASE, not the user
      db['photos.files'].countDocuments({})      // works
      db.perm_test.insertOne({x: 1})             // must fail: not authorized

      Write the test against a throwaway collection, never `photos.files`.
      If you are still connected as an admin user the insert *succeeds*, and
      a document with no `length`/`chunkSize` in the real GridFS collection
      can break clients that read it.

- [ ] **Rotate the `root` password.** It has been sitting in a `.env` on a
      developer workstation; treat it as exposed.

Do this before the full export. A 28 GB read is exactly the kind of long job you
do not want running as `root` against production.

---

## 1. Correct `configs/export.yaml` to the real schema

_Roadmap Phase 0: **Export script**_

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

_Roadmap Phase 0: **Export script**, **Manifest**_

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

_Roadmap Phase 0: **Manifest**, **Fixed test set**_

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

_Roadmap Phase 0: **Fixed test set**_

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

_Roadmap Phase 0: **Export script**_

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

## 6. Blocked on the business — chase these in parallel

_Roadmap Phase 0: **Class list**, **Packshots**, **Labeling guide**_

These do not depend on any of the above and are on the critical path for stage 2
(the identifier). `docs/requests.md` has the messages to send.

- [ ] **Class list.** `configs/classes.csv` is still the `Kix-Max` placeholder
      template. Stage 2 cannot be built against it, and
      `prepare_label_studio.py` will happily generate a labeling config full of
      fictional products if nobody notices.
- [ ] **Packshots**, 2–5 per SKU, for the reference gallery.
- [ ] **Labeling guide examples.** `docs/labeling_guide.md` is written, but its
      "Examples" section is still a placeholder asking for three annotated
      screenshots (an aisle, a fridge with glare, a crowded small shop). Labelers
      calibrate on those, so the guide is not finished without them.

The roadmap notes the fallback if these slip: start with a brand-level gallery
and `COMPETITOR_<category>` classes.

---

## 7. Phase 1 hand-off — do not start until §1–§4 land

_Roadmap Phase 1: **Working pipeline (days 4–10)**_

Listed for ordering only. Every item depends on a manifest and a frozen test
set:

- [ ] Train YOLO on SKU-110K (or licensed published weights); eyeball recall on
      10 of our photos.
- [ ] Large input size (1280) or SAHI tiling — with 3.2 MB average photos of
      whole aisles, products are small in frame.
- [ ] Pre-fill the test set's boxes in Label Studio; correct and assign classes.
- [ ] Reference gallery from packshots + crops (never from the test set).
- [ ] Embedding matcher (DINOv2/CLIP) with an `other` threshold.
- [ ] Evaluation script: per-brand count error, share-of-shelf error, detector
      recall.
