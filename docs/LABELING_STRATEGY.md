# Labeling strategy — how 9,500 photos get labeled by a small team

2026-09-26. Companion to [`ROADMAP.md`](ROADMAP.md) (what and when),
[`labeling-guide/README.md`](labeling-guide/README.md) (the rules a labeler follows per box),
and [`ERROR_ANALYSIS.md`](ERROR_ANALYSIS.md) §3 (active learning — which photos
go to labelers after the first model exists). This document answers the question
in between: **what labeling work exists at all, and in what order it starts.**

---

## 1. The job is not "label 9,500 photos"

The corpus is 9,573 photos after dedupe, each holding 100–500 products. Labeled
exhaustively, that is on the order of one to two million boxes, each with one
of ~100 of our classes plus every competitor product. No team of this size
labels that, and the two-stage design exists precisely so that nobody has to.

The design splits labeling into three jobs of very different size:

| Job | What a human does | Volume | When |
| --- | --- | --- | --- |
| **A. Test set** | Corrects pre-drawn boxes, names every product, carefully | 30 photos, ~4,500 boxes | First — nothing is measurable without it |
| **B. Identity, by cluster** | Names a *group* of near-identical crops at once | ~thousands of decisions, not millions of boxes | Phase 1, feeds the gallery |
| **C. Detector corrections** | Fixes boxes the detector got wrong, chosen by active learning | A few hundred photos, in rounds | Phase 3, only if the detector needs it |

Job A is the only exhaustive, box-by-box job, and it is small. Job B is where the
volume would have been, and clustering collapses it. Job C is optional and
metered: it happens only if published detector weights miss too much on our
photos, and the labeling ROI curve (`ERROR_ANALYSIS.md` §3) says when to stop.

## 2. Separate *where* from *what*

Every box carries two facts: its geometry (is there a product here, and where
are its edges) and its identity (which SKU). Asking one person to settle both at
once, box by box, is the slowest and least consistent way to get either. The
labeling workflow keeps them apart:

- **Geometry pass.** Boxes only, one class: `product`. The detector pre-draws;
  the labeler deletes ghosts, adds misses, fixes edges, and applies the
  front-row and 50%-visible rules from `labeling-guide/README.md`. No class list to
  search, so the pass is fast and inter-annotator agreement is measurable on
  geometry alone.
- **Identity pass.** Every box from the geometry pass becomes a crop; crops are
  named — on the test set one by one, on the training pool by cluster (§3).

This split also matches the model: stage 1 learns only from geometry, stage 2
only from identity. A disagreement between labelers is then unambiguously a
geometry bug or an identity bug, which makes it a precise bug report against
the guide.

## 3. Cluster labeling — how identity scales

The same can of the same flavor appears thousands of times across the corpus.
Labeling each appearance separately spends human attention on the same decision
over and over. Clustering makes it once.

1. **Crop.** Run the detector over the training pool (never the test set, never
   test stores — see §6). Keep each crop's `photo_id`, box, and `store_id`.
2. **Embed.** DINOv2 on the 4060 Ti: one vector per crop. This is the same
   embedding the stage-2 matcher uses, so what clusters together here is what
   the matcher will find similar later — labeling effort is spent exactly where
   the model's own notion of similarity lives.
3. **Cluster.** Tight clusters over the embeddings (k-means with many more
   clusters than classes, or HDBSCAN). Over-splitting is cheap — two clusters of
   the same flavor each get named once; under-splitting is expensive — a mixed
   cluster poisons the gallery.
4. **Pre-suggest.** Score each cluster's centroid against the invoice packshots
   (`configs/Product/from_invoice/`, one per `class_name`) and attach the top-5
   classes as suggestions.
5. **Name.** The labeler sees one task per cluster: a contact sheet of ~50
   thumbnails plus the suggestions, and picks one answer: a class, a
   `COMPETITOR_<category>` (§4), `out_of_scope`, `not_a_product`, or **`mixed`**.
   `mixed` sends the cluster back to be split, never to be half-labeled.
6. **Propagate.** A named cluster labels every crop in it. Low-similarity
   members at the cluster's edge are the cheap place to spot-check.

**Tooling.** No new tool is needed: a Pillow script renders the contact sheets,
and Label Studio serves them as image-classification tasks (one image, one
choice list). The class list is the same `configs/classes.csv` plus the
competitor and control labels.

