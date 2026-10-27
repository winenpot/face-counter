# Pilot: two brands, cans and glass bottles

**Start here when you pick the project up.** This is the active slice of the
work and its ordered to-do list. `ROADMAP.md` still holds the full,
horizontal plan; nothing in it is cancelled, only sequenced after this.

## Current checkpoint (2026-10-26, end of day)

Branch `master`, 217 tests pass (`uv run pytest`). `uv run ruff check .`
reports 56 errors, all pre-existing. Replace this section at every stop;
don't append. The ordered task list and the full handoff are in
`.hermes/plans/2026-10-04_demo-path.md` (section "Current handoff"); serving
detail is in `.hermes/plans/2026-10-10_111130-t6-fastapi-service.md`.

**Where the pilot stands, honestly.** The measurement half works (frozen test
set, gold set, `shelf-eval`, detector). The prediction half is wired end to
end but does not yet answer the pilot's question: brand identity is 65.3% on
gold, so the predicted share is far off ground truth (T5) and the demo API
counts products only. Rough completeness: ~65% of the pilot/demo, ~25% of
`ROADMAP.md` Phases 0-4.

- **Running:** demo API `face-counter-serve` on the apps server, public on
  port 8096 (plain HTTP, demo key, Basic Auth on the upload page `/`).
  Detection-only; brand matching behind `?debug=true`; CLIP canned/glass off.
  Runbook: `docs/vault/DevOps/Demo API on the apps server.md`.
- **Labeling (training batches, step 6b) started.** Five Label Studio
  projects `pilot-batch-01`..`05` (ids 6-10, 250 tasks each, Persian scope
  config). Read over the API on 2026-10-26 09:07: 232 of 1,250 submitted
  (01: 125, 02: 8, 03: 78, 04: 0, 05: 21) by three labelers plus the project owner. Live numbers and
  the review findings: `docs/vault/Findings/2026-10-26 Training batch labeling status.md`.
  Quality is below the test set's (misses, wrong names, per the user's own
  review); 14 photos were submitted with zero edits to the pre-drawn boxes
  and a few tasks carry two annotations. Both must be fixed before any
  export is trained on. No fine-tuning round has run, so there is no
  learning curve yet: whether 1,250 photos is enough is unmeasured
  (`LABELING_STRATEGY.md` §8 guesses 300-600 for geometry to plateau).
- **Next, in plan order (demo path):** T8 demo prep (photos, caveats, random
  key), then #6, T7, T7b.
- **Labeling track, in parallel (labelers work on their own):**
  1. Batch hygiene: send the 14 zero-edit photos back to their labelers,
     reduce multi-annotation tasks to one, take a dated JSON export per
     batch project.
  2. Round 1 of 6b: fine-tune on the cleaned batch-01 export (face-only
     boxes), score on gold, confirm on the test set, plot the first
     learning-curve point.
- **The gap that decides the pilot's number:** identity. SKU-level galleries
  on the gold crops (demo-path T3/T5 open item) are the next cheap
  experiment; not yet scheduled ahead of T8.
- **2026-10-26/27 (committed):** best-practice audit, audit sources,
  candidate model survey (`docs/vault/Findings/`); labeling status with a
  day-by-day table to 27 Oct 06:00 (337 annotations on 332 photos, 15
  zero-edit, 4 duplicate tasks); reports for trade marketing and a technical
  version (`docs/reports/2026-10-27_*`); plan tasks T9-T13; scripts
  `scripts/labeler_qc.py`, `ls_status.py`, `packtype_match.py`.
- **Next session runs on the GPU PC** (the user's from now on; the colleague
  has not left yet, so his account and files stay untouched). First, in
  order: `git pull` there; check `uv sync`, `pytest`, GPU visible to torch;
  back up weights and `runs/`. Then the cheapest high-value GPU work:
  T11's Cat2Real-DINOv3-384 drop-in on the 225 gold crops, T9 parity, T12
  RF-DETR timing probe, then MLflow and round 1 (6b) when the user says.
- **Open standing work:** face audit in a v2 copy project
  (`ISSUE_FACES_NOT_OBJECTS.md`, waits on BI answers); face/behind field in
  the evaluator; inter-annotator agreement (`ERROR_ANALYSIS.md` §3). Open
  GitHub issues: #1, #2, #3, #5, #6, #7, #8.
- **Never:** write to project 3 (test) or edit project 5 (gold); run
  `shelf-splits --force`; `docker compose down -v` on Label Studio; rsync
  code to hemin; publish credentials or IP addresses (the repo is public).

