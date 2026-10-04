# Issue: count faces, not every object

**Status:** open, standing · **Raised:** 2026-09-30 · **Priority:** high. It
decides what we label, what we measure and which model we keep.
**Reader of the output:** the BI analyst, who consumes face counts and share
of shelf from this system.

> No model, published or ours, is near the accuracy we need yet. That is why
> this is worth fixing now: no shipped number depends on the wrong reading, and
> every labeling and training round run under it makes the fix dearer.

## 1. The problem

The BI analyst reads **faces**: the product units a shopper's eye meets
directly. A drinks fridge holds far more units than that. Behind each front
unit others are queued, and on an angled photo some of them are plainly
visible. A detector that finds "every product" boxes all of them, so its count
is not faces, it is *visible units*.

The plan as written optimises for the second and reports it as the first. The
best model for this project is therefore **not** the one that finds the most
products. It is the one that finds the faces and leaves the rest alone.

## 2. What a face is

Two terms, used the same way in every doc from now on:

- **Lane:** a line of units going back into the shelf, one behind another.
  Cans in a fridge stand in lanes; so do bottles on a shelf.
- **Face:** the frontmost unit of a lane, the one facing the shopper. There is
  **one face per lane**, always.

```
side view of one shelf level, the shopper on the left

  shopper ->  [A1][A2][A3][A4]     lane A: A1 is the face; A2-A4 are behind it
              [B1][B2]             lane B: B1 is the face
              [C1][C2][C3]         lane C: C1 is the face
```

A photo taken straight on shows A1, B1, C1 side by side: that line is the
"front row" of the labeling guide. From an angle it also shows the tops or
sides of A2, B2, C2. Those are real products, clearly visible, and **not
faces**.

What follows from this:

- A face is defined by **position** (frontmost in its lane), not by how it
  looks. The same can is a face today and a behind unit earlier, after the
  front one is sold. A model can only infer position from cues in the picture:
  occlusion (the front unit covers part of the one behind), size, where the
  base sits at the shelf edge, and the camera angle. That is why this is hard,
  and why a detector trained to "find products" does not solve it.
- Visible is necessary, not sufficient. The guide's 50%-visible rule stays.
- "Row" has been used two ways. The BI side says "one face per row", meaning a
  lane (front to back). The guide says "front row", meaning the line of front
  units across a shelf. Both point at the same units, but "row" alone is
  ambiguous, so the docs say **lane** and **face**. This is the definition as
  understood on 2026-09-30; if it is wrong, correct this section first and
  everything below follows from it.

## 3. Where the plan goes wrong today

The intent was always faces: the guide says front row only and skips units
behind it, the failure taxonomy has a "Back-row" class, and Phase 0 says "front
row only". What is missing is anything that *enforces* it.

| Where | What it says or does | Problem |
| --- | --- | --- |
| Stage 1 in README, ROADMAP, CLAUDE.md, `DETECTOR_ALTERNATIVES.md` | "The detector finds every product" | Wrong target |
| `yolo26l-sku110k`, our pre-labeler | Trained to box every visible product as one class, `object` | Has no notion of front vs. behind; boxes both |
| Test-set labels | Corrected from that detector's boxes (2,814 pre-drawn, 2,869 after review). The guide itself warns that accepting pre-drawn boxes is the commonest labeling error | Unknown how many boxes are behind units. **Never measured** |
| Labeling guide | "Label every product in the photo"; grey boxes are "the ground truth for how many products the detector should find" | Pulls labelers toward all units |
| Metrics ([step-zero report §7](reports/2026-09-27_detector_step_zero.md), `shelf-eval`) | Recall and precision at IoU 0.5 against every labeled box; count error = boxes vs. labeled products | Nothing separates a face from a behind unit. A detector that also boxes behind units gets *better* recall while over-counting faces. The 0.878 recall / 0.896 precision from the 2026-09-28 review export (not final) says nothing about faces |
| Model choice | The bake-off kept the model with more boxes (2,814 vs. 2,319) | Right for pre-labeling, where deleting a box is cheap and drawing one is not. It must not become the selection rule |