**Prior art.** Labeling clusters instead of items is an established technique,
not an invention here. *Annotron* (WSCG 2022) does it for retail shelves
specifically: it embeds product crops and reference packshots into one space,
groups similar crops, and asks the labeler only to pick the matching reference
— the same shape as steps 2–5. A 2025 PCB-inspection study (Sensors 25(20))
runs the same pipeline on 9,354 crops and reports an upper bound of ~200×
fewer operator decisions. It also measured cluster purity of only ~0.62 with
HDBSCAN on ten look-alike defect classes — a direct warning for our look-alike
flavors, and the reason the `mixed` answer exists.

**Unmeasured, and to be measured on the first batch:** crops per cluster,
seconds per decision, and the rate of `mixed`. Those three numbers turn the
promise above into a real estimate. The first batch should be
`label_batch_01.txt` (250 photos), which bounds the experiment at a few tens of
thousands of crops.

**Known limits.** Flavor variants of one brand share shape, color scheme, and
layout; they will cluster together more often than distinct brands will. Expect
`mixed` to concentrate in exactly the pairs the roadmap already lists as the top
risk (blueberry vs. strawberry can). Brand-level naming of a mixed cluster is an
acceptable fallback; flavor is recovered later by the Phase-3 classifier.

## 4. Competitors: category, not SKU

**Share of shelf needs "ours vs. not ours" per category, not the identity of
every competitor product.** The ratio `our faces / all faces in the category`
does not care whether a competitor face is brand X or brand Y — only that it is
not ours and that it belongs to the category. So a competitor product needs a
category label, `COMPETITOR_<category>` (for example `COMPETITOR_canned`), and
nothing more. That removes most of the "~400 classes" from the labeling burden:
our ~100 SKUs are named at SKU level, and competitors collapse into one class
per category.

Three consequences follow, and each is a rule:

- **Competitors are still boxed.** The detector must find every product, and an
  unboxed competitor both teaches it that products are background and silently
  shrinks the share-of-shelf denominator. Only the *name* is coarse; the box is
  not optional.
- **The category vocabulary is a business decision, and labels must not depend
  on it.** *Decided 2026-09-27:* four reporting categories, **canned drinks,
  glass drinks (glass only), oils (cooking and frying) and dressings (for
  food)**. Competitors are labeled by what they physically are,
  `COMPETITOR_<pack_type>`, from a vocabulary that covers every pack type we
  sell plus `oil`, `dressing`, `plastic-bottle` and `other`.
  `configs/reporting.yaml` maps pack types to categories at report time, so a
  new or renamed category is a config edit, never a relabel.
  `tests/test_taxonomy.py` enforces the coverage.
- **Products outside every category we sell get `out_of_scope`**, not a
  competitor label. A whole-aisle photo holds shampoo and detergent too;
  counting them as competitor faces would drag every share-of-shelf number
  down by an amount that depends on how wide the rep framed the shot.

**Which competitors earn a name.** Clustering (§3) shows, for free, which
competitor products recur. If the business asks for brand-level competitor
share, name the **20–30 most frequent** competitor products or brands — the
head of the distribution covers most of the shelf — and leave the long tail as
`COMPETITOR_<category>`. Promote a competitor from category to name only when
someone will actually read the number; every named class is a class the
identifier can confuse.

**The risk this creates.** Share of shelf now hinges on one binary decision per
crop: ours or not. An our-product misread as a competitor moves the metric in
the direction that matters most, so the evaluation reports the ours-vs-not
confusion separately from flavor-level accuracy (see `ERROR_ANALYSIS.md` §1,
"false `other`" and "missed `other`").

## 5. Tools: which free options fit, and which do not

The constraint that decides this is not price but **where the photos go.** These
are company photos of customers' stores; the rule is that no labeling tool may
send them off-premises. Tools checked 2026-09-26:

