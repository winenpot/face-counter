# Graph Report - face-counter  (2026-10-04)

## Corpus Check
- 63 files · ~176,906 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 5, .example 2, .csv 1)

## Summary
- 776 nodes · 1195 edges · 46 communities (36 shown, 10 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 33 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a7b0ccb9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- cli.py
- build_classes.py
- setup_project.py
- test_evaluation.py
- prepare_label_studio.py
- detector_bakeoff.py
- export_photos.py
- test_phase0.py
- test_taxonomy.py
- test_bakeoff.py
- test_setup_project.py
- test_build_classes.py
- make_splits.py
- test_label_prep.py
- test_gallery_folders.py
- My track
- deploy_label_studio.sh
- face_counter/__init__.py
- post-commit
- sync_from_hemin.sh
- sync_to_hemin.sh
- face-counter
- Proposal: AI-Based Product Face Counting Web Service
- Labeling strategy — how 9,500 photos get labeled by a small team
- 1. Error analysis
- Label Studio deployment
- Labeling the test set for the pilot: step by step
- Shelf Detector Roadmap
- راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه
- face-counter (Shelf Detector)
- Detector alternatives — the knobs we deliberately left reachable
- Labeling guide: shelf product faces
- Dataset Preparation
- Issue: count faces, not every object
- Test-set label review, 2026-09-28
- face-counter — Vault Home
- CLAUDE.md
- Detector step zero: report and evaluation plan
- Phase 0 — what is left
- 7. Evaluation metrics
- Requests to send (Phase 0, day 1)
- Frozen: pilot test-set labels, v1 (2026-09-30)
- investigations/
- AGENTS.md

## God Nodes (most connected - your core abstractions)
1. `Proposal: AI-Based Product Face Counting Web Service` - 19 edges
2. `main()` - 13 edges
3. `FakeLS` - 12 edges
4. `Shelf Detector Roadmap` - 12 edges
5. `evaluate()` - 11 edges
6. `export()` - 11 edges
7. `_scope()` - 11 edges
8. `Labeling the test set for the pilot: step by step` - 11 edges
9. `evaluate()` - 10 edges
10. `load_config()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `1. Fix the test set` --references--> `diverse_sample()`  [INFERRED]
  docs/PHASE0_REMAINING.md → src/face_counter/label_studio/make_splits.py
- `[ ] Y4. Gold-val selection (pilot step 3b; independent)` --references--> `diverse_sample()`  [INFERRED]
  .hermes/plans/2026-09-29_pilot-parallel-tracks.md → src/face_counter/label_studio/make_splits.py
- `Done` --references--> `group_key()`  [INFERRED]
  docs/PHASE0_REMAINING.md → src/face_counter/label_studio/make_splits.py
- `To do, in order` --references--> `diverse_sample()`  [INFERRED]
  docs/PILOT.md → src/face_counter/label_studio/make_splits.py
- `1405/07/07 (2026-09-29) — the Persian font finally renders` --references--> `labeling_config()`  [INFERRED]
  LOGS.md → src/face_counter/label_studio/prepare_label_studio.py

## Import Cycles
- None detected.

## Communities (46 total, 10 thin omitted)

### Community 0 - "cli.py"
Cohesion: 0.06
Nodes (55): collections_abc, Counter, dataclasses, json, math, random, bootstrap_ci(), Percentile bootstrap over photos. 30 test photos make small differences noise;… (+47 more)

### Community 1 - "build_classes.py"
Cohesion: 0.06
Nodes (50): Require gitmoji + Conventional Commit subjects, and cap length (stdlib only).…, openpyxl, pathlib, pil, pymongo, pymongo_errors, re, build_classes() (+42 more)

### Community 2 - "setup_project.py"
Cohesion: 0.08
Nodes (37): contextlib, socket, copy_photos(), ensure_project(), ensure_storage(), existing_photo_ids(), _free_port(), import_tasks() (+29 more)

### Community 3 - "test_evaluation.py"
Cohesion: 0.13
Nodes (32): _ann(), _box(), _choice(), _dets(), _labeled(), _photo(), Evaluation against Label Studio exports: parsing, box matching, detector…, A Label Studio rectangle in percent of a W x H displayed image, given in pixels. (+24 more)

### Community 4 - "prepare_label_studio.py"
Cohesion: 0.07
Nodes (43): argparse, csv, [x] Y1. Named targeted competitors in the taxonomy (after U1), 1405/07/04 (2026-09-26) — test set frozen, labeling strategy written, and the first three detectors actually ran, 1405/07/05 (2026-09-27) — business answers, a taxonomy that can grow, and a two-brand pilot, 1405/07/06 (2026-09-28) — back up to speed, Persian labeling screen, test set reviewed, 1405/07/07 (2026-09-29) — the Persian font finally renders, 1405/07/08 (2026-09-30) — faces, not objects (+35 more)

### Community 5 - "detector_bakeoff.py"
Cohesion: 0.12
Nodes (31): Detector, Image, build_detr_r50_sku110k(), detect(), build_sku110k_yolo11s(), build_yolo26l_sku110k(), build_yoloe_26s(), clean_legacy_config() (+23 more)

### Community 6 - "export_photos.py"
Cohesion: 0.11
Nodes (27): Any, datetime, io, os, pillow_heif, export(), _ext_for(), iter_photo_records() (+19 more)

### Community 7 - "test_phase0.py"
Cohesion: 0.11
Nodes (30): Done, mongomock, mongomock_gridfs, build_fake_db(), _cfg(), fake_db(), _jpeg(), fixture (+22 more)

### Community 8 - "test_taxonomy.py"
Cohesion: 0.13
Nodes (21): Class list <-> reporting categories: the rules that keep labels valid as the…, _reporting(), _row(), _scope(), test_a_pack_type_in_two_categories_is_rejected(), test_brand_detail_scope_names_brand_and_pack_type_not_skus(), test_category_of_maps_pack_type_and_returns_none_outside_reporting(), test_consistent_class_list_has_no_problems() (+13 more)

### Community 9 - "test_bakeoff.py"
Cohesion: 0.09
Nodes (11): Detector bake-off plumbing, without any model: fake detectors, real outputs.…, A JPEG stored landscape with EXIF orientation 6 (displays as portrait)., _sideways_jpeg(), test_load_image_applies_exif_orientation(), test_main_records_the_prompts_it_used(), test_missing_weights_fail_fast_with_download_instructions(), test_run_writes_counts_jsonl_overlays_and_tasks(), test_weights_path_is_resolved_against_the_project_root() (+3 more)

### Community 10 - "test_setup_project.py"
Cohesion: 0.12
Nodes (17): FakeLS, parametrize, Tests for shelf-ls-setup (face_counter.label_studio.setup_project). Everything…, The test set's project is the evaluation ground truth: no config update, no…, Just enough of the Label Studio API for the setup flow., _task(), test_a_frozen_project_is_never_written_to(), test_a_task_file_listing_a_photo_twice_is_rejected() (+9 more)

### Community 11 - "test_build_classes.py"
Cohesion: 0.10
Nodes (3): Tests for scripts/build_classes.py's parsing heuristics. No .xlsm fixture (the…, test_legacy_file_without_source_or_pack_type_is_read_as_invoice_rows(), _write()

### Community 12 - "make_splits.py"
Cohesion: 0.18
Nodes (19): collections, DataFrame, hashlib, logging, pandas, _already_sent(), diverse_sample(), group_key() (+11 more)

### Community 13 - "test_label_prep.py"
Cohesion: 0.17
Nodes (13): _labels(), _pred(), Label Studio inputs for the pilot: labeling config, tasks with pre-drawn boxes,…, _tasks(), test_a_photo_without_predictions_fails_loudly(), test_a_predicted_label_missing_from_the_config_fails_loudly(), test_click_only_labels_leave_keys_1_to_7_where_they_were(), test_every_named_label_gets_its_own_colour_and_none_looks_grey() (+5 more)

### Community 14 - "test_gallery_folders.py"
Cohesion: 0.08
Nodes (25): pytest, shutil, skipif, subprocess, _code_lines(), parametrize, Path, Static checks on scripts/deploy_label_studio.sh and its git reminder hook. The… (+17 more)

### Community 15 - "My track"
Cohesion: 0.07
Nodes (29): Current checkpoint (2026-09-30, end of day), Deferred, not dropped, Pilot: two brands, cans and glass bottles, Scope (decided 2026-09-27, metric narrowed 2026-09-29), To do, in order, Decision recorded 2026-09-29 (changes the pilot's metric), My track, Open questions (+21 more)

### Community 16 - "deploy_label_studio.sh"
Cohesion: 0.39
Nodes (7): die(), images_of(), on_server(), say(), deploy_label_studio.sh script, step(), warn()

### Community 23 - "Proposal: AI-Based Product Face Counting Web Service"
Cohesion: 0.07
Nodes (27): 10. Deployment, 11. Performance Considerations, 12. Security, 13. Monitoring and Logging, 14. Evaluation Metrics, 15. Development Phases, 16. Risks and Limitations, 17. Expected Result (+19 more)

### Community 24 - "Labeling strategy — how 9,500 photos get labeled by a small team"
Cohesion: 0.14
Nodes (14): 1. The job is not "label 9,500 photos", 2. Separate *where* from *what*, 3. Cluster labeling — how identity scales, 4. Competitors: category, not SKU, 5. Tools: which free options fit, and which do not, 6. Guardrails, 7. Starting sequence, 8. Weekly rounds, and what survives a wider taxonomy (+6 more)

### Community 25 - "1. Error analysis"
Cohesion: 0.15
Nodes (13): 1. Error analysis, 2. Hyperparameter tuning, 3. Human-in-the-loop — and why it is *not* RLHF, Back-row is the headline error here, Error analysis, tuning, and the human-in-the-loop, Honesty rules, Practices that matter more than the algorithm, RLHF is a different tool for a different problem (+5 more)

### Community 26 - "Label Studio deployment"
Cohesion: 0.17
Nodes (11): Deploying changes, First run, Label Studio deployment, Labeling in batches on the server, Later: serving from GridFS instead of copies, Loading photos, Migrating an existing instance, Network exposure (+3 more)

### Community 27 - "Labeling the test set for the pilot: step by step"
Cohesion: 0.17
Nodes (11): 0. Build the files (on this machine), 1-4. Put it on the server: one command, 1. Upload the photos to the server, 2. Create the project (in the browser, once), 3. Project settings, 4. Import the tasks, 5. Label, 6. The three labeling-guide screenshots (done 2026-09-27) (+3 more)

### Community 28 - "Shelf Detector Roadmap"
Cohesion: 0.17
Nodes (12): Approach, Architecture, Phase 0 — Foundations (days 1–3), Phase 1 — Working pipeline (days 4–10), Phase 2 — MVP demo (days 11–15), Phase 3 — Error analysis and the data flywheel (month 2), Phase 4 — Production (month 3+), Resources and dependencies (+4 more)

### Community 29 - "راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه"
Cohesion: 0.18
Nodes (11): دکمه‌ها و تنظیمات Label Studio (انگلیسی می‌مانند), راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه, سه بخش پایین عکس, موارد خاص, نمونه‌ها, پایلوت: قوطی‌ها و بطری‌های شیشه‌ای, پیش از ثبت (Submit), چه چیزی را کادر بکشیم (+3 more)

### Community 30 - "face-counter (Shelf Detector)"
Cohesion: 0.18
Nodes (10): Commit messages, Data, Disk, face-counter (Shelf Detector), Finding your field paths, Labeling (Label Studio), Layout, Phase 0 workflow (+2 more)

### Community 31 - "Detector alternatives — the knobs we deliberately left reachable"
Cohesion: 0.20
Nodes (10): Constraints, Detector alternatives — the knobs we deliberately left reachable, First, three things the roadmap's phrasing hides, Open-vocabulary detection: YOLOE-26 as a third candidate, Sources, The candidates, The landscape, and why it moved, The shortcut we should try before training anything (+2 more)

### Community 32 - "Labeling guide: shelf product faces"
Cohesion: 0.20
Nodes (10): Before you submit, Class names, Edge cases, Examples, Face or the unit behind it?, Labeling guide: shelf product faces, Pilot: cans and glass bottles (test set, from 2026-09-27), Pre-drawn boxes and their numbers (+2 more)

### Community 33 - "Dataset Preparation"
Cohesion: 0.22
Nodes (8): 1. Data Collection, 2. Organization & Initial Preprocessing, 3. Annotation, 4. Annotation Validation & Dataset Quality Checks, 5. Dataset Splitting, 6. Dataset Versioning, Dataset Preparation, Recommended Tooling

### Community 34 - "Issue: count faces, not every object"
Cohesion: 0.22
Nodes (9): 1. The problem, 2. What a face is, 3. Where the plan goes wrong today, 4. What "done" means, 5. Open decisions (need the BI analyst), 6. Approach options, 7. Plan, 8. Where this is written down (+1 more)

### Community 35 - "Test-set label review, 2026-09-28"
Cohesion: 0.22
Nodes (8): 1. Name the unnamed cans and glass bottles, 2. Small fixes, 3. Then, Already good, Numbers from this export (for reference, not final), Test-set label review, 2026-09-28, To do, in order, Verdict: labels not final yet

### Community 36 - "face-counter — Vault Home"
Cohesion: 0.22
Nodes (8): apps server, db server, face-counter — Vault Home, Future: FastAPI inference service (Phase 2), Infrastructure, Label Studio deployment, Status (2026-09-28, superseded), Status (2026-09-30)

### Community 37 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture notes, Commands, Data pipeline, Label Studio is a separate app, Project state, Taxonomy: labels, categories, scope

### Community 39 - "Detector step zero: report and evaluation plan"
Cohesion: 0.25
Nodes (7): 1. What was done, 2. Measured results (no ground truth yet), 3. Visual review of the overlays, 4. Interpretation, 5. Limitations, 6. Next steps, Detector step zero: report and evaluation plan

### Community 40 - "Phase 0 — what is left"
Cohesion: 0.33
Nodes (5): 1. Fix the test set, 2. Data quality, 3. Blocked on the business, 4. Then Phase 1, Phase 0 — what is left

### Community 41 - "7. Evaluation metrics"
Cohesion: 0.40
Nodes (5): 7. Evaluation metrics, Business output, Operational, Stage 1: detector (finds every face), Stage 2: identifier (names each box)

### Community 42 - "Requests to send (Phase 0, day 1)"
Cohesion: 0.40
Nodes (4): 1. Class list (to sales / business analysts), 2. Packshots (to marketing), 3. Original uploads before recompression (to the field app developer), Requests to send (Phase 0, day 1)

## Knowledge Gaps
- **191 isolated node(s):** `face-counter`, `sync_from_hemin.sh script`, `sync_to_hemin.sh script`, `Decision recorded 2026-09-29 (changes the pilot's metric)`, `Two tracks` (+186 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 405 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `To do, in order` connect `My track` to `make_splits.py`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `Pilot: two brands, cans and glass bottles` connect `My track` to `ISSUE_FACES_NOT_OBJECTS.md`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `Phase 0 — what is left` connect `Phase 0 — what is left` to `test_phase0.py`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **What connects `face-counter`, `sync_from_hemin.sh script`, `sync_to_hemin.sh script` to the rest of the system?**
  _191 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `cli.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05704365079365079 - nodes in this community are weakly interconnected._
- **Should `build_classes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `setup_project.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07641196013289037 - nodes in this community are weakly interconnected._