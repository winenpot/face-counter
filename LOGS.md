# LOGS

Note (2026-09-24): entries from here forward are written in English.
Earlier entries below remain in Persian/Farsi as originally written —
left as-is rather than machine-translated, to avoid corrupting the
original record.

---

خط زمانی خوانا و انسانی از آن‌چه واقعاً روی این پروژه اتفاق افتاده —
تصمیم‌ها، باگ‌های پیدا شده، بن‌بست‌ها. این جایگزین `git log` نیست (آن‌جا
خودش هست)؛ این برای روزی است که شش ماه دیگر بپرسیم «چرا این‌طور
انجامش دادیم؟». هر بخش یک جلسه‌ی کاری، جدیدترین بالا، خلاصه و کوتاه.

---

## 1405/07/08 (2026-09-30) — faces, not objects

**Our yardstick was measuring the wrong thing, and nothing had flagged it.**
The BI analyst reads *faces*: the frontmost unit of each lane, one per lane.
Stage 1 was written everywhere as "the detector finds every product", the
SKU-110K detector that pre-drew the test set boxes every visible unit, and every
number so far (recall 0.878 and precision 0.896 on the 2026-09-28 review
export; the bake-off's box counts) is against all labeled boxes. A detector that
also boxes the units behind the face gets *better* recall while over-counting
faces, so those numbers cannot pick the right model.

- The intent was always faces (guide: front row only; taxonomy: "Back-row"), so
  nothing was reversed. What was missing is enforcement: the guide said "label
  every product", the metrics had no front/behind split, and how many test
  boxes sit on units behind a face has never been measured.
- "Row" meant two things: a lane (front to back) to the BI side, the line across
  a shelf to the guide. Docs now say **lane** and **face**.
- Written up as a standing issue, `docs/ISSUE_FACES_NOT_OBJECTS.md`: the
  definition, four open questions for BI, face metrics (face recall and
  precision, behind false-positive rate, face count error) and nine ordered
  steps. The first real step is a face audit of the test labels. Reworded in
  ROADMAP, PILOT, ERROR_ANALYSIS, LABELING_STRATEGY, DETECTOR_ALTERNATIVES,
  step-zero §7, README, CLAUDE.md and the labeling guide (EN and FA, now v0.2).
- No code changed. `shelf-eval` still scores all-object recall; that is step 4
  of the issue.

## 1405/07/07 (2026-09-29) — the Persian font finally renders

**The font was deployed on the 28th and still rendered as Figtree.** Fixing
it took three observations, and the order matters more than the fix:

1. Computed style said `Figtree, sans-serif` → Label Studio 1.23 hardcodes
   its font family and never reads a `--font-family` custom property. The
   original `html body { --font-family: 'BYekanLS' ... !important }` set a
   variable nothing consumes. `!important` cannot help: it wins the cascade
   for a property, it cannot make anyone *read* that property.
2. Only Figtree appeared in the Network tab → a browser downloads a webfont
   **only when a matched rule actually uses it**. Our woff2 was never
   fetched, which by itself proved no rule ever matched it. A font missing
   from Network is stronger evidence than anything in Computed.
3. Label chips changed but headings did not → a difference *inside* one
   family is a weight-matching problem, not a selector problem.

**The technique: redefine the family instead of overriding it.**
`@font-face` does not say "use this font", it says "here is a font, and here
are the characters it is for" (`unicode-range`). The browser matches **per
codepoint**, so several `@font-face` rules can share one family name and
split the alphabet between them. So B Yekan is declared *as* `Figtree`,
scoped to `U+0600-06FF, U+200C-200F, U+FB50-FDFF, U+FE70-FEFF`. Label Studio
keeps asking for Figtree, keeps getting real Figtree for Latin (`Kix-Max`,
`TorshX`), and silently gets B Yekan for Persian. No override, no cascade
fight, no forked stylesheet.

**Two traps worth remembering:**

- *Weights.* The faces were first declared `font-weight: 500 900`, a range —
  but the bold woff2 is a **static** font, and a static face spread over a
  range is matched inconsistently. Headings (`typography-title-*`, weight
  600/700) fell back while body-weight chips rendered. Declare `normal` and
  `bold`, one face per value.
- *Size.* The woff2 files are embedded as base64, so every extra
  `@font-face` costs ~70 KB of config. A first attempt declaring 24 faces
  (3 families × 8 weights) produced a **1.4 MB** labeling config; caught
  before deploying and trimmed to 4 faces / 235 KB.

Never use `* { font-family: ... !important }` for this: it also overrides
Label Studio's **icon fonts** and turns the toolbar into empty boxes. The
interface rule is scoped to real class names read off the live DOM
(`[class*="typography-title"]`, `.lsf-choice`, `.lsf-hint`,
`.ant-radio-wrapper`, ...).

**Finding, not yet fixed: the labeling config is not in git.**
`data/label_studio/` is gitignored as *generated* output, but
`labeling_config_scope_fa.xml` is hand-maintained — it holds the Persian
translation, the three photo-level fields, all 18 choices and now the font
fix, and it exists on exactly one disk with no revert. `prepare_label_studio.py`
cannot regenerate it either (`labeling_config()` emits the English config
from `classes.csv`). Fix: a `.gitignore` exception for
`labeling_config_*.xml`, and move the `<Style>` block into its own CSS file
that `labeling_config()` inlines — then the gold set (3b) gets correct fonts
for free instead of a hand-edited 235 KB copy.

**Also:** the `#N` photo numbers in the review checklist are Label Studio's
`inner_id` (1-30), while the Data Manager and task URLs use the global `id`
(2-31) — **off by one**, because task id 1 belongs to another project. Jump
to a photo with `/projects/3/data?task=<inner_id + 1>`. Putting the number
on the labeling screen is deferred to the gold set's project.

---

## 1405/07/06 (2026-09-28) — back up to speed, Persian labeling screen, test set reviewed

- **Phase 0 closed in the docs.** `PHASE0_REMAINING.md` is now a record;
  its open items moved to `PILOT.md` and ROADMAP "Risks".
- **Labeling plan written down.** `LABELING_STRATEGY.md` §8 covers weekly
  rounds of ~100 photos, how to choose them, capacity (100 a week is one
  full-time labeler), vendors, and what survives a wider taxonomy.
  `PILOT.md` gained 3b (a gold validation set) and 4b (the embedding
  matcher). The labeling guide says to ignore detector confidence and sweep
  for misses.
- **Labeling screen in Persian, data still in English.** Label Studio's
  `alias` shows Persian and stores the English names. It was proven in a
  throwaway project first. That test also showed Label Studio 1.23.0
  *accepts* a config that drops labels already in use, so its safety check
  can't be relied on. Three photo-level fields were added (scene type,
  capture problems incl. reflection and too-wide/cluttered, photo problems),
  plus the B Yekan font embedded in the config. `docs/labeling-guide/README.fa.md`.
  The config lives only in `data/label_studio/labeling_config_scope_fa.xml`
  (no source change); rebuild with `shelf-ls-setup --config` pointing at it.
  A dated JSON export was taken before every change.