| Tool | Free on what terms | Photos leave the premises? | Verdict |
| --- | --- | --- | --- |
| **Label Studio** (Community) | Apache-2.0, self-hosted, already deployed and hardened | No | **Primary.** Geometry pass, identity pass, cluster tasks. Pre-labels import as predictions, and its ML-backend repo has ready examples for YOLO pre-labeling and Grounding DINO / SAM assistance. **But see the team-workflow gap below.** |
| **Roboflow** | Free "Public" plan: 15 credits/month, 2 users, 10 projects — and **every dataset and model is listed publicly on Roboflow Universe**; private data starts at the paid Core plan ($79/month billed annually) | **Yes, and published** | **Not for company photos.** Fine for experiments on public data such as SKU-110K, and its open-source `supervision` library (already in our tooling) is free regardless. |
| **CVAT** (Community) | MIT-licensed, self-hosted; also a hosted cloud, and a paid Enterprise from $12,000/year | Self-hosted: no. Cloud: yes | **The fallback, and the one to switch to if the team grows.** Community already has what Label Studio Community lacks: organizations with roles, per-job assignees, and an annotation → validation → acceptance stage with issue reporting. Auto-annotation needs Nuclio functions you deploy yourself (the repo ships SAM and YOLO examples); SAM 2 tracking and the Hugging Face/Roboflow model integrations are Enterprise or Online only. |
| **Make Sense** | Free, runs entirely in the browser; the project states photos are not transferred to a server | No | **Solo scratchpad only.** No server, no multi-labeler review, no task assignment; labels live in the tab until downloaded. Its model assist is COCO-SSD or a YOLOv5 exported to TF.js. Good for a quick trial by one person, not for a team. |
| **X-AnyLabeling** | GPL-3.0 desktop app, offline; ships SAM 1/2/3, Grounding DINO, YOLO-World/YOLOE, and detectors including RT-DETR, D-FINE and DEIMv2 — plus object-counting models (CountGD, GeCo) | No | **Power-user tool** on the GPU box, for one person pre-labeling or fixing a batch quickly. Imports and exports COCO, so it plugs into the same pipeline. |

**The team-workflow gap in Label Studio Community.** Checked against
HumanSignal's own feature comparison: the free edition has **no reviewer role,
no review stream (accept / fix / reject), no task assignment to specific
labelers, no project-level membership, and no inter-annotator agreement
metrics** — all of those are Enterprise, or the paid Starter Cloud ($99/month).
In Community, every signed-in user can see every project. For the first phase
this is tolerable: one or two labelers, 30 test photos, and agreement measured
by our own script over two COCO exports (§6). It stops being tolerable around
the 5–10 labelers the roadmap plans for month 2. The workarounds are one project
per labeler or batch, and a review done by re-opening tasks — clumsy, and the
reason to plan the switch rather than discover it:

- **Stay on Label Studio for Phase 1** (test set + first cluster batch). It is
  deployed, hardened, and the team is small.
- **Re-decide before month-2 labelers start.** If review and assignment are
  needed, self-hosted CVAT Community provides them free; paying for Label
  Studio Enterprise is the other option. Moving then costs one COCO
  export/import, not lost work — the reason COCO stays the only interchange
  format.

**Why not use several at once?** A labeling tool is also a data store:
each one keeps its own copy of the photos, its own users, and its own idea of
what a box means. Two tools means two places a correction can hide and two
export paths to reconcile. The free thing that actually saves labeling time is
not the interface but the **pre-labels** — detector boxes and cluster
suggestions — and those work in any tool. So: one team tool (Label Studio), COCO
JSON as the only interchange format, and a single-user tool only where it
saves real time and its output is imported back.

## 6. Guardrails

- **The test set is never clustered, embedded into the gallery, or sampled by
  active learning** — and neither are other photos from test stores. Clustering
  and nearest-neighbour search are exactly the operations that pull a
  near-duplicate test crop into training. Filter on `split != test` at the
  crop stage, before anything is embedded.
- **Freeze the test set before job A starts.** Once labelers put hours into
  those 30 photos, regenerating them costs those hours.
- **Version every export.** A Label Studio export is a snapshot; keep each one,
  dated, and never overwrite a previous round's labels.
- **Never `docker compose down -v` on a Label Studio stack**, and never
  `docker volume prune` / `docker system prune --volumes` on a machine hosting
  one. Those delete the volumes holding every annotation; a plain `down` or
  `stop` keeps them. Export JSON and `pg_dump` before any upgrade or cleanup.
  Detail: `deploy/label-studio/README.md`, "Stopping without losing labels".
- **Measure agreement on the geometry pass first.** Two labelers, the same five
  test photos. If they disagree on what counts as a face, fix
  `labeling-guide/README.md` before labeling the other 25.
- **Only the photos being labeled go to the Label Studio server**, not the
  30 GB corpus: the apps server's root disk has ~20 GB free.

## 7. Starting sequence

1. **Freeze the test set.** Eyeball the 30 photos in `test_labeling.txt` on the
   GPU box for mix (aisle, fridge, glare, store types); re-roll now if the mix is
   poor, because this is the last cheap moment. Then give the file a versioned
   home (it is gitignored today).
2. **Detector step zero.** Run published SKU-110K weights over the 30 test
   photos and look at the boxes (`DETECTOR_ALTERNATIVES.md`). This decides
   whether pre-labels are good enough to correct rather than draw.
