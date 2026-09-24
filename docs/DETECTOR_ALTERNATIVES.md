# Detector alternatives — the knobs we deliberately left reachable

Survey date 2026-09-24. Everything here is stage 1 only: *find every product*,
don't name it. Naming is the embedding gallery's job (see `ROADMAP.md`).

The roadmap says "train a small YOLO on SKU-110K". That is a **starting point,
not a conclusion**. This document exists so that the day someone asks "could we
do better?", the answer is a config change and an evaluation run, not a
research project.

---

## First, two things the roadmap's phrasing hides

**SKU-110K is a dataset, not a model.** Goldman et al., CVPR 2019, *Precise
Detection in Densely Packed Scenes*. ~11,700 shelf photos, ~1.7M boxes,
averaging ~150 objects per image. It exists because normal detection benchmarks
(COCO) have a handful of large objects per photo and shelves have hundreds of
small, near-identical, tightly packed ones — a different problem wearing the
same name.

**SKU-110K is single-class.** Every box is labelled `object`. The "110K" counts
the distinct SKUs the photos happen to contain, *not* labels you receive. It
will never tell you which product a box holds.

That second fact is easy to misread as a limitation. It is the opposite — it is
precisely why the dataset fits: it solves stage 1 completely and demands zero
labelling from us, while leaving stage 2 (which is where our 103 classes and
our competitive advantage live) entirely to the gallery. If SKU-110K did hand us
110K usable classes, our whole two-stage design would be unnecessary.

---

## The landscape, and why it moved

For roughly 2016–2023 the practical answer to "fast detector" was some YOLO.
DETR (2020) was more accurate in principle — set prediction, no NMS, no anchors
— but converged so slowly (500 epochs) that nobody with one GPU could use it.

That objection has been dismantled, in three steps, and this is the part worth
understanding rather than just tabulating:

**RT-DETR** (Baidu, Apr 2023, Apache-2.0) made a DETR real-time. Its trick is a
hybrid encoder that *decouples* intra-scale attention from cross-scale fusion,
so multi-scale features stop costing quadratic attention over every level.
RT-DETR-L: 53.1% AP @ 108 FPS (T4), beating comparable YOLOs at similar speed.

**D-FINE** (USTC, Oct 2024) attacked *localisation*. Instead of regressing four
fixed coordinates, it predicts a **probability distribution** over coordinate
offsets and iteratively sharpens it through the decoder layers
("Fine-grained Distribution Refinement"). A second idea, Global Optimal
Localization Self-Distillation, pushes the refined deep-layer localisation
knowledge back into earlier layers. Neither costs anything at inference.
D-FINE-L: **54.0% AP @ 124 FPS**; D-FINE-X: 55.8% @ 78 FPS. With Objects365
pretraining, 57.1% / 59.3%.

Why this matters to us specifically: a distribution over box edges is a better
fit for *ambiguous* boundaries — which is exactly what the seam between two
identical cans touching on a shelf is. A point estimate has to commit; a
distribution can be honestly uncertain, and that uncertainty is also a free
active-learning signal (see `ERROR_ANALYSIS.md`).

**DEIM** (CVPR 2025, Apache-2.0) attacked *training cost*, and is the reason
this document exists. It is not an architecture — it is a training framework you
drop onto RT-DETRv2 or D-FINE, changing nothing at inference. DETR's one-to-one
matching assigns exactly one prediction per ground-truth box, which starves the
model of positive samples. DEIM's **Dense O2O** manufactures more targets per
image via standard augmentation, then **Matchability-Aware Loss (MAL)**
down-weights the low-quality matches that densification inevitably creates.

Results:
- **~50% less training time** on top of RT-DETRv2 and D-FINE, for *better* AP.
- RT-DETRv2 to **53.2% AP in a single day on one 4090**.
- DEIM-D-FINE-L: **54.7% AP @ 124 FPS**, beating YOLOv11-X (54.1%) while being
  20% faster.
- **Largest gains are on small objects** — +1.5 AP for D-FINE-X.

Read the last two bullets against our situation. Our hardware is one 4060 Ti
(same class as the 4090 in that claim, slower but not categorically different).
Our failure mode is small, densely packed objects. DEIM's headline strength and
our headline weakness are the same axis, and the training-cost objection that
made us pick YOLO in the first place is the specific thing DEIM removes.