- **All 30 test photos submitted; labels not final.** The box work is real,
  but many competitor cans and glass bottles are still grey `product` and
  #24-#30 were not corrected. Checklist:
  `docs/reports/2026-09-28_test_set_label_review.md`.
- **The GitHub repo is public.** It exposes the three shop screenshots in
  the labeling guide, `classes.csv` and the test photo ids. Make it private
  before pushing today's commits. The licensed font stays out of git until
  then (`deploy/label-studio/fonts/`, gitignored).

**Next:**
1. Work through the review checklist, export, and re-review.
2. Make the GitHub repo private, then commit the font and push.
3. Evaluation script (`PILOT.md` step 6), from the final export.

**Lesson of the day:** "all 30 submitted" is not "labeled". Check what the
metric needs (here, every can and glass bottle named) photo by photo, not
from the counts.

---

## 1405/07/05 (2026-09-27) — business answers, a taxonomy that can grow, and a two-brand pilot

**Business answers.** Reporting categories are canned drinks, glass drinks
(glass only, not plastic), oils and dressings. Studio packshots are probably
not coming in the remaining two weeks. The 2,230-vs-3,292 store gap is
revisits: the survey counted per-visit codes. Poor field recording also
splits some revisited stores into two IDs, so 2,230 is an upper bound and a
small train/test leak is possible; accepted. The `root` rotation item was
dropped by the user's decision.