3. **Load pixels through `ImageOps.exif_transpose`** (`PHASE0_REMAINING.md`
   §2) in any script that produces pre-labels. 14 of the 30 test photos are
   stored sideways; a bare `cv2.imread` puts their boxes 90° off.
4. **Job A, geometry pass** on the test set in Label Studio, class `product`
   only. Two labelers on the first five photos to measure agreement.
5. **Job A, identity pass** on the test set: our SKU,
   `COMPETITOR_<category>`, or `out_of_scope`, per box.
6. **Job B, first cluster batch** from `label_batch_01.txt`; measure crops per
   cluster, seconds per decision, and the `mixed` rate. Those numbers set the
   pace for the rest of the pool.
7. **Job C** only if step 2 showed the detector misses too much, driven by the
   active-learning loop in `ERROR_ANALYSIS.md` §3.

## 8. Weekly rounds, and what survives a wider taxonomy

Once the test set is labeled, the training pool is labeled in **weekly rounds
of about 100 photos**: the current model pre-labels a batch, people correct
it, the model is retrained on everything corrected so far, and the better
model pre-labels the next batch. This is iterative annotation, a known
method: Adhikari & Huttunen report up to 75% less manual work than drawing
from scratch. We do not start cold. `yolo26l-sku110k` already knows shelves,
so week one is corrections, not drawing: on the first three test photos a
labeler deleted 12–24 and drew 5–8 boxes out of about 115.

### What each round does

1. **Pick the batch** (see "Choosing the 100" below). Never from test stores
   and never from the gold validation set. `label_batch_NN.txt` already
   guarantees that no photo is sent to labelers twice.
2. **Pre-label and correct.** The detector pre-draws the boxes and the gallery
   matcher pre-suggests the names. These are two models (`ROADMAP.md`,
   Architecture) and both improve from round to round.
3. **Train.** Augmentation happens inside training: Ultralytics applies
   mosaic, colour, scale and flip, plus Albumentations when it is installed.
   Do not write augmented copies to disk. Add a targeted transform (glare,
   JPEG compression) only after error analysis names that failure. Never
   mirror crops for the identifier, because it would learn backwards text.
4. **Choose on the gold validation set, confirm on the test set.** Tune and
   compare on the gold validation set (PILOT step 3b). The frozen test set is
   read once per round, to confirm. A new model replaces the old one only if
   it beats it on the test set overall *and* in no slice does it get worse.
   Keep every round's weights.
5. **Record the learning curve:** detector recall and share-of-shelf error
   against the number of training photos, per slice.

### Choosing the 100

- **Round 1: stratified, not uniform.** Every scene type gets enough photos
  to be measured (roughly 15 or more), and rare types are over-sampled
  relative to the corpus. Scene type is what is photographed: an open or
  glass-door fridge, an aisle, a counter, a crowded small shop. It is a
  different axis from the **capture-quality** slices (glare, blur, and the
  field app's resolution tiers: full, 4 MiB-capped, 810x1080, 960x1280,
  1200x1600; `ERROR_ANALYSIS.md` §1). Every photo has one value on each
  axis. Resolution tier can be computed from the manifest. Scene type is not
  recorded anywhere yet, so it is tagged per photo (PILOT step 3b).
- **Rounds 2–3: re-weight by the learning curve, not by the error alone.**
  Move photos toward the slices that are bad *and still improving* when data
  is added. A slice that is bad and flat (say, glare that hides the label
  entirely) will not be fixed by more labels. It needs a photo guideline for
  reps or a different input. Keep a floor for the easy slices, roughly 20%
  of the batch, so they cannot regress unnoticed.
- **Round 4 on: pick photos, not types.** Active learning
  (`ERROR_ANALYSIS.md` §3) picks the photos the model is least sure of. That
  selects hard slices on its own, at photo level.
- **When to stop geometry rounds:** when two rounds in a row move gold-set
  recall by less than its noise in every slice. Labeling effort then moves to
  identity (cluster naming, gallery crops). How many rounds that takes is
  unmeasured; 3–6 rounds (300–600 photos) is a guess to be replaced by the
  curve.

### Capacity and cost

At the guide's 10–20 minutes per photo, one person does about 20 photos in a
productive day. **100 photos a week is one labeler, full time.** The test set
still needs its 27 remaining photos (about one day of labeling) and the gold
validation set about 30 more, both before round 1. Faster pre-labels shorten
each photo; more labelers shorten each week.

Outsourcing buys parallel labelers, not faster photos. It fits the loop under
three conditions:

