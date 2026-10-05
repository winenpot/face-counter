# Session Summary — 2026-10-05

Read this tomorrow to pick up where we left off. Everything is committed and
pushed (master @ 891524c == origin/master == hemin).


---

## What this project does (one paragraph)

A two-stage system for shelf photos: Stage 1 detects every product face
(a bounding box), Stage 2 identifies each face by nearest-match against a
reference gallery of packshots. The output is "share of shelf" — what fraction
of canned drinks (and glass drinks, separately) belong to Kix-Max or TorshX
vs. the tracked rivals we care about. Everything flows through a FastAPI
service eventually, but that part is not built yet.


---

## Repo layout (what's where)

    src/face_counter/
      evaluation/       shelf-eval CLI — detector scoring + ground-truth share
      identification/   NEW this session — gallery, embedder, matcher, pack_type, predict
      training/         shelf-bakeoff CLI — run detectors, produce detections.jsonl
      utils/            taxonomy, config helpers
    configs/
      scope.yaml        which brands and categories are active RIGHT NOW
      classes.csv       every product and competitor with brand/pack_type/is_ours
      reporting.yaml    category definitions (canned_drinks, glass_drinks, ...)
      Product/          gitignored packshots (from_invoice/, competitors/)
    data/
      raw/images/       gitignored shelf photos
      label_studio/exports/  gitignored Label Studio exports
    runs/               gitignored outputs (bakeoff, eval, match)
    scripts/            one-off helper scripts
    tests/              176 tests, all pass, all offline


---

## What was done today (three tasks, all committed)

### T3 — Embedding matcher (commit b114061)

Built src/face_counter/identification/:

- gallery.py    — loads packshots from configs/Product/from_invoice/ (ours,
                  brand-level) and configs/Product/competitors/<label>/ (rivals)
- embedder.py   — DINOv2 (facebook/dinov2-base), L2-normalised vectors
- matcher.py    — nearest cosine, configurable threshold, threshold sweep tuner
- pack_type.py  — CLIP ViT-L/14 "ens"-prompt can-vs-glass classifier (T4's
                  promoted model), for boxes the matcher doesn't name