**Labels no longer name business categories.** A box is our SKU,
`COMPETITOR_<pack_type>` or `out_of_scope`; `configs/reporting.yaml` maps pack
types to categories at report time. `classes.csv` gained `pack_type` (was
`category`) and `source`, and the invoice import now merges instead of
overwriting, so hand-added rows survive. `tests/test_taxonomy.py` fails if a
pack type we sell or report on has no competitor class.

**The `bottle` rows were wrong.** The invoice's own pictures showed the TorshX
energy drink is a can, and the business confirmed each TorshX flavor
ships as both can and glass bottle. 8 classes became 15. Invoice images were
re-extracted and the TorshX ones filed by eye; one (`TorshX_madrid_3.png`, a
pink bottle) looks mis-attached in the invoice and sits in `_unsorted/`.

**Pilot scope.** Kix-Max + TorshX, share of cans and of glass bottles,
reported separately. `configs/scope.yaml` filters the taxonomy without
changing it; `shelf-label-prep --level scope` gives labelers 31 labels instead
of 127. Every can and bottle is still named whoever makes it, and boxes outside
scope stay `product`, so widening the scope never relabels anything. The
ordered to-do list is `docs/PILOT.md`.

**Next:** pick the detector from the bakeoff overlays (`PILOT.md` step 1).
*(Done later the same day: YOLO26l, see below.)*

**Later the same day.**
- **Detector:** YOLO26l (SKU-110K weights) now pre-draws boxes for labeling.
  YOLOE with reworded prompts collapsed to 98 boxes across 30 photos and is
  shelved as a detector.
- **Pilot labels:** named by brand and pack type only (`scope.yaml`
  `detail: brand`), labeled in one pass by one person. Runbook:
  `docs/PILOT_LABELING.md`.
- **A discontinued brand was removed.** The company no longer produces or
  distributes it. Its class, its import rule in `build_classes.py`, its invoice
  images and every mention of it were deleted. Where it served as the example
  of "another brand of ours", the docs now say that in general terms. An old
  invoice that still lists it now adds nothing, because the brand is no longer
  in `BRAND_CANON`. 109 of our classes remain, 126 in total. The pilot has 7
  labels.
- **Label Studio is driven from git.** `uv run shelf-ls-setup` creates or
  updates a labeling project over Label Studio's API (through an SSH tunnel;
  the token lives in the gitignored `deploy/label-studio/.env`). It put the
  pilot project on the server: id 3, 30 tasks, 2,814 pre-drawn boxes.
  `scripts/deploy_label_studio.sh` deploys the app itself: backup, diff,
  confirm, sync, restart, health check. First real run deployed f87ad03 (docs
  only; same versions). No CI/CD on purpose: a pipeline would hold an SSH key
  to the shared production server and could run an irreversible database
  upgrade with nobody watching. A post-commit hook reminds instead.
- **Phase 0 is complete.** The first 3 test photos were labeled (#04, #06,
  #22) and their screenshots became the guide's examples; the guide moved to
  `docs/labeling-guide/README.md` beside them. Correcting YOLO26l's boxes on
  those photos meant deleting 12-24 and drawing 5-8 new ones per photo, out
  of about 115.
- **First export saved.** Full JSON, the 3 labeled photos, at
  `data/label_studio/exports/pilot-test-2026-09-27.json` (gitignored). It is
  the first backup of real test-set labels and what the evaluation script
  will read.
- **Grey `product` boxes are kept on purpose.** Only the 6 named labels count
  toward share of shelf, but the grey boxes are the ground truth for "did the
  detector find every product", and a later scope names them without
  redrawing. They follow the same rules as named boxes (added to the guide).
- **Outside the code: labeling vendors.** The owner called 4-5 labeling
  companies, sent them sample photos, and asked whether they could label
  1,000-10,000 photos at a fair price. Two asked for a formal request for
  proposal (RFP). Two others asked, by email and Telegram, for example photos
  with labels, and got 5-6 labeled examples; both are expected to call back on
  2026-09-28:
  - Taghizadeh (تقی زاده), phone 0912 26814913
  - Barai (بارای), info@barai.ir

  Nothing is agreed yet.
- **Paused by the owner:** tracking D-FINE ("DF-DETR") against YOLO26l.
  D-FINE and DEIM-D-FINE are already in `DETECTOR_ALTERNATIVES.md` and on the
  fine-tuning list (`PILOT.md` step 6b); a fair comparison needs the labeled
  test set first.

**Next:**
1. Label the other 27 test photos, exporting JSON after each session.
2. Taghizadeh and Barai call back (2026-09-28).
3. Write the RFP for the two vendors that asked for one. It should cover: how many photos and
   boxes per photo (about 100); our guide, labels and tool (Label Studio,
   JSON export); a paid pilot batch scored against our own labels before any
   large order; and data handling, since the photos are the company's (NDA,
   no reuse or publishing, deletion after the job, where the data is stored).