- **Score every vendor batch against the gold validation set before paying
  for the next.** People correcting a model's boxes tend to accept its
  misses; the gold set catches that.
- **Send geometry and the scope's short label list out; keep identity in
  house.** Look-alike flavours are where outsiders fail, and cluster naming
  (§3) makes identity cheap anyway.
- **Price per corrected photo**, with the paid pilot batch from the RFP.

If it gets expensive, these are the cheapest levers, in order:

1. **Stop earlier.** The learning curve says when more photos stop paying.
2. **Label bays, not photos.** Crop a photo to one shelf bay and label the
   crop *exhaustively*. A crop trains the detector as well as a photo, for a
   fraction of the boxes. Never label *part* of a full photo: every product
   left unboxed is taught as background.
3. **Buy geometry only.** The vendor boxes `product`; naming stays in house.
4. **Make the selection sharper.** Active learning picks fewer photos that
   matter more.

### What survives when the taxonomy grows

Adding SKUs, product lines (biscuits, oil, jelly powder) or named competitors
never means redrawing, because the detector only knows `product`:

| Asset | What happens when labels get more detailed |
| --- | --- |
| Boxes (geometry) | Kept, 100%. No taxonomy change touches the detector's single class. |
| `product` boxes | These are the ones a wider scope names. That is renaming, pre-suggested by the matcher, never redrawing. |
| Brand-level names (`Kix-Max_canned`) | Refined, not contradicted: the SKU classes share the brand prefix, so a labeler only picks among that brand's flavours, best done by cluster. |
| `COMPETITOR_<pack_type>` | Already covers oil, dressing and the other pack types. Naming competitor brands is a rename, worth it only if someone will read that number. |
| Identifier | A new SKU is gallery images, not retraining. A Phase-3 classifier would retrain on crops, starting from its previous weights. |
| Configs | `scope.yaml`, `reporting.yaml`, rows in `classes.csv`. No code: this is PILOT step 8's pass/fail test. |
| Test set | The frozen 30 are mostly drinks and may not cover a new category well enough to measure it. Add a second frozen list from the test split for it. Never re-cut the first. |

`product` stays useful at any scope. It is the detector's training target,
the ground truth for detector recall, and the honest label for anything not
named yet. Fewer boxes carry it as the scope widens, but the label never goes
away. What *can* force more geometry labeling is a new **scene type**, not a
new label: oil aisles and biscuit racks look different from drink fridges,
and the detector's recall there is unmeasured. That means more photos from
those aisles, not redoing the drinks ones.

---

## Sources

- Roboflow pricing page, roboflow.com/pricing, and docs.roboflow.com/platform/billing-and-plans/plans — Public plan lists all data on Universe; checked 2026-09-26
- CVAT, github.com/cvat-ai/cvat — MIT licence; cvat.ai/enterprise — Community vs. Enterprise; docs.cvat.ai "User roles", "Manual QA and Review", "AI models" — job stages, roles, Nuclio functions; checked 2026-09-26
- Label Studio, labelstud.io/guide/label_studio_compare and labelstud.io/guide/enterprise_features — Community vs. Enterprise feature matrix (review, assignment, RBAC, agreement); checked 2026-09-26
- *Semi-automatic Acquisition of Datasets for Retail Recognition* (Annotron), WSCG 2022, doi:10.24132/csrn.3201.11
- *A Semi-Automatic Labeling Framework for PCB Defects via Deep Embeddings and Density-Aware Clustering*, Sensors 25(20):6470, 2025, doi:10.3390/s25206470
- Make Sense, github.com/SkalskiP/make-sense — README, "Privacy" and model-assist sections, checked 2026-09-26
- X-AnyLabeling, github.com/CVHub520/X-AnyLabeling — GPL-3.0 licence, checked 2026-09-26
- Label Studio ML backend, github.com/HumanSignal/label-studio-ml-backend — YOLO, Grounding DINO, SAM examples, checked 2026-09-26
- Adhikari & Huttunen, *Iterative Bounding Box Annotation for Object Detection*, ICPR 2020, arXiv 2007.00961 — train on small batches, pre-label the next, up to 75% less manual annotation
- Ultralytics docs, "Albumentations integration" (docs.ultralytics.com/integrations/albumentations) — applied automatically during training when installed; checked 2026-09-28
- Oquab et al., *DINOv2: Learning Robust Visual Features without Supervision*, arXiv 2304.07193
- Goldman et al., *Precise Detection in Densely Packed Scenes* (SKU-110K), CVPR 2019
