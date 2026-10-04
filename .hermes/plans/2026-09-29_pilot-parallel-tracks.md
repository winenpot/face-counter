g# Pilot, from labeled test set to a first share-of-shelf number

> Work this task by task, in order, per track. Progress markers:
> `[ ]` not started · `[~]` in progress · `[x]` done. Ad-hoc requests go into
> the task they belong to, not in between. `docs/PILOT.md` is still the
> project's to-do list; this plan is how its steps 3–6 get done, and task Y0
> writes the decisions back into it.

**Goal:** a first honest number, per category (cans, glass): our share
against the targeted competitors on the frozen 30-photo test set, plus
detector recall, with bootstrap confidence intervals.

**Tech stack:** existing `face_counter` package (pandas, Pillow, PyYAML),
pytest with small hand-made fixtures, Label Studio JSON exports. No new
runtime dependencies until task Y7 (embeddings, analytics group only).

---

## Where we are (2026-09-29)

| Level | State |
| --- | --- |
| Phase 0 foundations | Done (2026-09-27). |
| Phase 1 / pilot step 1, pick pre-label detector | Done: `yolo26l-sku110k`. |
| Pilot step 2, drink photos in test set | Done in practice: 22 of 30 contain cans or glass (review export). |
| Pilot step 3, label test set | **Passed by decision, 2026-09-29** (below). Needs the targeted-competitor rename pass and 15 min of hygiene before the final export. |
| Pilot steps 3b, 4, 4b, 5, 6, 6b, 7, 8 | Not started. |
| Phases 2–4 (API, flywheel, production) | Not started. |

### Decision recorded 2026-09-29 (changes the pilot's metric)

- Grey `product` boxes stay grey. They are not counted in the pilot's number;
  they matter later, when more product types enter scope.
- Only **targeted competitors** are named. Coca-Cola, Bear, etc. are not
  targeted. The list (U1, answered 2026-09-29), 10 labels:
  Icy-Monkey (ایسی مانکی), Hoffenberg (هوفنبرگ), Laimon-Fresh (لایمون فرش):
  [2026-10-04: Laimon-Fresh glass retired, 9 labels now]
  can + glass. Fizzio (فیزیو), Freshy-Day (فرش دی), Genius (جنیوس),
  Sunich-Cool (سن ایچ کول): glass only ("bottles", read as glass because
  plastic is outside the pilot; to be confirmed).
- **A box with no label counts as `product` (key 7).** It is not an error and
  needs no fixing in LS; the evaluation parser maps it.
- Keys 1-7 stay as they are. The 10 new labels have **no hotkey**; they are
  picked by clicking the chip.
- So the pilot reports, per category:
  **share = ours / (ours + targeted competitors)**, "share against the rivals
  we track". This is not share of *all* cans; the doc must say so plainly,
  because the two numbers are not comparable when the scope widens.

### What this breaks, stated as findings (the extensibility test, step 8, early)

1. `taxonomy.problems()` (`src/face_counter/utils/taxonomy.py:79-82`) forbids a
   non-`COMPETITOR` brand with `is_ours=0`. Named competitors need a code
   change. Foreseen by `ROADMAP.md` ("top 20–30 get names"), but it is a code
   change, so it goes in the findings.
2. The 33 `COMPETITOR_canned` + 99 `COMPETITOR_glass` boxes already labeled mix
   targeted and untargeted brands. They need one rename pass (132 boxes, not
   2,650). A targeted can still grey on some photo would be missed; the rename
   pass looks for those too.
3. `PILOT.md` step 4 says "competitors need no gallery". Now the targeted ones
   do: the matcher has to name them.

---

## Two tracks

`You` = browser, business, GPU box, eyes. `Me` = code and docs in this repo.
Arrows are the only waits between tracks.

```
You:  U1 list ─┐   U2 hygiene   U3 rename pass ──> U4 final export   U5 gold-val review   U6 gallery pick   U7 label gold val
               v                   ^                  |                 ^                    |
Me:   Y0 docs  Y1 targeted classes ┘  Y2 detector eval (now)  Y3 identity+share eval <─┘   Y4 gold-val list ┘  Y5 gallery  Y6 can/glass  Y7 matcher
```

Start immediately, in parallel: **U1 + U2** (you), **Y0 + Y2** (me). Neither
blocks the other.

---

## Your track

### [x] U1. Send the full targeted-competitor list (blocks Y1)
Per brand: name as it should appear, and which pack types exist (can, glass,
both). E.g. `Icy-Monkeys: canned, glass`. Five minutes, but it gates the
rename pass.

