# Phase 0 — what is left

From a read-only survey of the live `atpg` database, 2026-09-22. These numbers
supersede `configs/export.yaml`, which was written before anyone looked at the
data. Re-check them any time with:

    uv run python scripts/verify_atpg_claims.py

---

## 1. Fix the test set

- [x] **Export run against production, 2026-09-24.** 9,409 new + 295 already on
      disk = **9,704 manifest rows**, `missing: 0`, `bad_image: 1`. ~30 GB, on
      the GPU box only — this workstation needs just the 2 MB manifest
      (`scripts/sync_from_hemin.sh --with-manifest`).
- [ ] Run `uv run shelf-splits` over the full manifest.
- [ ] Re-cut the fixed test set to **30 photos** — it currently holds 15, drawn
      from the old 295-photo sample. Needs `--force`, which should be its last
      use ever. Eyeball the mix first: aisles, fridges, glare, store types.
      Then freeze. Splits hash the resolved `store_id` (§1 of Done, below —
      NOT the raw `store_code`), so re-exporting never moves a store.
- [ ] **Unexplained: 2,230 distinct `store_id`, against the surveyed 3,292.**
      The 1% join-failure rate (93 blank rows) does not account for a 32% gap.
      Not blocking — median 3 photos/store, max 37, ample for a 30-photo test
      set — but do not quote store coverage until someone explains it.

## 2. Data quality

- [x] **The `(store_code, length)` collisions resolve safely.** The full
      manifest has 109 duplicate-`sha256` groups (131 extra rows), **19 of them
      spanning more than one `store_id`** — exactly the cross-store leakage
      worth worrying about. `make_splits.py:113` drops duplicates by `sha256`
      before splitting, so byte-identical re-uploads cannot land on both sides
      of the train/test boundary. That line is load-bearing, not decorative.
- [x] **The 7 KB photo is confirmed and contained.** Exactly one file under
      50 KB in the full manifest (7,253 bytes, 79x275) and exactly one
      `bad_image` in the export — the same photo. Not a new failure mode.
      Worth noting the earlier live sample's 8-of-13 decode failures collapsed
      to 1 in 9,704 once `pillow-heif` landed: good evidence that diagnosis
      was right.
- [ ] **No index on `photo_type`/`store_code`** — a filtered export
      collection-scans 24k docs. Acceptable once; do not add an index to
      production without asking, and keep `throttle_seconds` on during work hours.
- [ ] **Manifest dimensions can disagree with decoded dimensions (EXIF
      orientation).** Two of the 30 test photos are recorded `1836x4080`
      (portrait) in the manifest but decode as `4080x1836` (landscape) — the
      export stored the pre-rotation size while Pillow applies the EXIF
      orientation flag. Harmless today, but anything in Phase 1 that trusts
      manifest width/height over the decoded image will place boxes rotated
      90°. Decide one source of truth before boxes are drawn.
- [ ] **The field app recompresses uploads server-side.** 1,225 photos (12.6%)
      sit within 2 KB of exactly 4 MiB, 950 at the identical byte count
      4,194,868; further populations are downscaled to 810x1080 (221),
      960x1280 (214), 1200x1600 (200). Confirmed by the app developer's own
      account of fixing upload problems. Consequences: treat resolution tier as
      a reporting slice (`ERROR_ANALYSIS.md`), and ask whether the originals
      survive anywhere (`requests.md` §3). Low-resolution photos in the corpus
      are **representative, not defective** — do not filter them out.

## 3. Blocked on the business

`docs/requests.md` has the messages to send. On the critical path for stage 2.

- [x] **Is `sardar` shelf photography? No — confirmed 2026-09-24.** Front-of-store
      photos, not shelf photos. Stays excluded; `configs/export.yaml`'s existing
      `photo_type: shelf` filter is already correct as shipped, no export change
      needed. Corpus stays at ~9,200 photos / ~28 GB, not the ~doubled estimate.
