# Pilot: two brands, cans and glass bottles

**Start here when you pick the project up.** This is the active slice of the
work and its ordered to-do list. `ROADMAP.md` still holds the full,
horizontal plan; nothing in it is cancelled, only sequenced after this.

## Scope (decided 2026-09-27)

- **Question:** what share of all cans, and separately of all glass bottles,
  on a shelf are ours?
- **Brands reported:** Kix-Max and TorshX, named by brand and pack type only
  (`Kix-Max_canned`), not by flavour.
- **Categories:** `canned_drinks` and `glass_drinks`, reported **separately**.
  Glass means glass only; plastic bottles are not in either.
- Lives in `configs/scope.yaml`. It is a filter over the full taxonomy
  (`classes.csv`, `reporting.yaml`), never a fork of it.

Three rules keep the pilot from closing off the wider system:

1. **Every can and glass bottle is named, whoever makes it.** A can of
   another brand of ours is labeled as ours even when that brand's share is
   not reported. Calling it a competitor would corrupt the denominator.
2. **Boxes outside the scope keep the label `product`** ("not identified
   yet"), never `out_of_scope`. A later scope names them; nothing is
   relabeled. Pass one (geometry) still boxes every product on the shelf.
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
- [ ] **3. Label the test set: one pass, brand level.** Decided 2026-09-27: one
      labeler, so one pass (fix YOLO26l's boxes and name the drinks on the
      same visit), and brand + pack type labels, no flavours
      (`scope.yaml` `detail: brand`, 7 labels). Runbook:
      `docs/PILOT_LABELING.md`. Take the three labeling-guide screenshots on
      the way (the last Phase 0 item). **On the server since 2026-09-27:**
      project `pilot-test-cans-glass` (id 3), 30 tasks, 2,814 pre-drawn boxes,
      created by `uv run shelf-ls-setup`. Labeling itself not started.
- [ ] **4. Gallery for the in-scope classes.** Invoice images in
      `configs/Product/from_invoice/` (about 2 per SKU) plus crops from labeled
      non-test photos. Competitors need no gallery: not ours = competitor.
- [ ] **5. Can vs glass for non-ours crops.** Nothing in the plan does this
      yet, and the per-category share needs it. Cheapest candidates:
      zero-shot text match ("a can" vs "a glass bottle"), or YOLOE's own
      `can`/`bottle` prompt labels.
- [ ] **6. Evaluation script.** Implements the metric tables in
      `docs/reports/2026-09-27_detector_step_zero.md` §7. Per category:
      share-of-shelf error, the ours-vs-competitor confusion both ways (the
      error that moves the number), and detector recall on drinks.
- [ ] **6b. Fine-tune and re-score.** Label a training batch (never test
      stores), fine-tune the leading candidates (YOLO26, RF-DETR, DEIM-D-FINE),
      and score them on the same test set. Zero-shot results do not rule any
      model out.
- [ ] **7. Phase 2, narrowed.** `/count` and `/overlay` for the two
      categories, per `ROADMAP.md`.
- [ ] **8. The extensibility test.** Add a category (e.g. `oils`) or a
      named competitor to the scope, and record what else had to change.

## Deferred, not dropped

Corpus-scale cluster labeling (only a small version for gallery crops is
needed now), the full-class confusion matrix, oils and dressings (we have no
products of ours there yet), all non-drink categories.