4. Evaluation script, once the test set is labeled (`PILOT.md` step 6).

**Lesson of the day:** the invoice text said "Carbonated Soft Drink" and the
code guessed a container; the invoice's own pictures said otherwise. When a
source carries both text and images, check one against the other before
trusting a parse.

---

## 1405/07/04 (2026-09-26) — test set frozen, labeling strategy written, and the first three detectors actually ran

**Labeling strategy — how 9,500 photos get labeled by a small team.** New doc
`LABELING_STRATEGY.md`. Three decisions carry it: only the **test set** is
labeled exhaustively (two passes); identity is named per *cluster* of
near-identical crops rather than per crop; and competitors are labeled at
category level (`COMPETITOR_<category>`), because share of shelf only ever needs
"ours vs. not ours" within a category. Also settled a tooling question with a
licence answer: **Roboflow's free plan publishes your data**, so it is out for
company photos — Label Studio stays the primary tool.

**Label Studio operational guardrails.** The stack holds every annotation in
named volumes, so `down -v` / `docker volume rm` / `prune --volumes` are
unrecoverable there. Written into `deploy/label-studio/README.md` with the
export + `pg_dump` procedure to run before any upgrade. Noted that the unrelated
`ATPG-tagsystem` Label Studio on port 7071 is a different instance — don't
import into it, don't touch its volumes.

**The 30-photo test set is frozen (12:57).** Reviewed by eye, hand-corrected,
and committed: `data/splits/test_labeling.txt` is now the one tracked file under
`data/splits/`, via an explicit `.gitignore` exception. The **git copy is the
authority** and no seed regenerates it — `shelf-splits --force` must never run
again, or every accuracy number ever reported is measured against a different
test set.

**EXIF correction, worse than first recorded.** The 2026-09-24 entry said two of
the 30 test photos disagreed with the manifest on orientation. The real number
is **14 of 30 stored sideways**. The manifest's width/height are post-rotation;
pixels must always be loaded through `ImageOps.exif_transpose`. Anything that
skips it places boxes rotated 90° and it will look like a model bug.

**`shelf-bakeoff` — step zero of Phase 1 (13:30).** New CLI
(`src/face_counter/training/detector_bakeoff.py`): runs candidate detectors over
the frozen test set and writes what a human needs to judge them —
`detections.jsonl`, `counts.csv`, `overlays/<model>/*.jpg`, and
`ls_predictions_<model>.json` to pre-fill the Label Studio geometry pass.
Deliberately scores nothing: the test set has no boxes yet.

**A transformers 5 break, fixed (14:13).** The DETR-SKU110K checkpoint's
`config.json` was written by transformers 4.38 with `"dilation": null` (and three
other nulls). transformers 5 type-checks config fields strictly and rejects
`None` for a `bool`; dropping the null keys falls back to the class defaults,
which is what 4.x did with `None` anyway.

**First real run, on the GPU box (14:15–14:23), and what it showed.** 30 photos
x 3 models, ~15 s total; steady state 0.04–0.07 s/photo with a slower first
image per model (CUDA warm-up) — GPU, unambiguously. Box counts over the test
set:

| model | total | median | min | max |
|---|---|---|---|---|
| sku110k-yolo11s | 2,319 | 69.5 | 15 | 218 |
| detr-r50-sku110k | 5,545 | 183.5 | 51 | 396 |
| yoloe-26s | 1,466 | 40.5 | 1 | 134 |

Three readings, none of them accuracy:
- **DETR is structurally capped at 400 boxes** (400 queries) and one photo came
  back with 396 — saturation, on shelves documented as reaching ~500 faces. Its
  uniformly high counts are also what DETR does at conf 0.25 with no NMS, so
  part of the gap is recall and part is duplicate queries. Only the overlays
  separate the two.