**DEIMv2** (Sept 2025) adds DINOv3 backbones and ultra-light Pico/Femto/Atto
variants for edge deployment — potentially relevant to our CPU-capped serving
box, unverified.

---

## The candidates

| Model | License | Why we'd pick it | Why we might not |
| --- | --- | --- | --- |
| **YOLOv8 / v11 (Ultralytics)** | **AGPL-3.0** | Best-documented ONNX + SAHI path; overwhelming community support; fastest route to a baseline | AGPL; no longer the accuracy leader |
| **YOLOX / YOLOv7** | Apache-2.0 / GPL | Licence escape hatch if AGPL is refused | Older, weaker, less tooling |
| **RT-DETR / v2** | Apache-2.0 | NMS-free, strong on dense scenes, permissive | Heavier CPU inference than YOLO |
| **D-FINE** | check | Best accuracy/latency trade in the real-time class; distributional boxes suit ambiguous shelf seams | Newer, thinner tooling |
| **DEIM(-D-FINE)** | **Apache-2.0** | SOTA real-time; halves training cost; **best-in-class on small objects**; fits one GPU overnight | Newest; ONNX-on-CPU path unproven for us |
| **DEIMv2** | check | DINOv3 backbones; Pico/Femto/Atto for edge/CPU | Very new, unverified |
| **Co-DETR / DINO-DETR** | varies | Accuracy ceiling reference | Far too heavy for 4 CPU cores |

## The shortcut we should try before training anything

Published SKU-110K checkpoints already exist. Evaluating them costs an
afternoon; training costs a night plus setup. **Step zero of Phase 1 is a
bake-off of existing weights on our frozen test set.**

| Checkpoint | Reported | Note |
| --- | --- | --- |
| `isalia99/detr-resnet-50-sku110k` (HF) | **58.9 mAP** on SKU110K val | DETR, 400 queries — **trained on a 4060 Ti**, i.e. our exact hardware |
| Ultralytics platform, YOLO26l SKU-110K | **0.906 mAP50 / 0.548 mAP50-95** | Described by its author as the detect stage feeding an embedding gallery — literally our architecture |
| `Media-Smart/SKU110K-DenseDet` | — | mmdetection v1.0rc1 era; old stack |
| `eg4000/SKU110K_CVPR19` | — | Original RetinaNet + Soft-IoU reference weights |

**Do not treat those numbers as ours.** Two caveats, both load-bearing:

1. **Licence and provenance are unverified** for every one of them. Check before
   anything reaches production.
2. **Domain shift is real and unmeasured.** These are trained on Western retail.
   Our photos are Iranian shops and fridges, shot by field reps on phones, with
   glare through fridge glass. A checkpoint reporting 0.906 mAP50 on SKU-110K
   val may do considerably worse on ours. That gap is not a disappointment —
   it *is* the measurement, and it tells us whether fine-tuning is needed at
   all. Our frozen 30-photo test set is what decides.

## What this actually requires of Phase 1

One design decision, taken early and cheaply: **the detector's only contract is
`image -> boxes`.** A `Detector` protocol with a single
`detect(image) -> list[Box]`, backend chosen in config. Everything downstream —
cropping, embedding, gallery matching, counting, share of shelf — is
detector-agnostic by construction.

Get that right and swapping YOLO for DEIM-D-FINE in Phase 3 is a config line
and an evaluation run. Get it wrong and it is a rewrite. The evaluation script
(Phase 1) is what makes the comparison meaningful: same frozen test set, same
metrics, honest numbers.

The deliverable of Phase 1 is **not** "we picked the best detector". It is
"swapping detectors is cheap, and we can prove which one is better on our own
photos."

## Sources

- Goldman et al., *Precise Detection in Densely Packed Scenes*, CVPR 2019 — SKU-110K
- Zhao et al., *RT-DETR*, 2023 — arXiv 2304.08069
- Peng et al., *D-FINE*, 2024 — arXiv 2410.13842
- Huang et al., *DEIM: DETR with Improved Matching for Fast Convergence*, CVPR 2025 — arXiv 2412.04234
- Ultralytics SKU-110K dataset docs
