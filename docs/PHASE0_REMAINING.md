# Phase 0 — what is left

From a read-only survey of the live `atpg` database, 2026-09-22. These numbers
supersede `configs/export.yaml`, which was written before anyone looked at the
data. Re-check them any time with:

    uv run python scripts/verify_atpg_claims.py

---

## 1. Fix the test set

- [ ] Run the export, then `uv run shelf-splits`. 3,292 stores in the `shelf`
      subset means a 10% holdout gives ~329 test stores — ample for 30 photos.
- [ ] Label those 30 first, then freeze. Splits hash the resolved `store_id`
      (§1 of Done, below — NOT the raw `store_code`), so re-exporting never
      moves a store.

## 2. Data quality

- [ ] **432 `(store_code, length)` collisions** — likely re-uploads; confirm the
      existing `sha256` dedupe catches them.
- [ ] **1 photo at 7 KB** (vs 3,231 KB average) — almost certainly truncated.
- [ ] **No index on `photo_type`/`store_code`** — a filtered export
      collection-scans 24k docs. Acceptable once; do not add an index to
      production without asking, and keep `throttle_seconds` on during work hours.

## 3. Blocked on the business

`docs/requests.md` has the messages to send. On the critical path for stage 2.

- [ ] **Is `sardar` shelf photography?** 3,790 files, 13.3 GB, a distinct
      `photo_type` from `shelf`. If yes the corpus roughly doubles (add it to
      the export query); if it's storefront/banner photography it stays out.
      This is a business call, not a data one.
- [ ] **Class list** — `configs/classes.csv` is still the `Kix-Max` template.
      `prepare_label_studio.py` will generate a config full of fictional
      products if nobody notices.
- [ ] **Packshots**, 2–5 per SKU, for the reference gallery.
- [ ] **Labeling guide examples** — `docs/labeling_guide.md` still asks for
      three annotated screenshots. Labelers calibrate on those.

## 4. Then Phase 1

Do not start until §1 lands; every item needs a manifest and a frozen test set.
Full list in `docs/ROADMAP.md` — train YOLO on SKU-110K, 1280px or SAHI tiling,
pre-fill boxes in Label Studio, build the gallery from packshots (never the test
set), embedding matcher with an `other` threshold, evaluation script.

---

## Done

- [x] **`store_code` on a photo is a per-visit registration code, NOT the
      store's identity — corrected a bug in the two entries below.** Traced
      from a UI mismatch (field labeled "کد ثبت"/registration code shown next
      to "کد ثابت"/fixed code, a different number, for the same store).
      Confirmed live: `atpg.location` shows one physical store under 5
      different `code` values issued over time (1,100 of 3,072 stores do
      this); `store_events` logs `action: visit_started`/`visit_resumed` per
      `store_code`, actor = the rep. The durable store id is
      `location.permanent_id`, reachable only through the same
      `code -> permanent_id` join.

      Impact: the manifest's `store_id` column previously held this raw
      per-visit code. `make_splits.py`'s by-store leakage guard (its whole
      reason to exist — "same shelf, same visit" per-store dedup) was
      actually grouping by visit: the same physical store, visited twice,
      got two different codes and could legally land in both train and test.

      Fix: `configs/export.yaml` gained `metadata.store_join`
      (`location.code -> permanent_id`), parallel to `region_join`.
      `export_photos.py`'s join loader is now generic (`load_join_map`, used
      by both). The raw per-visit code now correctly populates `visit_id`
      (previously always empty — atpg genuinely has no other visit
      identifier); `store_id` holds the resolved, durable store. Unmatched
      codes fall back to `store_id: ""` rather than silently treating the
      visit code as a store. `make_splits.group_key()` needed no logic
      change — it already grouped by `store_id` with a `visit_id` fallback —
      only its docstring was clarified.

      Verified against the live `atpg` DB: photos sharing one visit code
      (`store_code`) resolved to the same `store_id`, an unmatched code fell
      back to `store_id: ""`. Covered by
      `test_store_join_resolves_visit_code_to_real_store` and the
      `store_join` assertion in `test_shipped_config_is_filled_in`.

- [x] **HEIC files decode instead of dropping into `bad_image`.** `pillow-heif`
      added as a core dependency (not `analytics` — `shelf-export` itself needs
      it); `export_photos.py` calls `pillow_heif.register_heif_opener()` at
      import time so `Image.open()` handles HEIC transparently, no extra code
      path. Output extension is `.heif` (from the decoded `im.format`, same
      mechanism as the existing `jpeg`→`jpg` rename). Verified against the live
      `atpg` DB: 8 of 25 sampled photos were HEIC, all decoded, `bad_image: 0`
      — previously these were silently dropped with no error. Covered by
      `test_heic_photo_is_exported_not_dropped`.

- [x] **Location joined for the region.** `configs/export.yaml` has
      `metadata.region_join` (`location.code -> store_code`, `region` field).
      `export_photos.load_join_map()` builds the lookup once per run;
      `city` falls back to `""` for unmatched stores rather than raising.
      Verified against the live `atpg` DB: 9 of 10 sampled photos got a region
      (`تهران منطقه 5`, `تهران منطقه 6`), 1 fell back to `""` — consistent with
      the ~99% match rate. Covered by `test_region_join_fills_city` and the
      `region_join` assertion in `test_shipped_config_is_filled_in`.

- [x] **Export filtered to `photo_type: shelf`.** `configs/export.yaml`'s
      `metadata.query` is now `{"photo_type": "shelf"}`. Verified against the
      live `atpg` DB — a 5-doc sample returned only `shelf`. Covered by
      `test_gridfs_source_respects_photo_type_query` and the query assertion in
      `test_shipped_config_is_filled_in`.

      `shelf` and `shelf_thumb` **share `photo_id`** — the thumb is a
      downscaled copy of the same photo, not a separate one — so this filter
      is what prevents a photo and its own copy landing in different splits
      (test-set leakage). Scale is smaller than the roadmap assumed (~20,000
      photos, 60–100 GB): budget **~30 GB**, not 100. Uploads span
      2026-07-08 → 09-22 only, so no seasonal variation — do not claim
      year-over-year drift.

      Still open: whether `sardar` (13.3 GB, 3,790 photos) is shelf
      photography — a business call, tracked in §3.

      Also surfaced while testing: 8 of 13 candidate docs in one live sample
      failed to decode as images. Overlaps §2 (data quality); not investigated
      further here.

- [x] **`configs/export.yaml` rewritten to the real schema.**

      `source: gridfs`, `database: atpg`, `gridfs_bucket: photos`,
      `store_id: store_code`, `taken_at: uploadDate`. `rep_id`/`city`
      left unmapped rather than invented (`visit_id` is populated via the
      store_join fix above). `export_photos.py` now normalises the resolved
      `store_id` to a trimmed string regardless of whether Mongo returned str
      or int. Verified against the live `atpg` DB with `--limit 1`; covered by
      `test_shipped_config_is_filled_in` and
      `test_int_store_code_normalised_to_string`.

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