### [x] U2. Label Studio hygiene, ~15 min (independent)
Done 2026-09-30 (except the #18 draft and a few duplicate grey boxes, left as
known in `data/label_studio/FROZEN.md`).
From `docs/reports/2026-09-28_test_set_label_review.md` §2. These are data
integrity, not naming, so they still matter:
- ~~#15: 9 boxes with no label~~ dropped 2026-09-29: no label = `product`.
- #6, #17: open, press **Update** (unsaved drafts).
- #23: delete the older of two submissions.
- #2, #15, #18, #19: drop the near-duplicate box pairs.
- #20, #21: check the corner/back glass bottles only if a targeted brand or
  ours is there.

### [x] U3. Rename pass (after Y1 pushes the new labels)
Done 2026-09-30.
Visit each photo with a `COMPETITOR_canned`/`COMPETITOR_glass` box; retag the
targeted ones. Also retag any targeted can/bottle still grey. Everything else
stays as it is.

### [x] U4. Final export (after U3)
Done 2026-09-30, frozen as `pilot-test-v1-2026-09-30.json` (not
`pilot-test-final.json`; see `data/label_studio/FROZEN.md`).
`docs/PILOT_LABELING.md` §7 → `data/label_studio/exports/pilot-test-final.json`.
Tell me; Y3 re-runs on it and the labels are marked final.

### [ ] U5. Review the gold-val contact sheet (after Y4)
Swap non-shelf photos, as was done for the test set.

### [ ] U6. Gallery images for targeted competitors (after Y1, any time)
2–5 packshots per targeted brand × pack type (web, marketing, or phone
photos). Drop into `configs/Product/competitors/<Brand>_<pack_type>/`.
Ours come from the invoice images already on disk.

### [ ] U7. Label the gold-val set (after U5 and Y4's project exists)
Same guide, same labels, one pass. ~4 h at the test set's pace.

---

## My track

Order: Y0, **Y1**, Y2, ... (Y1 pulled ahead of Y2 on 2026-09-29, once U1
arrived: your rename pass waits on it, Y2 blocks nobody).

### [x] Y0. Write the 2026-09-29 decision into the docs
Done 2026-09-29: PILOT.md (scope, step 3, step 4, step 8 findings),
scope.yaml, review report, labeling guide EN + FA (targeted table).

**Files:** `docs/PILOT.md` (scope section + step 3 marked passed + step 4
note), `configs/scope.yaml` (comment block), `docs/reports/2026-09-28_test_set_label_review.md`
(close §1 with the decision).
**Verify:** `uv run pytest` still green (docs only). Commit:
`📝 docs(pilot): share against targeted competitors; grey boxes stay grey`.

### [x] Y2. Detector evaluation, stage 1 (start now, needs nothing from you)
Done 2026-09-30, together with Y3's ground-truth side: `shelf-eval`.
**Objective:** real recall/precision for all 4 bake-off models against the
labeled test set.
**Files:**
- Create `src/face_counter/evaluation/__init__.py`, `evaluation/ls_export.py`
  (parse LS export → per-photo boxes in pixels, labels, scene tag; use the
  latest submitted annotation, ignore drafts), `evaluation/match.py` (IoU,
  greedy one-to-one matching at 0.5, AP50, AP50-95), `evaluation/detector.py`
  (per-model metrics table + per-scene slices + duplicate rate + count MAE),
  `evaluation/bootstrap.py` (percentile CI over photos, fixed seed).
- Create `tests/test_evaluation.py` with hand-made fixtures (2 photos, known
  boxes, known answers; one EXIF-rotated case since LS stores percentages of
  the rotated image).