> **Standing issue (2026-09-30): the pilot counts *faces*, not every object.**
> A face is the frontmost unit of a lane, one per lane; units behind it are
> not faces even when clearly visible. Labels, metrics and model choice below
> are read that way. Definition, open questions and plan:
> [`ISSUE_FACES_NOT_OBJECTS.md`](ISSUE_FACES_NOT_OBJECTS.md).

## Scope (decided 2026-09-27, metric narrowed 2026-09-29)

- **Question:** what share of the cans, and separately of the glass bottles,
  from us and our **targeted competitors** are ours? Per category:
  `ours / (ours + targeted competitors)`. This is our share *against the
  rivals we track*, **not** our share of all cans on the shelf: Coca-Cola, Bear
  and other untargeted brands are in neither the numerator nor the
  denominator. Always report it under that name; the two numbers are not
  comparable.
- **Targeted competitors** (decided 2026-09-29), named by brand and pack type
  like ours: Icy-Monkey, Hoffenberg (cans and glass), Laimon-Fresh (cans only; its glass was
  retired 2026-10-04, marketing); Fizzio,
  Freshy-Day, Genius, Sunich-Cool (glass only). Persian names in
  `configs/scope.yaml`.
- **Brands reported:** Kix-Max and TorshX, named by brand and pack type only
  (`Kix-Max_canned`), not by flavour.
- **Categories:** `canned_drinks` and `glass_drinks`, reported **separately**.
  Glass means glass only; plastic bottles are not in either.
- Lives in `configs/scope.yaml`. It is a filter over the full taxonomy
  (`classes.csv`, `reporting.yaml`), never a fork of it.

Three rules keep the pilot from closing off the wider system:

1. **Every can and glass bottle of ours is named**, whatever the brand. A can
   of another brand of ours is labeled as ours even when that brand's share is
   not reported. Targeted competitors are named too. Untargeted competitor
   cans and glass may keep `COMPETITOR_canned`/`COMPETITOR_glass` or stay
   `product`; the pilot's number reads neither.
