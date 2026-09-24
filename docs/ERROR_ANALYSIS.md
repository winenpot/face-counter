# Error analysis, tuning, and the human-in-the-loop

Written 2026-09-24. Owns the part of the process the roadmap originally skipped:
what happens *between* "the model produces numbers" and "the model gets better".

The failure mode this document exists to prevent is the common one — download a
pretrained model, fine-tune on our data, watch a metric, nudge some
hyperparameters, declare victory. That produces a number. It does not produce
understanding, and it cannot tell you what to do next.

---

## 1. Error analysis

**A single metric is a summary, not a diagnosis.** mAP going from 0.61 to 0.64
tells you something changed. It does not tell you whether fridges got better,
whether blueberry is still being called strawberry, or whether you just
overfitted to aisles because aisles dominate the test set.

### The failure taxonomy

Every error gets classified. Detection and identification fail in different
ways, and conflating them sends you optimising the wrong stage:

| Class | Meaning | Stage at fault |
| --- | --- | --- |
| **Miss** | A real face with no box | Detector (recall) |
| **Duplicate** | Two boxes on one product | Detector (NMS / thresholds) |
| **Ghost** | A box on background, shelf edge, or a price tag | Detector (precision) |
| **Bad box** | Product found, box badly placed | Detector (localisation) |
| **Back-row** | A product counted that our guide says shouldn't be | Detector + guide ambiguity |
| **Wrong brand** | Right box, wrong brand | Identifier — **serious** |
| **Wrong flavor** | Right brand, wrong SKU | Identifier — expected, tolerable early |
| **False `other`** | A known SKU dumped into `other` | Gallery gap or threshold too high |
| **Missed `other`** | An unknown product forced into a real class | Threshold too low |

That table is the whole point. "Wrong flavor" is a known, accepted, roadmapped
weakness — the risk table says brand-level counts land well before SKU-level.
"Wrong brand" is a different animal and means something is actually broken. One
mAP number cannot distinguish them; this taxonomy does, and it tells you which
stage to spend the week on.

The `other`-rate rows deserve special attention: they are the only errors that
are *self-reporting in production*. Phase 4 monitors the share of `other`
precisely because a rise means new products or new packaging — an error class
that announces itself without a labeler.

### Slices

Aggregate numbers hide everything that matters. Report every metric split by:

- **Fridge vs. aisle** — glass, reflection, and depth make fridges the known
  hard case.
- **Crowding** — bucket photos by detected box count. SKU-110K's founding
  observation is that density is the difficulty axis.
- **Resolution / recompression tier** — *not a hypothetical: the field app
  recompresses server-side after upload.* 12.6% of the corpus (1,225 photos)
  lands within 2 KB of exactly 4 MiB, 950 of them at the identical byte count
  4,194,868 — a hard cap, not natural variation. A second population is
  heavily downscaled: 221 photos at 810x1080, 214 at 960x1280, 200 at
  1200x1600. JPEG recompression destroys fine detail first, which is precisely
  what a small, densely packed product is. Expect the capped and downscaled
  tiers to score worse, measure them separately, and never average them into
  one number. Whether the app still holds the uncompressed originals is an
  open question in `requests.md` — if it does, retraining on originals is free
  accuracy.