- **YOLOE collapses on two photos** (1 box each) while returning 134 elsewhere:
  a failure, not a weak score. Generic text prompts are the suspect.
- The three models disagree by 3–10x on the same photo, which is exactly why
  step zero exists — the geometry pass can't be pre-filled from a model chosen
  on vibes.

**The pull had to be done by hand, and that is a real finding.**
`sync_from_hemin.sh` gates on the remote tree being clean, but
`~/code/face-counter` on the GPU box **is not a git repo** (it was rsynced, never
cloned), so the gate fails closed and every results pull aborts. Pulled the 43 MB
run directly with `rsync` instead. Two facts worth keeping: the box has **no
revert safety net** for anything edited there, and the fix is to `git clone` it
rather than to weaken the gate.

**Also established: this workstation cannot be pushed to.** It runs no sshd —
from the GPU box, `ssh <user>@<this-workstation>` is refused. So "results are sent
back" is not implementable as a push; results come back only because this side
pulls them. Any future automation of that must be initiated here.

**Reverted an over-engineered sync refactor.** Started building `.env`-driven
sync config (`GPU_HOST` alias, `GPU_REMOTE_DIR`, `GPU_REMOTE_HAS_GIT`), a
`report.json` per run, and a `--run <stamp>` pull mode — five files. The user
called it too much machinery for the problem and reverted it all; the existing
scripts work, and where things go is easier to remember than to configure.
Recorded because the *underlying facts* (no sshd here, no git there) outlive the
code that was deleted.

**Still open, end of day:**
- Eyeball the overlays in `runs/bakeoff/20260926-141557/overlays/` and decide
  whether DETR's extra boxes are recall or duplicates — that single judgement
  picks the model that pre-fills the geometry pass.
- The 3 annotated examples for `labeling_guide.md` (last Phase 0 item, owner
  working on it).
- `git clone` the GPU box so sync stops needing manual rsync.
- Carried over: the 2,230-vs-3,292 store gap, studio packshots.

**Lesson of the day:** a guard that fails closed on a condition nobody
anticipated (no `.git` on the far side) is indistinguishable from a broken
script, and gets worked around by hand instead of fixed. Same shape as
2026-09-24's `--with-data` bug: the failure is silent-ish, the workaround is
cheap, so the cause survives. Note the cause where it will be read again.

---

## ۱۴۰۵/۰۷/۰۲ (۲۰۲۶-۰۹-۲۴) — the export finally ran; the model landscape moved; a user tip corrected a wrong call

**Morning – Phase 0 audit.** Walked the roadmap checkbox by checkbox. The
picture was worse than the checkboxes implied: the export had never run against
production, so the "manifest" and "fixed test set" were both artifacts of a
295-photo sample, and the test set held 15 photos instead of the required 30.