- Add script `shelf-eval = "face_counter.evaluation.cli:main"` to `pyproject.toml`.
**Inputs:** `data/label_studio/exports/pilot-test-2026-09-28-review.json`,
`runs/bakeoff/20260927-114232/detections.jsonl`.
**Output:** `runs/eval/<stamp>/detector.csv` + a short markdown summary.
**Verify:** `uv run pytest tests/test_evaluation.py`, then
`uv run shelf-eval detector --labels <export> --detections <jsonl>`.
**Caveat to print in the summary:** labels were seeded from YOLO26l's boxes,
so its numbers are biased upward (anchoring). YOLO11s/DETR/YOLOE are the
fairer comparison; the bias shrinks where boxes were redrawn (#1–#23).

### [x] Y1. Named targeted competitors in the taxonomy (after U1)
Done 2026-09-29: 10 rows in classes.csv (via build_classes' own writer,
byte-stable), `competitors:` in scope.yaml, taxonomy + label-prep code, 7 new
tests (103 pass). Live project 3 updated from the hand-kept Persian config
(`labeling_config_scope_fa.xml`, previous copy `.before-targeted.xml`); backup
export + config `exports/pilot-test-2026-09-29-before-targeted.*` taken first;
verified after: 17 labels live, keys 1-7 unchanged, all 30 annotations
byte-identical. **U3 is unblocked.**

**Objective:** `IcyMonkeys_canned`-style competitor classes, no relabel of
anything else.
**Files:**
- `configs/classes.csv`: `source=manual`, `is_ours=0`, real brand, one row per
  brand × pack type. `COMPETITOR_<pack>` stays as the untargeted catch-all.
- `configs/scope.yaml`: `competitors: [Icy-Monkeys, ...]`.
- `src/face_counter/utils/taxonomy.py`: allow `is_ours=0` with a real brand;
  `Scope` gains `competitors`; `scoped_label_names` emits them.
- `tests/test_taxonomy.py`: named competitor is valid; a named competitor
  with `is_ours=1` is not; scoped labels include them at `detail: brand`.
**Push to LS:** back up first (export JSON + config XML, as the existing
`before-*` files), then `uv run shelf-ls-setup` updates project 3's config.
Adding labels is safe; removing a label in use is refused by LS, and we remove
none. Hotkeys: current 1–6 must not move, new ones go after (check
`labeling_config()` ordering in `prepare_label_studio.py:77`).
**Verify:** pytest green; open one task in LS, old labels intact, new ones
present. Record finding 1 in `PILOT.md` step 8.

### [~] Y3. Identity and share-of-shelf evaluation (after Y1; final run after U4)
2026-09-30: ground-truth share per category, both denominators, per brand,
bootstrap CI, per-photo table — in `shelf-eval`. Waits on U4 for the final
run and on Y7 for the predicted side (share error, 2x2 confusion).
**Files:** `evaluation/share.py`, extend `cli.py` and tests.
- Per photo, per category: ours count, targeted count, share. Photos with
  zero ours+targeted in a category are left out of that category's share
  (not scored 0).
- Ours-vs-targeted 2×2 confusion (once a predictor exists; until Y7 it only
  reports the ground-truth side).
- Per-brand count table, bootstrap CI.
**Verify:** fixture tests with known shares; run on the review export now,
re-run on `pilot-test-final.json` after U4.

### [ ] Y4. Gold-val selection (pilot step 3b; independent)
**Files:** `src/face_counter/label_studio/make_splits.py`: new
`--gold-val N` path that runs `diverse_sample` over **val** rows and writes
`data/splits/gold_val.txt`; refuses to overwrite it; never touches
`test_labeling.txt` or the salt. `.gitignore` exception for the new file.
Test in `tests/test_phase0.py`: only val-split stores, deterministic, refuses
overwrite, test list byte-identical after the run.
Then a contact sheet for U5, and after U5 a second LS project
(`pilot-gold-val`, same config incl. the existing `scene` field) via
`shelf-ls-setup` with the new list.
**Needs:** the manifest on this machine (`sync_from_hemin.sh --with-manifest`);
photos for the contact sheet are on the GPU box, so the sheet is built there.

### [ ] Y5. Gallery builder (pilot step 4; after Y1)
Script that assembles `data/gallery/<brand>_<pack_type>/` from
`configs/Product/from_invoice/` (ours, collapsed to brand level per
`scope.yaml` detail) and `configs/Product/competitors/` (U6). Report classes
with < 2 images. Test with a temp dir fixture.

### [ ] Y6. Can vs glass for unmatched crops (pilot step 5; spike)
Time-boxed spike: CLIP zero-shot "a can" / "a glass bottle" on labeled test
crops (ours + targeted), accuracy reported. Throwaway notebook under
`runs/`, promoted to code only if it works. Runs on the GPU box.

### [ ] Y7. Embedding matcher (pilot step 4b; after Y5)
DINOv2 embeddings, nearest gallery match, threshold tuned on gold-val crops
(never test). Output feeds Y3's confusion matrix. GPU box.

Then: pilot step 6b (fine-tune rounds) and step 7 (`/count`, `/overlay`),
planned separately once Y3 produces a number.

---

## Risks

| Risk | Level | Mitigation |
| --- | --- | --- |
| Metric misread as "share of all cans" | Medium, business-facing | Name it "share vs targeted competitors" everywhere; Y0. |
| Targeted cans left grey are silently missed | Medium | U3 looks for them explicitly; Y3 prints per-photo counts for a spot-check. |
| LS config push breaks existing annotations | Low | Additive only; backup export + config first; LS refuses removing used labels. |
| YOLO26l looks best only because it drew the seed boxes | Medium, decision-facing | Printed caveat in Y2; decisions weigh the other three models. |
| Gold-val code touches the frozen test list | Low, catastrophic | Separate code path, overwrite refusal, byte-identity test on `test_labeling.txt`. |
| 30 photos (22 with drinks) → wide intervals | Certain | Bootstrap CIs on every number; no claims inside the interval. |

## Open questions

1. Full targeted-competitor list (U1).
2. Keep `COMPETITOR_canned/glass` for untargeted ones, or fold them into
   `product`? Plan assumes **keep** (costs nothing, keeps a future "share of
   all cans" possible for those boxes).
3. Uncommitted: `.githooks/commit-msg` and the review report. Yours to commit,
   or should I, as two separate commits?