- **Glare / blur / tilt** — rep photo quality varies; the guideline ("stand
  back, shoot straight, one bay per photo") is an intervention we should be
  able to *measure the effect of*.
- **Store type and region** — from the manifest's `store_id` join.
- **Class frequency** — head vs. tail of the 103 classes. Rare SKUs will look
  fine in the aggregate while being unusable individually.

A model that improves overall while getting worse on fridges is not an
improvement — it is a trade we should make knowingly, not discover in month 4.

### The confusion matrix and the worst-50 bank

- **Confusion matrix over the 103 classes.** The off-diagonal mass *is* the
  research agenda. If blueberry↔strawberry dominates, that is a flavor-classifier
  problem (Phase 3). If everything smears toward one class, the gallery is
  unbalanced.
- **A standing bank of the 50 worst photos**, reviewed **by eye** every model
  version. Not optional and not automatable. This is where you discover the
  things no metric encodes — that a whole store's photos are upside down, that
  one rep shoots from two metres too far back, that a promotional shelf-wobbler
  is being counted as a product.

### Honesty rules

- **Report in business terms.** "Brand counts off by 2.3 faces per photo" and
  "share of shelf off by 4 points", not just mAP. The roadmap already demands
  this for the demo; it applies to every report afterwards.
- **Confidence intervals on 30 photos.** A 30-photo test set produces noisy
  numbers. A 2-point move may well be nothing. Say so rather than celebrating.
- **The test set is frozen.** Never tuned against, never sampled into by active
  learning, never regenerated without `--force` and a very good reason.

---

## 2. Hyperparameter tuning

Real, but deliberately *late* and deliberately *bounded*. Tuning before the data
pipeline and error taxonomy exist optimises a number nobody understands.

- **Order of returns, highest first:** more/better labelled data → input
  resolution and tiling (SAHI) → confidence and NMS thresholds → the gallery
  similarity / `other` threshold → learning-rate schedule and augmentation →
  everything else. The first two dominate for dense small objects. Do not start
  at the bottom.
- **Tune on a validation split, never the test set.** If tuning touches test,
  every number reported afterwards is inflated and the roadmap's whole
  leakage-prevention design (split by store, fixed from day 3) was wasted.
- **Every run logged to MLflow** with config, data version, and commit. A model
  is promoted only if it beats the incumbent on the frozen test set — the
  roadmap's existing gate.
- **Time-box it.** Tuning has no natural stopping point; give it a fixed budget
  and stop on the clock, not on satisfaction.

One threshold deserves naming separately: the **`other` similarity cutoff**. It
is a single scalar that trades "unknown products silently misfiled as ours"
against "known products dumped into `other`". It is cheap to sweep, it directly
moves a business-visible number, and it should be re-swept whenever the gallery
grows.

---

## 3. Human-in-the-loop — and why it is *not* RLHF

### RLHF is a different tool for a different problem

**RLHF (Reinforcement Learning from Human Feedback)** exists to optimise models
whose output has **no ground truth**. There is no correct next token for "write
me a poem", so you cannot compute a loss against a right answer. RLHF works
around that absence: collect human *preferences* between pairs of outputs, fit a
**reward model** to those preferences, then use reinforcement learning (PPO — or
DPO, which skips the RL and optimises preferences directly) to push the policy
toward higher predicted reward.

Every piece of that machinery is a workaround for a missing label.

**We are not missing labels.** When a labeler drags a box onto the right product
and picks a class, that *is* ground truth — complete, unambiguous, directly
usable. Converting it into a preference pair, fitting a reward model, and running
policy-gradient on a CNN would be strictly worse on every axis: less
sample-efficient, vastly more complex, far less stable, and it discards
information the correction already gave us for free.

This is not a close call, and it is not a matter of maturity or timeline.
Detection has a loss function; supervised learning on corrections is the right
answer and will remain the right answer. Anyone marketing "RLHF for computer
vision" is, in practice, renaming **active learning**.

The instinct behind the question was exactly right, though: *feed the model
signal about where it fails, and let humans generate that signal.* That is a
real, well-studied discipline. It is just called something else.

### What we actually want: active learning

The mechanism the roadmap gestures at ("prioritize low-confidence photos,
fridges, and SKUs with few examples") is one sentence with no mechanism behind
it. It should be a loop:

```
frozen test set (never touched)
        |
   train model  -->  predict over the unlabeled pool
        ^                      |
        |               sampling strategy
        |                      |
   corrections  <----  labelers correct pre-filled boxes
```

The only question active learning answers is: **which photos go to the labelers
next?** With 5–10 labelers at 3–4 h/day, that choice *is* the budget. Random
sampling wastes a large fraction of it re-teaching the model things it already
knows.

**Strategies, roughly in value-for-effort order:**

1. **Uncertainty sampling.** Lowest max-confidence detections; crops sitting
   near the gallery's `other` threshold. Cheapest thing that works; the
   canonical baseline (Settles' survey; Wang & Shang; Roy et al. for detection).
2. **Ensemble / committee disagreement.** Two detectors disagree on a photo →
   that photo is informative. Beluch et al. found ensemble-based uncertainty
   measures performed **best** in their evaluation, above single-model scores.
   Nearly free for us, because the Phase-1 bake-off leaves us holding two
   trained detectors anyway.
3. **Diversity, computed over object regions — not whole images.** NORIS
   (arXiv 2307.08414) selects samples that are informative *and* distant from
   other informative samples, and crucially computes distance from features of
   **detected object regions** rather than whole-image features. Result: 20–30%
   labelling-cost reduction vs. random on VOC/KITTI. The object-region detail is
   the load-bearing part for us — whole-image features on shelf photos would
   make every aisle shot look identical, and we would label 400 near-duplicate
   pictures of the same fridge.
4. **Class-balanced allocation.** ALMUS (2025) allocates the annotation budget
   per class using **category-specific metrics**, deliberately favouring classes
   where the model underperforms, with a dynamic allocation accounting for class
   difficulty and instance distribution. Directly aimed at our problem: 103
   classes with a long tail that will otherwise collapse into the 10 most common.
5. **Density.** Prioritise high box-count photos — SKU-110K's own thesis is that
   crowding is the difficulty axis.

**Considered and deferred: box-level sampling.** Desai et al. (CVPRW 2020) query
individual bounding boxes rather than whole images, which is finer-grained and
appealing. It produces **partially labelled images**, which complicates training
in ways not worth absorbing in month 2. Revisit only if image-level sampling
visibly plateaus.

### Practices that matter more than the algorithm

- **Measure the labelling ROI curve** — accuracy vs. number of photos labelled,
  plotted every round. If 500 corrections move the number 2 points and the next
  500 move it 0.3, the strategy is exhausted: change it, or stop. Without this
  curve you can burn labeler-months on a flat line and never notice.
- **Never let active learning touch the test set.** Uncertainty sampling
  *systematically* selects unusual photos. If those leak into evaluation, the
  test set silently stops representing real traffic — a corruption that is very
  hard to detect after the fact and that invalidates every number retroactively.
- **Track inter-annotator agreement.** Two labelers, the same 20 photos, once a
  month. If humans agree only 85% of the time on what counts as a face, **85% is
  the ceiling** — and you will otherwise spend weeks chasing a gap that is
  labelling noise, not model error. Disagreements are also the best possible
  bug reports against `labeling_guide.md`.
- **Version corrections, never overwrite.** One labeler having a bad week must
  be revertible without rebuilding the dataset.
- **Seed each round with the previous model's worst-50 bank** (§1). The photos a
  human flagged as embarrassing are reliably informative.

---

## Sources

- Settles, *Active Learning Literature Survey*, UW-Madison TR-1648 — the canonical reference
- Roy et al., *Active Learning for Deep Object Detection*, arXiv 1809.09875
- Beluch et al., 2018 — ensemble-based uncertainty outperforms single-model
- Hekimoglu et al., *NORIS: Non-Redundant Informative Sampling*, arXiv 2307.08414
- Phan et al., *ALMUS: Metric-Based Uncertainty Sampling*, IEEE 2025
- Desai et al., *Towards Fine-Grained Sampling for Active Learning in Object Detection*, CVPRW 2020