**~11:37–12:17 – the production export ran** (on Hemin's box, by the user).
9,409 new + 295 already on disk = **9,704 manifest rows**, `missing: 0`,
`bad_image: 1`. About 30 GB. Two things worth recording: the single `bad_image`
is the already-known truncated 7 KB photo, not a new failure mode; and the
earlier live sample's alarming 8-of-13 decode failures collapsed to **1 in
9,704** once `pillow-heif` landed — good retrospective evidence that diagnosis
was right.

**Detector research — the landscape moved, and our stated plan is out of date.**
The roadmap says "train a small YOLO on SKU-110K", which hides two things.
SKU-110K is a *dataset*, not a model, and it is *single-class* — every box is
labelled `object`, so it can never name a product. That is not a limitation but
the reason it fits: it solves stage 1 completely and demands zero labelling
from us. Second, YOLO is no longer the accuracy leader. The DETR branch took
over: RT-DETR made DETR real-time, D-FINE replaced point-estimate box
coordinates with a distribution it iteratively sharpens, and **DEIM** (CVPR
2025, Apache-2.0) attacked training cost — ~50% less training time, SOTA
real-time AP, and *largest gains on small objects*, which is exactly our
weakness. DEIM reaches 53.2 AP in one day on a single 4090; our 4060 Ti is in
the same conversation. The training-cost objection that justified picking YOLO
is the specific thing DEIM removes. Also found published SKU-110K checkpoints
(one DETR-ResNet-50 at 58.9 mAP, *trained on a 4060 Ti*), so Phase 1 now starts
with an afternoon evaluating existing weights before spending a night training.
Written up in `DETECTOR_ALTERNATIVES.md`; Phase 1 gained a `Detector` protocol
so the backend stays a config choice.

**RLHF question → the process gap it exposed.** The user asked whether RLHF
applied here. It does not, and the reason is structural: RLHF exists to optimise
models whose output has *no ground truth* — every part of its machinery
(preference pairs, reward model, policy gradient) is a workaround for a missing
label. A corrected bounding box *is* ground truth, so supervised learning on
corrections is strictly better. What the user actually wanted is **active
learning**, and that led somewhere more useful: the roadmap had no home for
error analysis, hyperparameter tuning, or any mechanism behind "prioritize
low-confidence photos". Phase 3 was rewritten around diagnosis-before-retraining
(a nine-row failure taxonomy separating wrong-brand from wrong-flavor, sliced
metrics, confusion matrix, a worst-50 bank reviewed by eye) plus a real active
learning loop (uncertainty → ensemble disagreement → NORIS diversity over
*object-region* features → ALMUS class-balanced allocation). New doc:
`ERROR_ANALYSIS.md`.

**A pre-existing bug in `sync_from_hemin.sh --with-data`: it never worked.**
Found while adding `--with-manifest` (splits need a 2 MB CSV, not 32 GB of
photos, and there was no way to ask for that). With the trailing
`--exclude '*'` default-deny, rsync never descended into `data/` because
`data/` itself was never included — the mode would report success and transfer
nothing. Nobody had exercised it. Both modes now include the parent dir
explicitly, verified against the live remote with `--ignore-times` dry runs.

**Splits re-cut over the full corpus, test set frozen at 30.** Cleared the old
sample-derived files and re-ran from scratch. 9,573 photos after dropping 131
exact duplicates; train 7,640 / val 1,076 / test 857, and **zero store overlap
between any pair of splits** — the leakage guard holds at full scale. The test
set is 30 photos from 30 *distinct* stores, one photo each. All 30 decode
(including 3 `.mpo` and 1 `.heif`).

**The user's tip that corrected a wrong call.** During the decode check, three
test photos shared an identical byte size and two more looked like screenshots;
I was heading toward calling them contamination and re-rolling the test set.
The user mentioned the field app's developer had modified images server-side
after upload because of upload problems. The data confirms it exactly: **1,225
of 9,704 photos (12.6%) sit within 2 KB of exactly 4 MiB, 950 at the identical
byte count 4,194,868**, plus downscaled populations at 810x1080 (221), 960x1280
(214), 1200x1600 (200). So the low-resolution photos are a *systematic,
representative slice of real production traffic* — filtering them out would
have made the test set less representative than reality and inflated every
number the project ever reports. Resolution tier became a reporting slice in
`ERROR_ANALYSIS.md`; `requests.md` gained a question to the app developer about
whether pre-compression originals still exist anywhere (if they do, training on
them is free accuracy).

**Still open / waiting on someone else, end of day:**
- Eyeball pass on the 30 test photos for mix (aisles, fridges, glare, store
  types) — images are on Hemin's box.
- The 3 annotated examples for `labeling_guide.md` — owner working on it.
- **Unexplained: 2,230 distinct stores against the surveyed 3,292.** The 1%
  join-failure rate does not account for a 32% gap. Not blocking, but nobody
  should quote store coverage until it is understood.
- **EXIF orientation trap:** the manifest records pre-rotation dimensions while
  Pillow applies the orientation flag; two of the 30 test photos disagree.
  Harmless today, but anything in Phase 1 trusting manifest width/height will
  place boxes rotated 90° — and it will look like a model bug, not an
  assumption bug.
- Studio packshots from marketing (all 8 brands, named by `class_name`).

**Lesson of the day:** the two most valuable corrections came from outside the
code. The user's offhand remark about the app developer's upload fix overturned
a conclusion I had reached from the data alone and was about to act on — the
numbers were right, the interpretation was wrong, and only domain context could
tell the difference. Corollary: before treating unusual data as defective,
find out who touched it and why. The same day also showed the cost of *never*
exercising a code path — `--with-data` had been broken since it was written,
and only running it revealed that.

---



## ۱۴۰۵/۰۶/۳۱ (۲۰۲۶-۰۹-۲۲) — یک روز کامل: ادغام shelf-detector، یک باگ واقعی در اسکیما، راه‌اندازی سرور GPU



**۰۹:۴۶ – اولین نگاه واقعی به دیتابیس تولید.** یک بررسی فقط‌خواندنی از
`atpg` (دیتابیس واقعی و زنده) یک شگفتی بزرگ نشان داد: تنظیمات export
(`configs/export.yaml`) *قبل از این‌که کسی اسکیمای واقعی را دیده باشد*
نوشته شده بود — فیلدهایی (`visit_id`, `rep_id`, `city`, `created_at`)
نگاشت شده بودند که اصلاً در داده‌ی واقعی وجود نداشتند.

**۱۰:۰۷–۱۰:۴۵ – مستندات از کنترل خارج شد، بعد جمع‌وجور شد.** یک
`VERIFY.md` مفصل به‌همراه یک اسکریپت تأیید نوشته شد تا هر ادعای بررسی
به‌طور مستقل قابل بررسی باشد. کمی بعد این حجم مستندات جمع شد:
`VERIFY.md` حذف شد، سند باقی‌مانده (`PHASE0_REMAINING.md`) کوتاه‌تر
شد، و اسکریپت تأیید ساده‌تر شد. درس: پیش‌فرض باید ساده‌ترین راهی
باشد که کار می‌کند؛ پیچیدگی فقط وقتی اضافه شود که واقعاً یک استفاده‌ی
دوم داشته باشد.

**۱۰:۴۵–۱۰:۵۱ – تنظیمات export روی اسکیمای واقعی تنظیم شد.**
`configs/export.yaml` بازنویسی شد تا با شکل واقعی `atpg` هم‌خوان
باشد: مبتنی بر GridFS، فیلتر شده روی `photo_type: shelf` (عکس‌ها چند
نوع دارند؛ فقط یکی از آن‌ها عکاسی واقعی از قفسه است)، و جوین‌شده با
مجموعه‌ی `location` برای به‌دست‌آوردن منطقه، چون خود عکس منطقه را
مستقیماً حمل نمی‌کند. هر کدام از این‌ها روی داده‌ی زنده تأیید شد،
نه فقط روی تست‌ها.

**۱۴:۱۱ – عکس‌های HEIC بی‌سروصدا ناپدید می‌شدند.** عکس‌های آیفون
به‌صورت پیش‌فرض HEIC هستند، فرمتی که Pillow به‌تنهایی نمی‌تواند
بخواند — هر آپلود HEIC در حین export بی‌سروصدا حذف می‌شد، بدون خطا،
بدون هشدار، بدون هیچ اثری در manifest. کتابخانه‌ی `pillow-heif` اضافه
شد؛ روی داده‌ی زنده تأیید شد که از یک نمونه‌ی ۲۵ تایی، ۸ عکس HEIC
بودند و همه اکنون درست دیکد می‌شوند.

**۱۴:۳۱ – مورد بزرگ روز: store_code در واقع یک فروشگاه نیست.**
جرقه‌اش یک مشاهده‌ی دو خطی از رابط کاربری برنامه بود — دو عدد متفاوت
برای یک فروشگاه نمایش داده می‌شد، با برچسب «کد ثابت» و «کد ثبت». این
موضوع خیلی مهم بود: `store_code` روی یک عکس در واقع یک **کد ثبت
مخصوص بازدید** است، و هر بار که فروشگاه دوباره ثبت می‌شود، عوض
می‌شود — به‌صورت زنده تأیید شد که یک فروشگاه در طول زمان ۵ کد متفاوت
داشته. منطق تقسیم‌بندی train/test فرض می‌کرد که «تقسیم بر اساس
فروشگاه» از نشت عکس‌های تقریباً تکراری بین train و test جلوگیری
می‌کند، اما در واقع بر اساس *بازدید* تقسیم می‌شد — یک فروشگاه فیزیکی
واحد، در دو بازدید مختلف، می‌توانست هم در train و هم در test بیفتد.
با یک جوین دوم (`location.code -> permanent_id`) اصلاح شد تا هویت
واقعی و پایدار فروشگاه بازیابی شود؛ کد خام هر بازدید حالا درست در
ستون `visit_id` قرار می‌گیرد، جایی که قبلاً همیشه خالی بود.

**بعدازظهر — پاک‌سازی Docker روی apps server (بی‌ربط به کد، ولی
واقعی).** apps server (۳۰ کانتینر، شامل MongoDB تولید و Label Studio)
روی ٪۷۹ فضای دیسک بود، فقط ۲۰ گیگابایت آزاد. حجم زیادی از build
cache و ایمیج‌های بلااستفاده‌ی Docker پیدا شد که قابل پاک‌سازی بودند
— بخش‌های امن پاک شدند (فقط build cache و ایمیج‌های dangling، هیچ‌چیز
تگ‌خورده یا در حال استفاده)، حدود ۱۵ گیگابایت آزاد شد. دیسک از ٪۷۹
به ٪۶۳ رسید. همچنین تأیید شد که حذف یک ایمیج بلااستفاده‌ی `mongo:7`
توسط کاربر بی‌خطر بوده — MongoDB تولید روی `mongo:latest` اجرا
می‌شود و دست‌نخورده باقی ماند.

**۱۶:۲۶ – راه‌اندازی سرور GPU برای آموزش مدل.** دسترسی SSH بدون رمز
به کامپیوتر یکی از همکاران در شبکه‌ی داخلی (RTX 4060 Ti، ۸ گیگابایت
VRAM) برای آموزش مدل راه‌اندازی شد — عمداً فقط به‌عنوان *هدف اجرا*
نگه داشته شد، نه محیط توسعه، چون سخت‌افزار مشترک است. `uv` نصب شد،
ریپو سینک شد، `torch`/`ultralytics` نصب شدند (حدود ۲۵ دقیقه طول
کشید، بیشترش دانلود wheel‌های CUDA بود — چیزی گیر نکرده بود).
`torch.cuda.is_available() == True` تأیید شد و GPU درست شناسایی شد.
اسکریپت `scripts/sync_to_gpu.sh` اضافه شد تا آپدیت‌های بعدی کد/تنظیمات
فقط یک rsync باشند.

**۱۶:۳۶ – بستن ریسک «ارسال دوباره‌ی همان عکس به برچسب‌زن‌ها».**
دسته‌های برچسب‌گذاری (`label_batch_01.txt`, `_02.txt`, ...) قبلاً
در هر اجرای `shelf-splits` کاملاً بازنویسی می‌شدند — یک export جدید
که عکس تازه می‌آورد می‌توانست بی‌سروصدا عکس‌های *متفاوتی* را زیر همان
نام فایل جایگزین کند، بدون هیچ راهی برای فهمیدن این‌که برچسب‌زن‌ها
قبلاً چه چیزی دیده بودند. حالا دسته‌ها شماره‌دار و تجمعی هستند: عکسی
که یک‌بار در یک دسته ظاهر شده باشد، دیگر هرگز در دسته‌ی بعدی انتخاب
نمی‌شود. روی نمونه‌ی ۲۹۵ عکسی به‌صورت زنده تأیید شد: اجرای دوباره‌ی
split درست یک `label_batch_02.txt` تازه ساخت، فقط با عکس‌های باقی‌مانده
و هرگز ارسال‌نشده.

**هنوز گیر / منتظر یک نفر دیگر، پایان روز:**
- export واقعی تولید (حدود ۹٬۲۰۷ عکس، حدود ۲۸ گیگابایت) — منتظر
  کاربر که خودش اجرایش کند.
- لیست کلاس‌ها و پک‌شات‌ها از فروش/بازاریابی — کاربر چند پک‌شات و یک
  فایل اکسل از لیست کلاس‌ها را همین امروز در دست دارد.
- این‌که آیا عکس‌های نوع `sardar` جزو عکاسی قفسه حساب می‌شوند یا نه
  (اگر بله، حجم داده‌ی آموزشی تقریباً دو برابر می‌شود) — یک تصمیم
  کسب‌وکاری است.

**درس روز:** تقریباً هر باگ واقعی که امروز پیدا شد (حذف بی‌صدای
HEIC، اشتباه فروشگاه/بازدید، ریسک بازنویسی دسته‌ها) از طریق *اجرای
واقعی pipeline روی داده‌ی زنده* و خواندن دقیق خروجی پیدا شد، نه از
خواندن کد روی کاغذ. باید ادامه داد: اجراهای کوچک با `--limit` روی
داده‌ی تولید، زود و مکرر.