Expected effect on the BI number (reasoned, not measured): counting behind
units measures partly how deep a brand's lanes are stocked and how the photo
was angled, not how many facings it holds. Share of shelf then moves with
stocking depth and camera angle instead of shelf presence.

**Not affected:** the share-of-shelf arithmetic (`ours / all in category`), the
two-stage design, the taxonomy and `scope.yaml`. This changes what a *box*
means, not what a class is. The frozen test *photos* stay frozen; only their
labels can change, and every change is a new dated export
(`LABELING_STRATEGY.md` §6).

## 4. What "done" means

The rule: **the best model is the one that best counts faces.** In practice:

**Training images and labels**

- A face-only label set. Whatever is not boxed is background, so unboxed behind
  units teach the detector to skip them. That works only if the labels are
  consistent: one behind unit boxed by mistake teaches the opposite. Label
  consistency on face vs. behind is the whole game.
- No raw SKU-110K annotations, or any other all-objects dataset, mixed into
  fine-tuning. Their labels say the opposite of ours.
- Training batches deliberately include the photos that are hard *for this*:
  angled shots, deep open fridges, chest freezers, lanes with a visible second
  unit. Sampling signal (`ERROR_ANALYSIS.md` §3): photos where the current
  model predicts many more boxes than labeled faces.
- Vendor batches follow the same rule, and vendors copy their examples. The
  5-6 labeled sample photos already sent to labeling vendors (`LOGS.md`,
  2026-09-27) predate this definition: check whether they box units behind a
  face, and send corrected ones with the face rule before any vendor labels a
  batch.
- Gallery crops come from face boxes only. A unit behind another is partly
  hidden and angled, a bad reference for the matcher.

**Metrics and evaluation** (ground truth = labeled faces, IoU 0.5)

| Metric | Computed as | Why |
| --- | --- | --- |
| **Face recall** (primary) | faces matched / labeled faces | A missed face shrinks the count |
| **Face precision** | predictions matching a face / all predictions | Extra boxes inflate it |
| **Behind false-positive rate** | predictions matching a behind-tagged box / all predictions | The "Back-row" error, made visible for the first time. Needs the audit (§7 step 2) |
| **Face count error** | mean abs. (predicted faces − labeled faces) per photo, and per brand and category | What the BI analyst reads |
| Share-of-shelf error | as in `PILOT.md` step 6 | The business number |

Slices, always: `angled` (already a capture-problem tag), scene type, crowding,
and photos containing behind units (known after the audit). The old all-object
recall and precision stay as a **diagnostic column**, never a headline: the gap
between them and the face numbers is the size of this problem.

**Model selection.** A model is promoted only if it beats the incumbent on face
metrics and share-of-shelf error. All-object AP or box counts are never the
gate. The bake-off is re-scored on face ground truth once it exists, and the
`Detector` swap (`DETECTOR_ALTERNATIVES.md`) is judged the same way.

**Reporting.** Every report, `/count` response and dashboard tile says what a
face is. If the pipeline ever keeps non-face boxes (`predictions` in
`ROADMAP.md`), they carry a flag and counts read only faces. Any "units
visible" figure is named that, never "faces".

## 5. Open decisions (need the BI analyst)

These block guide v1.0 and the audit. Proposed defaults in italics.

1. **A lane's front slot is empty** (the front bottle was sold, the next one
   sits 20 cm back). *Proposed: the frontmost unit still present is the face.*
2. **The front unit is unreadable** (glare, under 50% visible) but the one
   behind it is clear. *Proposed: the lane counts zero faces, and the guide's
   50% rule stands.* Confirm an undercount is acceptable.
3. **No lanes** (loose pile, bin, crate). *No proposal.* Needs a rule, or these
   photos get a `display` tag and are reported apart.
4. **Stacked units and multipacks.** The guide boxes each stacked unit and has
   multipacks "to be decided". *Proposed: keep as is.*

