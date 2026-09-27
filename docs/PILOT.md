# Pilot: two brands, cans and glass bottles

**Start here when you pick the project up.** This is the active slice of the
work and its ordered to-do list. `ROADMAP.md` still holds the full,
horizontal plan; nothing in it is cancelled, only sequenced after this.

## Scope (decided 2026-09-27)

- **Question:** what share of all cans, and separately of all glass bottles,
  on a shelf are ours?
- **Brands reported:** Kix-Max and TorshX (27 of our classes).
- **Categories:** `canned_drinks` and `glass_drinks`, reported **separately**.
  Glass means glass only; plastic bottles are not in either.
- Lives in `configs/scope.yaml`. It is a filter over the full taxonomy
  (`classes.csv`, `reporting.yaml`), never a fork of it.

Three rules keep the pilot from closing off the wider system:

1. **Every can and glass bottle is named, whoever makes it.** Bomb's energy
   drink is ours, so it is labeled as ours, even though Bomb's share is not
   reported yet. Calling it a competitor would corrupt the denominator.
2. **Boxes outside the scope keep the label `product`** ("not identified
   yet"), never `out_of_scope`. A later scope names them; nothing is
   relabeled. Pass one (geometry) still boxes every product on the shelf.
3. **Extensibility is the experiment.** Widening the scope (add Bomb, a
   category, a named competitor) must only touch `scope.yaml`,
   `classes.csv`, `reporting.yaml` and gallery images. If it needs code or a
   relabel, write down where; that is the finding.

## To do, in order

- [x] **Scope config and scoped labeling.** `configs/scope.yaml`;
      `uv run shelf-label-prep --list data/splits/test_labeling.txt --level scope`
      emits the 31-label identity-pass config (our 28 in-scope classes incl.
      Bomb, `COMPETITOR_canned`, `COMPETITOR_glass`, `product`).
- [~] **1. Pick the detector that pre-draws boxes.** Zero-shot run and visual
      review done 2026-09-27; report and metric plan in
      `docs/reports/2026-09-27_detector_step_zero.md`. Working choice:
      `sku110k-yolo11s`. Still to run on the GPU box before confirming:
      `yolo26l-sku110k` (download its weights first, see `configs/bakeoff.yaml`)
      and `yoloe-26s` with reworded can prompts (`--yoloe-prompts`). This picks
      the labeling assistant only; every candidate is re-scored after
      fine-tuning. **This blocks everything below.**
- [ ] **2. Count the drink photos in the test set.** Some of the 30 are candy
      aisles. The frozen set must not change, so report the pilot on the
      subset that contains cans or glass bottles and say how many that is
      (expect 15-20, so noisier numbers).
- [ ] **3. Label the test set, two passes.** Pass one: every product, one
      label, pre-filled with the chosen detector's boxes (`shelf-bakeoff`
      already writes `ls_predictions_<model>.json`). Pass two
      (`--level scope`): name cans and glass bottles only. Take the three
      labeling-guide screenshots from a drinks fridge.
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
- [ ] **8. The extensibility test.** Add Bomb to `scope.yaml` `brands`, and
      record what else had to change. Then try a named competitor.

## Deferred, not dropped

Corpus-scale cluster labeling (only a small version for gallery crops is
needed now), the full-class confusion matrix, oils and dressings (we have no
products of ours there yet), all non-drink categories.