- cli.py        — shelf-match gallery (list what's in the gallery)
                  shelf-match tune --labels ... (embed + tune threshold)
19 offline tests. All heavy model calls mocked.

Real GPU run on hemin (188 gallery images, 245 named gold crops):
  Threshold accuracy:  92.2% @ 0.0625   (0 named crops missed, 19/20 grey
                                          untargeted false-accepted)
  Identity accuracy:   65.3%             (147/225 right brand+pack)

Confusions: TorshX_glass -> TorshX_canned (x11), Kix-Max_canned -> TorshX_canned
(x6), glass-brand mix-ups. Root cause: brand-level galleries pool every
flavour/angle; DINOv2 sees the brand's look but not the container.
Not a code bug — the arithmetic is right, the embedding space is the problem.


### T5 — Predicted share wired into shelf-eval (commits e71c673, da751a0, 891524c)

Built src/face_counter/identification/predict.py:
  predict_photos() — crop boxes from images, embed all at once, match gallery,
  classify unmatched with CLIP can/glass. Returns Photo objects with the same
  GT metadata so share.evaluate() can compare apples-to-apples.

Extended src/face_counter/evaluation/cli.py with --predict flag:
  shelf-eval --labels ... --detections ... --predict --images-dir ... \
             --match-threshold 0.0625 --device cuda
  Writes predicted_share.csv + predicted_share_per_photo.csv and adds a
  GT-vs-predicted comparison table to summary.md.

8 new offline tests. 176 total, all passing.

Real GPU run on hemin (gold set, 30 photos, 2,457 detector boxes):

  FIRST RUN (threshold 0.0625, tuned only on named crops):
    canned_drinks: GT share 69.0%  →  predicted 31.4%  (-37.6 pp)
    glass_drinks:  GT share 29.8%  →  predicted  2.9%  (-26.9 pp)
  Root cause found: 0.0625 was calibrated on 245 named crops. The full
  detector fires 2,457 boxes — 1,725 grey "product" boxes that should NOT
  match anything. At 0.0625 almost everything matched, flooding the
  denominator.

  FIX: shelf-match tune --include-product-boxes added (includes grey boxes
  in the tuning signal as should_not_match). Re-tuned: threshold → 0.7115.

  SECOND RUN (threshold 0.7115, tuned on full box set):
    Only 27 of 225 named crops clear 0.7115 (12% recall).
  Root cause exposed: DINOv2 similarity between shelf crops and clean packshots
  rarely exceeds 0.7. The threshold fix was right — it just revealed the
  deeper problem, which is embedding separability, not calibration.


---

## Where things stand right now

The pipeline is architecturally correct and fully wired. The predicted share
is not demo-ready. The gap is: DINOv2 cosine similarity between a shelf crop
(small, blurry, reflective, angled) and a packshot (clean marketing image) is
too low to separate reliably at any threshold.

Three paths to fix it, cheapest first:

  (a) SKU-level galleries — instead of one pool per brand+pack, one pool per
      flavour. More reference vectors, finer coverage. gallery.py's docstring
      has the one-line change. No label work. Try this first.
      Command to test: in gallery.py, don't roll up class_name to brand+pack.
      Then re-run shelf-match tune --include-product-boxes and check if
      threshold accuracy improves with less recall penalty.

  (b) More/better gallery images — more angles, lighting conditions per SKU.
      No label work, just collecting images. Would help any backbone.

  (c) Fine-tuning / domain adaptation — train or adapt the embedding model on
      shelf-crop vs. packshot pairs. T8 scope. Real work.

The demo can still be shown with ground-truth share (shelf-eval without
--predict) which is solid: canned 69%, glass 29.8%, with 95% CIs. The
"predicted" pipeline exists but reports meaningless numbers until (a) or (b).


---

## Decision needed at the start of tomorrow

Before T6 (FastAPI service): try option (a) SKU-level galleries.
It takes maybe 30 minutes to test (one gallery.py change + one hemin run).
If the numbers improve, the demo is real. If they don't, we know (b)/(c) are
needed and we can proceed to T6 anyway with GT-share-only.

Ask: "Try SKU-level galleries before T6?" and go from there.


---

## Current state of every task

  [x] T1  Detector bakeoff — yolo26l-sku110k picked, recall 0.87
  [x] T2  Gold validation labels — 30 photos, 1,970 boxes, exported + on hemin
  [x] T3  Embedding matcher — scaffolded, tuned, identity 65.3% (flagged weak)
  [x] T4  Can-vs-glass — CLIP ViT-L/14 ens-prompt, AUC 0.985 on gold, promoted
  [x] T5  Predicted share — wired, architectural gap found and documented
  [ ] T6  FastAPI service — not started
  [ ] T7  Docker on db server — not started
  [ ] T7b Harden hemin git access — not started (after T7)
  [ ] T8  Model quality / future work — not started


---

## Key numbers to remember

  Gold export:      30 photos, 1,970 boxes, sha256 44e316ae...1d44d
                    data/label_studio/exports/gold-val-2026-10-05.json
  Ground-truth share (gold set):
    canned_drinks:  69.0%  (58 ours, 26 targeted, 95% CI 51–88%)
    glass_drinks:   29.8%  (42 ours, 99 targeted, 95% CI 15–44%)
  Detector recall:  96.5% (yolo26l-sku110k, biased upward — seed model)
  T4 can/glass:     AUC 0.985, acc 93.8% on gold rival boxes
  T3 threshold acc: 92.2% (0.0625 on named crops only)
                    89.8% (0.7115 on full box set — the right calibration)
  T3 identity acc:  65.3% (named crops only, brand-level galleries)
  T5 share error:   -37.6 pp canned, -26.9 pp glass (first run, now understood)


---

## Code entry points

  uv run shelf-eval  --labels ... --detections ...  (ground-truth share)
  uv run shelf-eval  --labels ... --detections ... --predict --device cuda (predicted)
  uv run shelf-match gallery                        (what's in the gallery)
  uv run shelf-match tune --labels ... --images-dir ... --include-product-boxes --device cuda
  uv run shelf-bakeoff                              (run detectors, GPU)
  uv run pytest                                     (176 tests, all offline)


---

## hemin notes

  SSH alias: hemin (192.168.1.221)
  uv: ~/.local/bin/uv  (not on PATH in non-interactive SSH)
  Code syncs via git only (git push + git pull on hemin), never rsync
  Gallery images sync via rsync (gitignored): configs/Product/competitors/
  Gold export syncs via scp: data/label_studio/exports/gold-val-2026-10-05.json
  Runs sync back via: bash scripts/sync_from_hemin.sh


---

Rest well.