## 6. Approach options

How the model learns it, in order of preference. Decide after the audit, not
before.

1. **Fine-tune the detector on face-only labels (default).** Fewest parts, and
   the pipeline stays detector-agnostic. Depends on label consistency (§4).
2. **Keep an all-object detector and add a face-or-behind classifier** on each
   box plus its surrounding context. More moving parts. Only if option 1
   plateaus on behind false positives.
3. **Geometry heuristics** (box size, shelf-edge alignment). Fragile under
   angle. A diagnostic at most.

**Recording behind units in the labels.** (a) Delete them: simplest, but the
count of behind units is then lost and so are the hard negatives. (b) A new
click-only label `behind` (no hotkey, so keys 1-7 do not move), kept in the
export and scored as "must not be predicted". (c) A per-box marker in Label
Studio: keeps a label physical, at two clicks per box. *Recommended: (b) for the
test and gold sets.* Behind units are never named, so nothing is lost; the
exception to "labels record what is physically on the shelf" (a behind unit is
a position, not a thing) is recorded here and in `CLAUDE.md`.

## 7. Plan

`[x]` done · `[~]` partly done · `[ ]` not started. Steps 1 to 3 come before the
labels are marked final and `shelf-eval` starts from them.

- [~] **0. Say it in the docs.** Lane and face defined; "every product"
      reworded to "every face" in the guide (EN and FA), ROADMAP, PILOT,
      ERROR_ANALYSIS, LABELING_STRATEGY, DETECTOR_ALTERNATIVES, step-zero §7,
      README, CLAUDE.md (2026-09-30). Pending the BI answers below.
- [ ] **1. BI answers §5.** Then guide v1.0.
- [ ] **2. Face audit of the frozen test labels.** Every box on the 30 photos
      is face or behind (§6, recording). Report how many of the 2,869 boxes
      are behind, per scene type. This is the first real number for this
      issue. Save as a new dated export; keep the old one.
      **Where (decided 2026-09-30):** a new Label Studio project seeded from
      the frozen v1 labels, never the v1 project itself
      (`data/label_studio/FROZEN.md`); its export becomes `pilot-test-v2`.
- [ ] **3. Agreement check.** Two labelers, the same five photos, the
      face-vs-behind decision only. If they disagree, fix the guide before
      labeling more.
- [ ] **4. Face metrics in `shelf-eval`** (`src/face_counter/evaluation/`).
      Re-score every bake-off candidate on faces; keep the old numbers as a
      diagnostic column.
- [ ] **5. Gold validation set (`PILOT.md` 3b) and every training batch are
      labeled under the face rule,** vendor batches included (§4: check the
      sample photos already sent).
- [ ] **6. Hard-photo sampling** for training rounds (§4).
- [ ] **7. Fine-tune on face-only labels;** promotion gate on face metrics
      (`ROADMAP.md` Phase 3).
- [ ] **8. State the rule inside Label Studio.** Header text and the `behind`
      label, in `prepare_label_studio.py`. The project config is live and
      labelers are working in it: check before touching, and deploy as a
      planned change.
- [ ] **9. Reporting wording** for `/count`, `/overlay` and the dashboard.

Out of scope: how many units sit in each lane (stock depth). It is a different
question and may interest BI later; it needs its own issue.

## 8. Where this is written down

[`ROADMAP.md`](ROADMAP.md) (section "Standing issue", Phases 1 to 3, risks) ·
[`PILOT.md`](PILOT.md) · [`ERROR_ANALYSIS.md`](ERROR_ANALYSIS.md) ·
[`LABELING_STRATEGY.md`](LABELING_STRATEGY.md) ·
[`DETECTOR_ALTERNATIVES.md`](DETECTOR_ALTERNATIVES.md) ·
[step-zero report §7](reports/2026-09-27_detector_step_zero.md) ·
[labeling guide](labeling-guide/README.md) and its
[Persian translation](labeling-guide/README.fa.md) · `LOGS.md`.