2. **Boxes outside the scope keep the label `product`** ("not identified
   yet"), never `out_of_scope`. **A box with no label at all counts as
   `product`** (decided 2026-09-29). A later scope names them; nothing is
   relabeled. Pass one (geometry) still boxes every *face* on the shelf: the front unit
   of each lane; units behind it are not boxed.
3. **Extensibility is the experiment.** Widening the scope (add a brand, a
   category, a named competitor) must only touch `scope.yaml`,
   `classes.csv`, `reporting.yaml` and gallery images. If it needs code or a
   relabel, write down where; that is the finding.

## To do, in order

- [x] **Scope config and scoped labeling.** `configs/scope.yaml`;
      `uv run shelf-label-prep --list data/splits/test_labeling.txt --level scope`
      emits the pilot's 7 labels (`detail: brand`): Kix-Max_canned/glass,
      TorshX_canned/glass, `COMPETITOR_canned`, `COMPETITOR_glass`, `product`.
- [x] **1. Pick the detector that pre-draws boxes: `yolo26l-sku110k`.**
      Decided 2026-09-27 from run `runs/bakeoff/20260927-114232/`: more boxes
      than YOLO11s (2,814 vs 2,319) at the same duplicate rate (~5%), and the
      extra boxes checked by eye are real products YOLO11s missed. YOLOE with
      specific prompts collapsed (98 boxes total) and is shelved as a
      detector. This picks the labeling assistant only; every candidate is
      re-scored after fine-tuning.
- [~] **2. Count the drink photos in the test set.** Contact sheet
      2026-09-27: nearly all 30 show cans or glass bottles (fridges and drink
      aisles), a few only snacks or oil. The frozen set must not change; the
      exact subset falls out of the labels (a photo with no named can or glass
      bottle), so the evaluation script counts it rather than an eyeball.
- [x] **3. Label the test set: one pass, brand level.** Decided 2026-09-27: one
      labeler, so one pass (fix YOLO26l's boxes and name the drinks on the
      same visit), and brand + pack type labels, no flavours
      (`scope.yaml` `detail: brand`, 7 labels). Runbook:
      `docs/PILOT_LABELING.md`. Take the three labeling-guide screenshots on
      the way (the last Phase 0 item). **On the server since 2026-09-27:**
      project `pilot-test-cans-glass` (id 3), 30 tasks, 2,814 pre-drawn boxes,
      created by `uv run shelf-ls-setup`. 3 of 30 labeled (#04, #06, #22),
      and their screenshots are the guide's examples: Phase 0 closed.
      **2026-09-28: all 30 submitted.** **2026-09-29: naming passed** by
      decision: grey `product` boxes stay grey (only the pilot's number
      ignores them; they remain detector ground truth), and only targeted
      competitors need names. **Remaining:** add the 10 targeted-competitor
      labels, one rename pass over the 132 `COMPETITOR_*` boxes plus any
      targeted can or bottle still grey, the hygiene items in
      `docs/reports/2026-09-28_test_set_label_review.md` §2, the **face audit** (are the boxes
      faces? `docs/ISSUE_FACES_NOT_OBJECTS.md` §7), then the final
      export. Plan: `.hermes/plans/2026-09-29_pilot-parallel-tracks.md`.
      **2026-09-30: labels frozen as v1** (all objects, rename pass done):
      `data/label_studio/FROZEN.md`. The project is never edited again; the
      face audit is done in a separate copy project and saved as v2.
      **Done as v1.** The face audit is still open (standing issue).
- [x] **3b. Gold validation set.** About 30 photos from **val-split** stores,
      labeled exactly like the test set (same guide, same scope labels). It is
      what weekly tuning, model comparison and vendor scoring run on, so the
      frozen test set is only read to confirm (`LABELING_STRATEGY.md` §8).
      Needed before the first training round (6b) and before any vendor batch.
      - Pick with the same `diverse_sample` logic as the test set, but
        written to a new file, `data/splits/gold_val.txt`, tracked in git.
        Needs a small addition to `make_splits.py`; **never** via
        `shelf-splits --force`. Contact-sheet it and swap non-shelf photos,
        as was done for the test set.
      - Tag **scene type** on every gold and test photo: open fridge,
        glass-door fridge, aisle, counter, small shop. It is recorded
        nowhere today and every slice needs it. Add it as a single-choice
        field in the Label Studio config. Resolution tier comes from the
        manifest, so it needs no tag.
      - Load it as its own Label Studio project, so its tasks never mix with
        training batches.
      **Done 2026-10-05:** project `pilot-gold-val` (id 5), 30/30 labeled
      with scene/capture/photo-issue fields, export
      `data/label_studio/exports/gold-val-2026-10-05.json`, 1,970 boxes.
      List sha `71c7f434c344`. Scene tags exist on gold only; the frozen
      test set has none.
- [x] **4. Gallery for the in-scope classes.** Invoice images in
      `configs/Product/from_invoice/` (about 2 per SKU) plus crops from labeled
      non-test photos. Targeted competitors need a gallery too (2026-09-29):
      the matcher has to name them. Untargeted ones need none: not ours and
      not targeted = not counted.
      **2026-10-04:** the 10 tracked-competitor folders are generated from
      config by `uv run python scripts/make_gallery_folders.py` (`--check`
      reports what is still empty), each with a README of what belongs in it;
      index and Persian brand names in `configs/Product/competitors/README.md`.
      Waiting on the packshots themselves (you); at least 2 per folder, never
      crops from the frozen test set.
      **Filled 2026-10-04/05:** 9 of 10 folders, 154 images
      (Laimon-Fresh_glass retired). Cleanup of a few bad images is optional
      (demo-path T1).
- [x] **4b. Embedding matcher.** Embed each crop (DINOv2 or CLIP), take the
      nearest gallery match, and call it not-ours below a similarity
      threshold. This is the identifier half of the two-stage design; without
      it nothing names a crop outside Label Studio. Tune the threshold on
      non-test crops only.
      **Built 2026-10-05** (`src/face_counter/identification/`, `shelf-match`):
      DINOv2, threshold tuned on gold. Identity accuracy is **weak, 65.3%**;
      next experiment is SKU-level galleries (demo-path T3/T5).
- [x] **5. Can vs glass for non-ours crops.** Nothing in the plan does this
      yet, and the per-category share needs it. Cheapest candidates:
      zero-shot text match ("a can" vs "a glass bottle"), or YOLOE's own
      `can`/`bottle` prompt labels.
      **Done 2026-10-05:** CLIP ViT-L/14, ensemble prompts, AUC 0.985 / acc
      93.8% on gold human boxes (never measured on detector boxes: issue #2).
      Off by default in serving (ADR-0002).
- [~] **6. Evaluation script.** Implements the metric tables in
      `docs/reports/2026-09-27_detector_step_zero.md` §7. Per category:
      share-of-shelf error, the ours-vs-competitor confusion both ways (the
      error that moves the number), and detector recall on drinks.
      **2026-09-30: `uv run shelf-eval --labels <export> --detections <jsonl>`**
      (`src/face_counter/evaluation/`) scores every bake-off detector and
      computes the ground-truth share per category, both denominators
      (`share_against` in `scope.yaml` picks the headline). Brands, tracked
      competitors and categories are read from config only; a test proves
      that adding a tracked competitor is a config edit that changes the
      number. An unknown label stops the run instead of dropping out of the
      share. Still to come: share error and the ours-vs-competitor confusion,
      which need the matcher (4b) to produce predicted names.
      **Amended 2026-09-30 (standing issue):** detector recall and precision
      are scored against *faces*, and a behind false-positive rate is added;
      the all-object numbers stay as a diagnostic column. This needs a
      face/behind field in the label parser (`ls_export.py`).
      **2026-10-05:** `shelf-eval --predict` gives predicted share and its
      error (demo-path T5: cans -37.6 pp, glass -26.9 pp on v1). Still open:
      the face/behind scoring above.
- [~] **6b. Fine-tune and re-score, in weekly rounds.** Label a training batch (never test
      stores), fine-tune the leading candidates (YOLO26, RF-DETR, DEIM-D-FINE),
      and score them on the same test set, on face metrics. Labels are
      face-only and no raw SKU-110K annotations go in (standing issue).
      Zero-shot results do not rule any
      model out. Training batches were not hand-reviewed the way the test
      set was: expect a few non-shelf uploads under `photo_type: shelf`
      (screenshots, storefronts; 9 PNGs in the corpus). Give labelers a
      "not a shelf photo, skip" answer before the batch goes out
      (`PHASE0_REMAINING.md` §2). The round-by-round loop (batch choice,
      capacity, vendors, stopping rule) is `LABELING_STRATEGY.md` §8.
      **Started:** batches 01-05 (`data/splits/label_batch_0N.txt`, 250
      photos each) are Label Studio projects 6-10; 232/1,250 submitted on
      2026-10-26. No training round yet. Status and review findings:
      `docs/vault/Findings/2026-10-26 Training batch labeling status.md`.
      Before round 1: set up MLflow on the GPU PC (local, SQLite, ~half a
      day; ROADMAP MLflow item) so round 1 is the logged baseline.
- [~] **7. Phase 2, narrowed.** `/count` and `/overlay` for the two
      categories, per `ROADMAP.md`.
      **2026-10-10/11:** service built and deployed, scope cut to
      detection-only (per-category share behind `debug=true` until identity
      improves); upload page at `/`. Hosting decision and hardening open
      (demo-path T7, issues #6, #8).
- [~] **8. The extensibility test.** Add a category (e.g. `oils`) or a
      named competitor to the scope, and record what else had to change.
      Findings so far:
      - 2026-09-29, named competitors: `taxonomy.problems()` rejected any
        brand other than `COMPETITOR` with `is_ours=0`, and `scope.yaml` had
        no way to list competitors. Both needed a code change (small, but
        code). Adding a *further* targeted competitor is now config only.
      - 2026-10-04, retiring a tracked label (`Laimon-Fresh_glass`): the scope
        had no way to drop one pack type of a tracked brand, so it needed a
        small code change (`retired:` in `scope.yaml`, read by `load_scope`,
        `targeted_label_names`, `Taxonomy.resolve`). Existing labels are not
        relabeled: the frozen v1 export is untouched and its 9 boxes are read as
        grey `product`. Retiring a label is now config only.
      - 2026-09-29: the 132 boxes already labeled `COMPETITOR_*` needed a
        rename pass, because the category label had mixed targeted and
        untargeted brands. Future named competitors will need the same pass
        over `COMPETITOR_*` boxes; no box is redrawn.

## Deferred, not dropped

Corpus-scale cluster labeling (only a small version for gallery crops is
needed now), the full-class confusion matrix, oils and dressings (we have no
products of ours there yet), all non-drink categories.

Open question carried from Phase 0: `classes.csv` has no oil or dressing
products of ours (the only `sauce` rows are Tommy-Joy dessert sauces). Either
they are on another invoice, or those categories are competitor-only today.
Ask before widening the scope to them; adding them is `source=manual` rows
with `pack_type` `oil`/`dressing`, no code change.
