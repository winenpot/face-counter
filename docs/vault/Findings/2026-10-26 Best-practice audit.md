# 2026-10-26 Best-practice audit (web research vs this repo)

Three research passes (detection; product identification and commercial
share-of-shelf vendors; labeling, evaluation and serving), about 30 web
searches. Most sources were judged from search snippets, not read in full.
Preprints and vendor claims are marked. Verified link list:
[[2026-10-26 Audit sources]] (written separately; titles checked).

## Critical findings

1. **Served detector is not the scored detector.** The 0.87 recall came from
   Ultralytics' NMS-free path (`detector_bakeoff.py:149`, `MAX_DET = 1000`).
   Serving runs the ONNX export's raw per-anchor output `(1,5,33600)` through
   our own greedy NMS at IoU 0.45 (`onnx_detector.py:9-15,28`). No parity test
   exists. The "NMS-free by design" rationale (`detector_bakeoff.py:173`) does
   not hold for the deployed graph. Checked in code 2026-10-26; the size of
   any difference is unmeasured.
2. **Identity gap is packshot-to-shelf domain shift, not gallery granularity.**
   Literature fixes it with real shelf crops in the gallery and a
   metric-learning head on the embedder (ArcFace/triplet on frozen DINOv2),
   not with finer folders. The threshold dilemma (0.0625 matches all, 0.71
   keeps 12% of named crops) is an embedding-separability problem; grey boxes
   used as negatives include tracked products, so they are noisy negatives.
3. **Test labels do not support face metrics yet.** `FROZEN.md`: v1 boxes
   "every visible product", while the headline metric is face
   recall/precision. Face numbers on the test set wait on the v2 audit.

## Aligned (or beyond common practice)

Class-agnostic detection + open-set retrieval; counting facings, with a
behind-unit false-positive rate (beyond); store-level splits, frozen
checksummed test set, choose on gold / confirm on test, no-slice-regresses
rule (beyond); iterative pre-label/correct/retrain with a stop rule; active
learning planned with test and gold excluded; CLIP only for can vs glass;
ORT thread caps; idempotent async serving design (ADR-0003). Our evaluation
honesty exceeds published vendor claims (95-97%, unstated protocols).

## Gaps

Labeling and evaluation:
- No per-labeler check against known answers (gold/honeypot tasks), no
  edit-rate gate, no box-level agreement metric. The 14 zero-edit
  submissions are textbook automation bias. Agreement measures consistency,
  not correctness; correctness per labeler needs known-answer tasks.
- Pre-labels show only confident boxes, so the hard misses are exactly what
  labelers never see; with automation bias, training labels will be
  under-boxed. Missing boxes are the most harmful label error for detection.
- Bootstrap CIs are not resampled by store; the stop rule's "noise" is
  unmeasured.
- Docs disagree on the agreement study (5 photos in `LABELING_STRATEGY.md`,
  20 monthly in `ERROR_ANALYSIS.md`). The Label Studio Community re-decision
  (due once several labelers start) has not been made.
- Training-batch exports are not snapshotted with hashes; no per-labeler
  provenance column.

Detection:
- NMS IoU and confidence never swept against count error on our labels.
- RF-DETR authors hypothesise its regulariser needs more than 100 epochs on
  small datasets (arXiv 2511.09554, stated as a hypothesis, not measured);
  default 300 queries caps detections per photo. Our densest labeled photo
  has 236 boxes (v1 test set), so 300 is enough so far; raise it only if
  denser photos appear. The 6b plan records no epoch budget.
- SAHI tiling and the 1280 input size were never tested against count error
  (one unreviewed study found a larger input worsened counts via duplicates).
- Minor: facings share vs linear share not stated for BI.

Identification:
- Frozen embedder, no metric-learning fine-tune; galleries mostly packshots.
- No pack-type constraint on matching, though most confusions cross pack
  type and can/glass is already AUC 0.985 on gold.
- No OCR / text cue (Unitail, vendors treat it as core; Persian brand names
  should help). No shelf-context smoothing. No synthetic data.
- Roadmap's later ~400-class closed classifier conflicts with SKU churn;
  literature prefers fine-tuned retrieval.

## Recommendations, by value for effort

1. Detector parity test (ONNX+NMS vs Ultralytics) on the 30 test photos, then
   sweep NMS IoU and confidence on gold against count error. (Plan T9.)
2. Labeler quality control: hidden gold photos per batch, per-labeler scores
   on misses / extras / names, bounce zero-edit photos, box-level agreement
   on 10-20 shared photos. (Plan T10.)
3. Identity: restrict matching to the predicted pack type's gallery; then
   named shelf crops in the galleries, per-class scoring. (Plan T11.)
   Update: only 20 of the 78 baseline errors cross pack type, so the pack
   filter's ceiling is 74.2% (from 65.3%). Shelf crops and a metric-learning
   head are the bigger levers.
4. Metric-learning head on frozen DINOv2 (validate on gold only); then OCR
   re-ranking of top-k.
5. Store-level bootstrap; hashed snapshot of every batch export before
   training; epoch/query budget in the RF-DETR/DEIM configs.

## Cat2Real (arXiv 2607.09888), read in full 2026-10-27

Walmart Global Tech, July 2026 preprint (not peer reviewed). Fine-tunes
DINOv2/v3 with a triplet loss on pairs (real shelf crop, its catalog
packshot) against the closest wrong product, in three stages.

- Reported: 80.73% top-1 / 94.70% top-5 (DINOv3-384) on an in-house set of
  5,043 shelf crops searched against 2,155 products. Not reproducible
  outside Walmart.
- Data: 196,531 labeled shelf crops, 409,891 catalog images, 45,243
  products, one A100. Smallest experiment: 68,407 crops (75.8% top-1).
- Off-the-shelf DINOv2 ViT-L/14 scored 35.5% on their task; Cat2Real-DINOv2
  76.3%. The gain comes from training on labeled real crops, not from the
  packshots themselves.
- "No retraining as inventory changes": with all test products removed from
  training, 80.23% vs 80.73%. That transfer is learned from 43k other
  products; scale is the precondition.
- What mattered (ablations): hard-negative sampling from similar products
  (-5.9 pts without), three-stage curriculum (73.8 -> 78.5 -> 80.7),
  dynamic closest-image selection, low-quality crop filter (~-1.2 pts
  without), single hard negative better than random or four.

What it means here:
- Our packshots alone already gave 65.3%; packshots are the gallery side,
  the fuel is named shelf crops. Training batches yield ~7.6 named crops per
  photo: ~2,500 from the 337 photos done by 2026-10-27, ~9,500 at 1,250.
- For us: ~16 brand+pack classes vs their 2,155 products, and our errors are
  exactly look-alike brands (hard-negative territory). Against us: 10-30x
  less data than their smallest run, ~2 low-res invoice images per SKU
  (some 148 px), labeler naming errors become wrong training pairs, GPU box
  required. Not comparable numbers: different task and test set.
- Expected gain is unmeasured. Cheapest test (T11 step): triplet head on
  frozen DINOv2-base, positives = named crops from cleaned batch-01/03
  exports + their packshots, negatives mined from our confusion pairs,
  scored on the 225 gold crops vs 65.3%. About a day on the GPU box.