- [x] **Packshots — enough to proceed; the marketing ask stays open.**
      Phase 0 is no longer blocked on this. *242 images extracted from the
      invoice's own embedded "Image" column into `configs/Product/from_invoice/`
      (see `scripts/extract_invoice_packshots.py`), one per class_name,
      matching the same brand/category/sku parsing as `classes.csv` — so the
      two stay in lockstep. Gitignored like the rest of `configs/Product/`.
      All company material, nothing placeholder: the gap is **resolution,
      coverage, and naming**, not authenticity. These are invoice thumbnails
      (~42 KB average), small and inconsistently framed — one spot-checked
      case showed a multi-flavor carton photo attached to a single-flavor
      sku, which would teach an embedding matcher the wrong thing. Good
      enough to seed a first gallery experiment in Phase 1; re-check that
      mismatch before trusting gallery numbers.*

      *Checked 2026-09-24: `configs/Product/Kixmax/` (2 subfolders) and
      `configs/Product/Torsh-X/` (15 files, ~4 MB each) hold genuine studio
      marketing photography — ~100x the resolution of the invoice thumbnails
      — but they cover only 2 of 8 brands, are partial even there (no
      gum/sour-candy shots for Kix-Max, no sour-candy for Torsh-X), and are
      named by flavor or mockup (`Berlin.png`, `24_cans_mockup.png`) rather
      than `class_name`, so nothing in the pipeline maps them to a class yet.
      `24_cans_mockup.png` is a marketing composite, not a single product
      face — wrong as a gallery reference. Would need renaming and curation
      before use.*

      **Outstanding ask (`docs/requests.md`), no longer Phase 0-blocking:**
      studio packshots named by `class_name`, 2–5 per SKU, covering all 8
      brands. Matters most for SKUs that are rare in our own corpus — Phase 1
      also builds gallery crops from corrected photos, which may well beat
      packshots anyway since they match the reps' real cameras and lighting.
- [~] **Labeling guide examples** — `docs/labeling_guide.md` still asks for
      three annotated screenshots. In progress (owner working on it 2026-09-24);
      not blocking the rest of §1/§4.

## 4. Then Phase 1

Do not start until §1 lands; every item needs a manifest and a frozen test set.
Full list in `docs/ROADMAP.md` — train YOLO on SKU-110K, 1280px or SAHI tiling,
pre-fill boxes in Label Studio, build the gallery from packshots (never the test
set), embedding matcher with an `other` threshold, evaluation script.

---

## Done

- [x] **Class list built from the real sales export invoice, not the
      `Kix-Max` template.** `scripts/build_classes.py` reads only the
      "Product Description" column of the company's proforma invoice
      (`.xlsm`, never pricing/customer data, never committed — see the note
      below) and collapses wholesale packaging variants (Middle Box, Card
      board, Dispenser Box — B2B case types, invisible on a shelf) into one
      class per shelf-visible product, while keeping real visual differences
      (Can vs Glass, each flavor) as separate classes. `configs/classes.csv`
      now has 103 real classes across 9 brands (Kix-Max, TorshX, Picola,
      My-Milk, Kix, Biskett, Tommy-Joy, Bomb), all `is_ours=1` — this
      invoice has no competitor rows. Heuristic text parsing on free-form
      invoice descriptions; expect some rough edges (e.g. two rows fell back
      to `..._unspecified` sku with no flavor word matched) — worth a human
      skim before labelers rely on it. Re-run any time a newer invoice
      arrives: `uv run python scripts/build_classes.py <path-to-.xlsm>`.
      Covered by `tests/test_build_classes.py` (packaging collapse, Can/Glass
      split, brand canonicalisation, flavor-order-independent dedup).

      **The source `.xlsm` and `configs/Product/` (packshots) are gitignored
      — company pricing, a real customer name/country, and product
      photography.** Only the derived `classes.csv` (product names only) is
      committed. See `.gitignore` for the exact rule.

- [x] **Labeling batches are numbered and cumulative — a photo can never be
      sent to labelers twice.** Previously `label_batch_01.txt` was
      unconditionally overwritten on every `shelf-splits` run, so a re-export
      that pulled in new photos could silently swap in different photos
      under the same filename, with no way to tell what labelers had already
      seen. Fixed: `make_splits.py` now writes `label_batch_01.txt`,
      `_02.txt`, ... — each run only pulls train photos that have never
      appeared in *any* prior batch file, existing batch files are never
      rewritten, and if nothing new is available no file is written at all.
      Verified against the 295-photo live sample: re-running `shelf-splits`
      with no new data correctly created `label_batch_02.txt` with the 44
      train photos `label_batch_01.txt`'s per-group cap had left out, zero
      overlap between the two files. Covered by
      `test_label_batches_never_repeat_a_photo`.

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
      as exposed. **Deferred by user decision, 2026-09-24** — not blocking
      Phase 0 close-out; not forgotten. The read-only `read@atpg` user is
      already in use for the export, so the exposed root credential is not
      on the active path, just outstanding cleanup.
