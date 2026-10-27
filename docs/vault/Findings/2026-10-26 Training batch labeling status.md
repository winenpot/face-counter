# 2026-10-26 Training batch labeling status

First read of the training-batch projects (PILOT step 6b) after labelers
started. Read-only over the Label Studio API on 2026-10-26 09:07 (+0330),
with the repo's client (`face_counter.label_studio.setup_project`) through an
SSH tunnel. Snapshot only; rerun to refresh.

## Progress

| id | project | tasks | submitted | last submit | labeler(s) |
| --- | --- | --- | --- | --- | --- |
| 3 | pilot-test-cans-glass | 30 | 30 | 2026-09-30 | frozen v1, untouched since |
| 5 | pilot-gold-val | 30 | 30 | 2026-10-05 | project owner |
| 6 | pilot-batch-01 | 250 | 125 | 2026-10-26 | labeler A (+2 extra annotations) |
| 7 | pilot-batch-02 | 250 | 8 | 2026-10-24 | labeler A, owner (1) |
| 8 | pilot-batch-03 | 250 | 78 | 2026-10-25 | labeler B, owner (2) |
| 9 | pilot-batch-04 | 250 | 0 | - | nobody yet |
| 10 | pilot-batch-05 | 250 | 21 | 2026-10-25 | labeler C |

232 of 1,250 batch photos submitted. Labeler identities are in Label Studio,
not here (public repo).

Mean boxes per submitted photo, predicted -> kept: batch-01 96.6 -> 76.5,
batch-02 54.0 -> 33.1, batch-03 80.8 -> 65.9, batch-05 116.4 -> 86.7, gold
81.9 -> 65.7. Labelers delete about 20% of the detector's boxes, the same
order as on gold.

## Quality findings

- **The user's own review (2026-10-26):** quality below the test set's;
  missed boxes and wrong names. Not yet quantified per labeler.
- **14 zero-edit submissions:** annotation identical to the detector's boxes
  (every box kept at IoU > 0.999, none added, deleted or named). Batch-01:
  inner #5, 6, 8, 45, 58, 70, 84, 90, 94, 106, 120 (global ids 67, 68, 70,
  107, 120, 132, 146, 152, 156, 168, 182). Batch-02: #3 (id 315), #6 (id
  318). Batch-05: #8 (id 1070). Open one with
  `.../projects/<project>/data?task=<id>`. Treat as unchecked: on training
  data they teach the detector its own mistakes.
- **More annotations than tasks:** batch-01 127 on 125 tasks, batch-02 10 on
  8, batch-03 79 on 78. Per-task list not yet pulled (SSH to the server
  kept timing out after the first read). Reduce to one annotation per task
  before export.

## What it means for training

- Round 1 trains on face-only boxes, so a wrong brand name barely affects
  the detector; it matters later for identity work. Missed boxes are the
  harmful error: they teach real products as background.
- How many photos are enough is unmeasured. `LABELING_STRATEGY.md` §8
  guesses 300-600 for geometry to plateau; the learning curve decides,
  and it starts with round 1.
- Inter-annotator agreement (`ERROR_ANALYSIS.md` §3) is the way to put a
  number on "the labeling is not good"; not run yet. Correction (same day,
  best-practice audit): agreement measures consistency between labelers,
  not correctness. Per-labeler correctness needs hidden known-answer
  (gold) tasks.

## Per-labeler report (16:55 same day)

`uv run python scripts/labeler_qc.py` (GET-only); full output in
`runs/labeler_qc/2026-10-26/report.txt` (gitignored). Progress since the
morning: batch-01 172 annotations, batch-03 115. Edit rate = (adjusted +
deleted + new + named) / predicted boxes.

| who | photos | median edit rate | deleted | new boxes/photo | named/photo | zero-edit |
| --- | --- | --- | --- | --- | --- | --- |
| owner on gold (reference) | 30 | 39% | 23% | 2.3 | 8.2 | 0 |
| labeler A (batches 01, 02) | 181 | 59% | 32% | 3.7 | 7.5 | 13 |
| labeler B (batch 03) | 115 | 52% | 28% | 5.1 | 7.6 | 0 |
| labeler C (batch 05) | 21 | 54% | 36% | 3.0 | 10.0 | 1 |

Reading: labelers edit *more* than the owner did on gold, and delete more
(28-36% vs 23%). So outside labeler A's 13 zero-edit photos, the problem is
not lack of effort; it may be over-deletion (e.g. deleting real faces) or
wrong edits, which edit rate cannot tell apart. Only hidden gold photos
(T10 next step) measure correctness. Multi-annotation tasks: batch-01 ids
121, 179; batch-02 id 319 (three); batch-03 id 593. Labeler C's median time
per photo is ~15 min, the others ~5 min.

## First three labeling days (from the 2026-10-27 08:24 pull, local time)

No submissions on 22-23 Oct (weekend). Per day, all batches:

| day | photos | median edit rate | deleted | new/photo | named/photo | zero-edit | min/photo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21 Oct | 11 | 44% | 28% | 1.0 | 10.9 | 1 | 28 |
| 24 Oct | 94 | 54% | 29% | 3.1 | 7.1 | 5 | 4.8 |
| 25 Oct | 117 | 52% | 23% | 4.5 | 6.9 | 7 | 4.4 |
| 26 Oct | 110 | 69% | 32% | 5.6 | 9.0 | 1 | 5.4 |
| 27 Oct 00:00-06:00 | 5 | 75% | 40% | 3.0 | 4.0 | 1 | 6.5 |

Cumulative to 27 Oct 06:00: 337 annotations on 332 tasks (batch-01 187,
batch-02 8, batch-03 116, batch-05 21), 15 zero-edit (new: batch-01 #186,
id 248, 27 Oct ~00:30), 4 multi-annotation tasks unchanged.

Owner on gold for reference: 39%, 23%, 2.3, 8.2, 0, 2.5 min.
12 of the 14 zero-edit photos were submitted on 24-25 Oct by one labeler
(batch-01/02); on 26 Oct that labeler edited the most (76%) with 1 zero-edit.

## Reproduce

Probe scripts were scratch (not in the repo): page `GET /api/tasks/?project=<id>`,
keep `total_annotations > 0`, diff each annotation's `rectanglelabels`
against the task's predictions with greedy IoU >= 0.5 matching. Recipe:
`labeling-platform-operations` skill, API reference §3.
