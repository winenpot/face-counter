# Detector step zero: report and evaluation plan

Date: 2026-09-27. Scope: two-brand drinks pilot (Kix-Max, TorshX; cans and glass
bottles, reported separately).

## 1. What was done

Three publicly available detectors were run, **as downloaded, with no training on
our data and no labels**, over the frozen 30-photo test set on the GPU box
(RTX 4060 Ti, input size 1280, confidence threshold 0.25).

| Model | Trained on | Type |
| --- | --- | --- |
| sku110k-yolo11s | SKU-110K (retail shelves) | YOLO11 small, single class "object" |
| detr-r50-sku110k | SKU-110K (retail shelves) | DETR ResNet-50, max 400 boxes per photo |
| yoloe-26s | General web data | Open-vocabulary, finds objects from text prompts |

This step does **not** pick the final detector. It picks which model pre-draws
boxes for the labelers, so labeling is faster. Every candidate is re-evaluated
after it is fine-tuned on our own labeled photos.

## 2. Measured results (no ground truth yet)

| Metric | sku110k-yolo11s | detr-r50-sku110k | yoloe-26s |
| --- | --- | --- | --- |
| Boxes, all 30 photos | 2,319 | 5,545 | 1,466 |
| Boxes per photo, median (min-max) | 69.5 (15-218) | 183.5 (51-396) | 40.5 (1-134) |
| Share removed as overlapping duplicates | 4% | 24% | 6% |
| Photos with 3 boxes or fewer | 0 | 0 | 2 |
| Inference time per photo, median | 0.05 s | 0.06 s | 0.06 s |

YOLOE labeled its boxes as: bottle 1,370, carton 64, juice box 16, packet 13,
box 3, **can 0**, although "can" was one of its prompts.

## 3. Visual review of the overlays

- **sku110k-yolo11s:** good coverage on dense drink fridges (209 boxes on a full
  fridge photo, nearly all on real products). Some duplicate boxes, boxes on dark
  empty areas, and boxes on reflections in fridge glass.
- **detr-r50-sku110k:** highest coverage, but many stacked duplicates. DETR does not
  remove duplicates by itself; that step was not applied. It also reached 396 of its
  400-box limit on one photo.
- **yoloe-26s:** reliable on bottles, weak on cans, and found 1 box on a fridge full
  of drinks. The likely cause is the prompt wording ("can" is ambiguous), not the
  architecture; this is being retested with reworded prompts.

## 4. Interpretation

- These are **zero-shot** results. They are not overfitting or underfitting in the
  training sense: none of the models has seen our data. The differences are a
  trade-off between catching everything and producing extra boxes.
- For pre-labeling, extra boxes are cheaper than misses: a labeler deletes a wrong
  box in about a second, but must draw a missed one, and misses are easy to overlook.
- **Working choice for pre-labeling: sku110k-yolo11s.** Fewest duplicates with good
  coverage on dense fridges. To be confirmed against YOLO26 (below).

## 5. Limitations

- No labels yet, so no accuracy numbers: no recall, precision or mAP.
- Confidence scores are not comparable between models.
- 30 test photos; a subset of them contains drinks.

## 6. Next steps

1. Run YOLO26l trained on SKU-110K (added; designed to avoid duplicate boxes) and
   YOLOE with reworded prompts.
2. Confirm the pre-labeling model.
3. Label the test set (pass 1: every product box; pass 2: name cans and glass bottles).
4. Score every candidate with the metrics below.
5. Label a training batch (never test-set stores) and fine-tune the leading
   candidates: YOLO26, RF-DETR, DEIM-D-FINE. Score them again on the same test set.

## 7. Evaluation metrics

Detection is scored by first **matching** each predicted box to a labeled box.
Two boxes match when their overlap, **IoU** (area of intersection / area of union),
is at least 0.5. After matching, each predicted box is a true positive (TP) or a
false positive (FP), and each unmatched labeled box is a false negative (FN).
There are no true negatives (empty background is not counted), so ROC and AUC do
not apply; the precision-recall curve replaces them.

### Stage 1: detector (finds every product)

| Metric | Measures | Computed as | Why it matters here |
| --- | --- | --- | --- |
| Recall @ IoU 0.5 | Share of real products found | TP / (TP + FN) | **Primary.** A missed product shrinks the share-of-shelf total |
| Precision @ IoU 0.5 | Share of boxes that are real products | TP / (TP + FP) | Extra boxes cost labeler time and inflate totals |
| F1 @ IoU 0.5 | Balance of the two | 2PR / (P + R) | One number per model at a fixed threshold |
| AP50 | Precision-recall trade-off over all thresholds | Area under the precision-recall curve at IoU 0.5 | Standard, threshold-free comparison |
| AP50-95 | Box tightness | AP averaged over IoU 0.50 to 0.95 | Tight boxes give clean crops for identification |
| Count error | Accuracy of the product count | Mean absolute error of boxes vs labeled products per photo | Share of shelf is built on counts |
| Duplicate rate | Same product boxed more than once | Extra predictions matching an already-matched product / all predictions | The overlap problem seen in the overlays |
| Recall by slice | Where it fails | Recall per slice: fridge vs aisle, glare, crowding, resolution | An average can hide a failure on fridges |

### Stage 2: identifier (names each box)

| Metric | Measures | Computed as | Why it matters here |
| --- | --- | --- | --- |
| Confusion matrix | Which products get mixed up | Predicted vs true class, on correctly found boxes | Shows the look-alike pairs |
| Precision, recall, F1 per class | Per-product quality | Standard classification | Macro-average so rare products count |
| Ours-vs-competitor confusion | Our product called a competitor, and the reverse | 2x2 matrix on found boxes | **The error that moves the share-of-shelf number** |
| Can vs glass accuracy (competitors) | Correct category for non-ours boxes | Accuracy on competitor boxes | Needed for the per-category share |

### Business output

| Metric | Measures | Computed as | Why it matters here |
| --- | --- | --- | --- |
| Share-of-shelf error, per category | Accuracy of the reported number | Mean absolute difference, predicted vs labeled share, in percentage points | **What the business reads** |
| Brand count error | Per-brand counts | Mean absolute error of faces per brand per photo | Business-readable ("off by X faces") |
| Confidence interval | How certain the number is | Bootstrap over test photos | 30 photos make small differences noise |

### Operational

| Metric | Measures | Why it matters here |
| --- | --- | --- |
| Inference time per photo | Speed | CPU deployment on the server |
| Maximum boxes per photo | Hard cap | Dense shelves reach about 500 products |
| Labeler corrections per photo | Boxes added and deleted when fixing pre-drawn boxes | The real cost of the pre-labeling choice |
