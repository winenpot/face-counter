# Graph Report - face-counter  (2026-10-11)

## Corpus Check
- 95 files · ~698,769 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 5, .example 2, .csv 1)

## Summary
- 1233 nodes · 2113 edges · 91 communities (67 shown, 24 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 151 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2ac8f027`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_identification.py
- Detections
- test_bakeoff.py
- test_phase0.py
- setup_project.py
- Home.md
- test_evaluation.py
- detector_bakeoff.py
- test_gallery_folders.py
- pipeline.py
- test_taxonomy.py
- Proposal: AI-Based Product Face Counting Web Service
- test_predict.py
- bootstrap.py
- test_setup_project.py
- gallery.py
- make_splits.py
- My track
- build
- export_photos.py
- LOGS
- test_build_classes.py
- app.py
- prepare_label_studio.py
- test_onnx_detector.py
- score_model
- Labeling strategy — how 9,500 photos get labeled by a small team
- cmd_tune
- build_classes.py
- 1. Error analysis
- Detector step zero: report and evaluation plan
- match.py
- Photo
- Session Summary — 2026-10-05
- face_counter_identification
- Label Studio deployment
- Labeling the test set for the pilot: step by step
- Shelf Detector Roadmap
- predict_photos
- face-counter (Shelf Detector)
- main
- راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه
- Detector alternatives — the knobs we deliberately left reachable
- Labeling guide: shelf product faces
- Serving strategy: from a synchronous demo API to a queue-backed counting pipeline
- classes_for
- extract_invoice_packshots.py
- load
- [x] Task 2: Extract crop naming from predict.py (refactor, no behaviour change) — DONE 2026-10-10 (commit 25666bc)
- Dataset Preparation
- Issue: count faces, not every object
- Test-set label review, 2026-09-28
- verify_atpg_claims.py
- deploy_label_studio.sh
- score_crops
- CLAUDE.md
- evaluate
- Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14
- Tasks
- face_counter_serving
- face_counter_serving_pipeline
- make_gallery_folders.py
- Phase 0 — what is left
- Demo path: upload a photo, get ours vs tracked rivals (2026-10-04)
- Requests to send (Phase 0, day 1)
- sys
- export_onnx.py
- Pilot: two brands, cans and glass bottles
- render
- Frozen: pilot test-set labels, v1 (2026-09-30)
- face_counter_utils_config
- investigations/
- UnknownContainer
- face_counter/__init__.py
- AGENTS.md
- post-commit
- pull_photos.sh
- sync_from_hemin.sh
- sync_to_hemin.sh
- face_counter_evaluation
- face_counter_evaluation_bootstrap
- face_counter_evaluation_cli
- face_counter_evaluation_ls_export
- face_counter_identification_gallery
- face_counter_label_studio
- face_counter_training
- face_counter_training_detector_bakeoff
- face_counter_utils
- face_counter_utils_taxonomy
- face-counter

## God Nodes (most connected - your core abstractions)
1. `Detections` - 41 edges
2. `_make_pipeline()` - 19 edges
3. `Proposal: AI-Based Product Face Counting Web Service` - 19 edges
4. `Box` - 16 edges
5. `fake_detector()` - 16 edges
6. `Photo` - 15 edges
7. `GalleryImage` - 14 edges
8. `evaluate()` - 13 edges
9. `main()` - 13 edges
10. `_scope()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `What the stage has to do, and what it costs today` --references--> `score_crops()`  [INFERRED]
  docs/PACK_TYPE_ALTERNATIVES.md → src/face_counter/identification/pack_type.py
- `5. Making each count cheaper, ranked by return on atpg` --references--> `score_crops()`  [INFERRED]
  docs/SERVING_STRATEGY.md → src/face_counter/identification/pack_type.py
- `1. Fix the test set` --references--> `diverse_sample()`  [INFERRED]
  docs/PHASE0_REMAINING.md → src/face_counter/label_studio/make_splits.py
- `[ ] Y4. Gold-val selection (pilot step 3b; independent)` --references--> `diverse_sample()`  [INFERRED]
  .hermes/plans/2026-09-29_pilot-parallel-tracks.md → src/face_counter/label_studio/make_splits.py
- `T6 FastAPI service Implementation Plan` --references--> `evaluate()`  [INFERRED]
  .hermes/plans/2026-10-10_111130-t6-fastapi-service.md → src/face_counter/evaluation/share.py

## Import Cycles
- None detected.

## Communities (91 total, 24 thin omitted)

### Community 0 - "test_identification.py"
Cohesion: 0.06
Nodes (35): dict, _ann(), _box(), cfg(), _choice(), _FakeBatchEncoding, _FakeClipModel, _FakeClipProcessor (+27 more)

### Community 1 - "Detections"
Cohesion: 0.07
Nodes (57): Detector, fastapi_testclient, build_detr_r50_sku110k(), detect(), build_sku110k_yolo11s(), build_yolo26l_sku110k(), build_yoloe_26s(), Detections (+49 more)

### Community 2 - "test_bakeoff.py"
Cohesion: 0.06
Nodes (24): Detector bake-off plumbing, without any model: fake detectors, real outputs.…, A JPEG stored landscape with EXIF orientation 6 (displays as portrait)., _sideways_jpeg(), test_load_image_applies_exif_orientation(), test_main_records_the_prompts_it_used(), test_missing_weights_fail_fast_with_download_instructions(), test_run_writes_counts_jsonl_overlays_and_tasks(), test_weights_path_is_resolved_against_the_project_root() (+16 more)

### Community 3 - "test_phase0.py"
Cohesion: 0.08
Nodes (42): Done, mongomock, mongomock_gridfs, build_fake_db(), _cfg(), fake_db(), _gold_setup(), _jpeg() (+34 more)

### Community 4 - "setup_project.py"
Cohesion: 0.08
Nodes (36): socket, copy_photos(), ensure_project(), ensure_storage(), existing_photo_ids(), _free_port(), import_tasks(), is_personal_access_token() (+28 more)

### Community 5 - "Home.md"
Cohesion: 0.06
Nodes (34): Open issues (serving), ADR-0001 Serve the detector through ONNX Runtime only, Consequences, Context, Decision, ADR-0002 Pack-type stage off by default, Consequences, Context (+26 more)

### Community 6 - "test_evaluation.py"
Cohesion: 0.13
Nodes (34): _ann(), _box(), _choice(), _dets(), _labeled(), _photo(), Evaluation against Label Studio exports: parsing, box matching, detector…, A Label Studio rectangle in percent of a W x H displayed image, given in pixels. (+26 more)

### Community 7 - "detector_bakeoff.py"
Cohesion: 0.14
Nodes (23): [x] Task 1b: Detector as ONNX, not ultralytics, inside the service — DONE 2026-10-10 (commit efe921b), clean_legacy_config(), _detr_config(), draw_overlay(), load_image(), ls_prediction(), ls_task(), main() (+15 more)

### Community 8 - "test_gallery_folders.py"
Cohesion: 0.08
Nodes (26): pytest, shutil, skipif, subprocess, _code_lines(), parametrize, Path, Static checks on scripts/deploy_label_studio.sh and its git reminder hook. The… (+18 more)

### Community 9 - "pipeline.py"
Cohesion: 0.13
Nodes (24): argparse, collections, csv, dataclasses, datetime, hashlib, json, logging (+16 more)

### Community 10 - "test_taxonomy.py"
Cohesion: 0.13
Nodes (23): Class list <-> reporting categories: the rules that keep labels valid as the…, _reporting(), _row(), _scope(), test_a_pack_type_in_two_categories_is_rejected(), test_brand_detail_scope_names_brand_and_pack_type_not_skus(), test_category_of_maps_pack_type_and_returns_none_outside_reporting(), test_consistent_class_list_has_no_problems() (+15 more)

### Community 11 - "Proposal: AI-Based Product Face Counting Web Service"
Cohesion: 0.07
Nodes (27): 10. Deployment, 11. Performance Considerations, 12. Security, 13. Monitoring and Logging, 14. Evaluation Metrics, 15. Development Phases, 16. Risks and Limitations, 17. Expected Result (+19 more)

### Community 12 - "test_predict.py"
Cohesion: 0.16
Nodes (17): Box, _make_photo(), Path, Tests for T5: predict.py and cli.py --predict path. All model calls are…, A photo whose image file is missing yields 0 predicted boxes, not an error., A GT photo with no matching detection entry yields 0 predicted boxes., Scene/capture/task metadata from GT Photo is preserved in predicted Photo., End-to-end --predict run with all GPU calls mocked out. (+9 more)

### Community 13 - "bootstrap.py"
Cohesion: 0.22
Nodes (8): collections_abc, random, bootstrap_ci(), Percentile bootstrap over photos. 30 test photos make small differences noise;…, (low, high) of `stat` over `n` resamples of `items` with replacement. Resamples…, T, test_bootstrap_is_deterministic_and_brackets_the_estimate(), typing

### Community 14 - "test_setup_project.py"
Cohesion: 0.12
Nodes (17): FakeLS, parametrize, Tests for shelf-ls-setup (face_counter.label_studio.setup_project). Everything…, The test set's project is the evaluation ground truth: no config update, no…, Just enough of the Label Studio API for the setup flow., _task(), test_a_frozen_project_is_never_written_to(), test_a_task_file_listing_a_photo_twice_is_rejected() (+9 more)

### Community 15 - "gallery.py"
Cohesion: 0.15
Nodes (25): To do, in order, [x] Y1. Named targeted competitors in the taxonomy (after U1), Tasks, in order, Context the implementer needs, (brand, pack_type, role), or None for a box that names nothing., build(), _competitor_images(), GalleryImage (+17 more)

### Community 16 - "make_splits.py"
Cohesion: 0.20
Nodes (22): DataFrame, pandas, _already_sent(), diverse_sample(), group_key(), main(), make_gold_val(), make_splits() (+14 more)

### Community 17 - "My track"
Cohesion: 0.09
Nodes (22): Decision recorded 2026-09-29 (changes the pilot's metric), My track, Open questions, Risks, Two tracks, [ ] U5. Review the gold-val contact sheet (after Y4), [ ] U6. Gallery images for targeted competitors (after Y1, any time), [ ] U7. Label the gold-val set (after U5 and Y4's project exists) (+14 more)

### Community 18 - "build"
Cohesion: 0.10
Nodes (21): 2026-10-10 Serving investigation, Accuracy, Corrections to statements made during the session, Latency and memory, Machines, Things that turned out different from what was assumed, build(), detect() (+13 more)

### Community 19 - "export_photos.py"
Cohesion: 0.13
Nodes (23): Any, export(), _ext_for(), iter_photo_records(), load_existing(), load_join_map(), main(), _parse_date() (+15 more)

### Community 20 - "LOGS"
Cohesion: 0.22
Nodes (8): 1405/07/04 (2026-09-26) — test set frozen, labeling strategy written, and the first three detectors actually ran, 1405/07/05 (2026-09-27) — business answers, a taxonomy that can grow, and a two-brand pilot, 1405/07/06 (2026-09-28) — back up to speed, Persian labeling screen, test set reviewed, 1405/07/08 (2026-09-30) — faces, not objects, 1405/07/08 (2026-09-30) — first numbers, test labels frozen as v1, LOGS, ۱۴۰۵/۰۶/۳۱ (۲۰۲۶-۰۹-۲۲) — یک روز کامل: ادغام shelf-detector، یک باگ واقعی در اسکیما، راه‌اندازی سرور GPU, ۱۴۰۵/۰۷/۰۲ (۲۰۲۶-۰۹-۲۴) — the export finally ran; the model landscape moved; a user tip corrected a wrong call

### Community 21 - "test_build_classes.py"
Cohesion: 0.10
Nodes (3): Tests for scripts/build_classes.py's parsing heuristics. No .xlsm fixture (the…, test_legacy_file_without_source_or_pack_type_is_read_as_invoice_rows(), _write()

### Community 22 - "app.py"
Cohesion: 0.06
Nodes (52): BaseModel, contextlib, Request path, FastAPI, field_validator, [x] Task 3: Pipeline object (serving/pipeline.py) — DONE 2026-10-10 (commit efd27ff), REVISED SCOPE, [x] Task 4: Response schema (serving/schemas.py) — DONE 2026-10-10 (commit 9d5dc0e), [x] Task 5: App and endpoints (serving/app.py) — DONE 2026-10-10 (commit 7b2a923) (+44 more)

### Community 23 - "prepare_label_studio.py"
Cohesion: 0.21
Nodes (14): 1405/07/07 (2026-09-29) — the Persian font finally renders, attach_predictions(), build_tasks(), labeling_config(), main(), Path, Build Label Studio inputs: the labeling config (XML) and a task file for a…, Classes with `"hotkey": False` are click-only: they get no number key and don't… (+6 more)

### Community 24 - "test_onnx_detector.py"
Cohesion: 0.13
Nodes (9): numpy, _FakeInput, _FakeSession, ndarray, Tests for the ONNX Runtime detector (serving/onnx_detector.py). No real ONNX…, _row(), test_build_filters_by_confidence_and_unletterboxes(), test_build_never_imports_ultralytics() (+1 more)

### Community 25 - "score_model"
Cohesion: 0.17
Nodes (15): auc(), collect_crops(), main(), _open(), Image, Path, Return (crops, meta, skipped): one crop per can/glass-named box of every photo., Per prompt set: glass-minus-can cosine score for every crop (> 0 = glass). (+7 more)

### Community 26 - "Labeling strategy — how 9,500 photos get labeled by a small team"
Cohesion: 0.14
Nodes (14): 1. The job is not "label 9,500 photos", 2. Separate *where* from *what*, 3. Cluster labeling — how identity scales, 4. Competitors: category, not SKU, 5. Tools: which free options fit, and which do not, 6. Guardrails, 7. Starting sequence, 8. Weekly rounds, and what survives a wider taxonomy (+6 more)

### Community 27 - "cmd_tune"
Cohesion: 0.10
Nodes (27): Namespace, cmd_gallery(), cmd_tune(), collect_crops(), main(), _open(), Image, Path (+19 more)

### Community 28 - "build_classes.py"
Cohesion: 0.24
Nodes (13): openpyxl, build_classes(), load_descriptions(), main(), merge(), Path, Build configs/classes.csv from a sales/export proforma invoice. The invoice…, Current classes.csv rows. Files from before `source`/`pack_type` existed were… (+5 more)

### Community 29 - "1. Error analysis"
Cohesion: 0.15
Nodes (13): 1. Error analysis, 2. Hyperparameter tuning, 3. Human-in-the-loop — and why it is *not* RLHF, Back-row is the headline error here, Error analysis, tuning, and the human-in-the-loop, Honesty rules, Practices that matter more than the algorithm, RLHF is a different tool for a different problem (+5 more)

### Community 30 - "Detector step zero: report and evaluation plan"
Cohesion: 0.15
Nodes (12): 1. What was done, 2. Measured results (no ground truth yet), 3. Visual review of the overlays, 4. Interpretation, 5. Limitations, 6. Next steps, 7. Evaluation metrics, Business output (+4 more)

### Community 31 - "match.py"
Cohesion: 0.33
Nodes (8): ap50_95(), average_precision(), greedy(), iou(), MatchResult, Box matching and average precision (COCO-style, one class)., Highest score first; each prediction takes the best still-free labeled box with…, Area under the precision-recall curve over all photos, 101-point interpolated.

### Community 32 - "Photo"
Cohesion: 0.43
Nodes (7): evaluate(), _per_photo(), _precision(), Stage 1: how well each detector finds products, against the labeled boxes.…, One row per model: recall, precision, F1, AP50, AP50-95, duplicate rate, count…, _recall(), Photo

### Community 33 - "Session Summary — 2026-10-05"
Cohesion: 0.15
Nodes (12): Code entry points, Current state of every task, Decision needed at the start of tomorrow, hemin notes, Key numbers to remember, Repo layout (what's where), Session Summary — 2026-10-05, T3 — Embedding matcher (commit b114061) (+4 more)

### Community 35 - "Label Studio deployment"
Cohesion: 0.17
Nodes (11): Deploying changes, First run, Label Studio deployment, Labeling in batches on the server, Later: serving from GridFS instead of copies, Loading photos, Migrating an existing instance, Network exposure (+3 more)

### Community 36 - "Labeling the test set for the pilot: step by step"
Cohesion: 0.17
Nodes (11): 0. Build the files (on this machine), 1-4. Put it on the server: one command, 1. Upload the photos to the server, 2. Create the project (in the browser, once), 3. Project settings, 4. Import the tasks, 5. Label, 6. The three labeling-guide screenshots (done 2026-09-27) (+3 more)

### Community 37 - "Shelf Detector Roadmap"
Cohesion: 0.17
Nodes (12): Approach, Architecture, Phase 0 — Foundations (days 1–3), Phase 1 — Working pipeline (days 4–10), Phase 2 — MVP demo (days 11–15), Phase 3 — Error analysis and the data flywheel (month 2), Phase 4 — Production (month 3+), Resources and dependencies (+4 more)

### Community 38 - "predict_photos"
Cohesion: 0.18
Nodes (13): Guarantees and how they are enforced, Known defects, Serving pipeline, [x] Task 6b: Pack-type classifier off for the demo — DONE 2026-10-10, crop_box(), name_crops(), predict_photos(), Image (+5 more)

### Community 39 - "face-counter (Shelf Detector)"
Cohesion: 0.17
Nodes (11): Commit messages, Data, Disk, face-counter (Shelf Detector), Finding your field paths, Labeling (Label Studio), Layout, Phase 0 workflow (+3 more)

### Community 40 - "main"
Cohesion: 0.26
Nodes (12): _fmt(), main(), _pct(), Path, Side-by-side GT vs predicted share for the --predict section of summary.md., summary(), summary_predict_comparison(), _write_csv() (+4 more)

### Community 41 - "راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه"
Cohesion: 0.18
Nodes (11): دکمه‌ها و تنظیمات Label Studio (انگلیسی می‌مانند), راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه, سه بخش پایین عکس, موارد خاص, نمونه‌ها, پایلوت: قوطی‌ها و بطری‌های شیشه‌ای, پیش از ثبت (Submit), چه چیزی را کادر بکشیم (+3 more)

### Community 42 - "Detector alternatives — the knobs we deliberately left reachable"
Cohesion: 0.20
Nodes (10): Constraints, Detector alternatives — the knobs we deliberately left reachable, First, three things the roadmap's phrasing hides, Open-vocabulary detection: YOLOE-26 as a third candidate, Sources, The candidates, The landscape, and why it moved, The shortcut we should try before training anything (+2 more)

### Community 43 - "Labeling guide: shelf product faces"
Cohesion: 0.20
Nodes (10): Before you submit, Class names, Edge cases, Examples, Face or the unit behind it?, Labeling guide: shelf product faces, Pilot: cans and glass bottles (test set, from 2026-09-27), Pre-drawn boxes and their numbers (+2 more)

### Community 44 - "Serving strategy: from a synchronous demo API to a queue-backed counting pipeline"
Cohesion: 0.20
Nodes (9): 1. What the measurements say, 2. Reframing the requirement, 3. Target shape, 4. Phased path, 5. Making each count cheaper, ranked by return on atpg, 6. Gradio and hosted platforms, 7. Open decisions, Serving strategy: from a synchronous demo API to a queue-backed counting pipeline (+1 more)

### Community 45 - "classes_for"
Cohesion: 0.24
Nodes (10): classes_for(), drink_kind(), guess_brand(), guess_category(), guess_sku(), pack_types_for(), Returns (canonical_brand, raw_text_as_it_appears) or None., Pack type stated by the text, or None for a drink that states no container. (+2 more)

### Community 46 - "extract_invoice_packshots.py"
Cohesion: 0.31
Nodes (9): strip_wholesale_packaging(), _drawing_path(), guess_ext(), main(), Extract the per-product images embedded in the proforma invoice's "Image"…, 1-indexed spreadsheet row -> raw image bytes, for the first anchored picture on…, row_to_image(), xml_etree (+1 more)

### Community 47 - "load"
Cohesion: 0.33
Nodes (6): _choices(), load(), parse_task(), Path, Every photo with a submitted annotation, in export order., One task -> Photo, or None when nothing was submitted.

### Community 48 - "[x] Task 2: Extract crop naming from predict.py (refactor, no behaviour change) — DONE 2026-10-10 (commit 25666bc)"
Cohesion: 0.67
Nodes (3): [x] Task 2: Extract crop naming from predict.py (refactor, no behaviour change) — DONE 2026-10-10 (commit 25666bc), A crop below threshold gets COMPETITOR_<pack> from the T4 classifier., test_name_crops_unmatched_get_competitor_pack()

### Community 49 - "Dataset Preparation"
Cohesion: 0.22
Nodes (8): 1. Data Collection, 2. Organization & Initial Preprocessing, 3. Annotation, 4. Annotation Validation & Dataset Quality Checks, 5. Dataset Splitting, 6. Dataset Versioning, Dataset Preparation, Recommended Tooling

### Community 50 - "Issue: count faces, not every object"
Cohesion: 0.22
Nodes (9): 1. The problem, 2. What a face is, 3. Where the plan goes wrong today, 4. What "done" means, 5. Open decisions (need the BI analyst), 6. Approach options, 7. Plan, 8. Where this is written down (+1 more)

### Community 51 - "Test-set label review, 2026-09-28"
Cohesion: 0.22
Nodes (8): 1. Name the unnamed cans and glass bottles, 2. Small fixes, 3. Then, Already good, Numbers from this export (for reference, not final), Test-set label review, 2026-09-28, To do, in order, Verdict: labels not final yet

### Community 52 - "verify_atpg_claims.py"
Cohesion: 0.28
Nodes (8): pymongo, pymongo_errors, main(), mongo_uri(), Re-check the numbers in docs/PHASE0_REMAINING.md against the live database.…, Read MONGO_URI out of .env. The value is used, never printed., One aligned result line: what it is, what it is now, what I reported., row()

### Community 53 - "deploy_label_studio.sh"
Cohesion: 0.39
Nodes (7): die(), images_of(), on_server(), say(), deploy_label_studio.sh script, step(), warn()

### Community 54 - "score_crops"
Cohesion: 0.27
Nodes (10): _load_model(), pack_types(), Image, Can vs. glass for crops the matcher doesn't put a pack type on: a rival's crop…, Glass-minus-can cosine score per crop; > threshold means glass., "canned" or "glass" per crop, from the promoted zero-shot classifier., score_crops(), feats() (+2 more)

### Community 55 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture notes, Commands, Data pipeline, Label Studio is a separate app, Project state, Taxonomy: labels, categories, scope

### Community 56 - "evaluate"
Cohesion: 0.22
Nodes (10): Counter, CategoryResult, _denominator(), evaluate(), pooled(), Path, _ratio(), Taxonomy (+2 more)

### Community 58 - "Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14"
Cohesion: 0.25
Nodes (7): Candidates, How much the 93.8% actually tells us, Measured: box shape alone (zero ML), Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14, Proposed order, Sources, What the stage has to do, and what it costs today

### Community 59 - "Tasks"
Cohesion: 0.18
Nodes (10): Follow-up proposal (not started, awaiting decisions), Not in T6, Open questions — resolved 2026-10-10 by the user, T6 FastAPI service Implementation Plan, Tasks, [x] Task 1: Dependencies — DONE 2026-10-10 (commit b9b9fa7), [x] Task 5b: API key auth (placeholder) — DONE 2026-10-10 (commit a0ae449), [x] Task 6: Real smoke run (hemin, only when the user says it is up) — DONE 2026-10-10 (+2 more)

### Community 62 - "make_gallery_folders.py"
Cohesion: 0.43
Nodes (6): count_images(), gallery_labels(), main(), Path, Create the reference-gallery folder per tracked competitor, from config only.…, (label, brand, pack_type, category) per tracked competitor pack type.

### Community 63 - "Phase 0 — what is left"
Cohesion: 0.33
Nodes (5): 1. Fix the test set, 2. Data quality, 3. Blocked on the business, 4. Then Phase 1, Phase 0 — what is left

### Community 64 - "Demo path: upload a photo, get ours vs tracked rivals (2026-10-04)"
Cohesion: 0.33
Nodes (5): Current handoff (2026-10-11, end of day). Replace this section; do not append., Demo path: upload a photo, get ours vs tracked rivals (2026-10-04), Not blocking the demo, Risk of T0, Where we are

### Community 65 - "Requests to send (Phase 0, day 1)"
Cohesion: 0.40
Nodes (4): 1. Class list (to sales / business analysts), 2. Packshots (to marketing), 3. Original uploads before recompression (to the field app developer), Requests to send (Phase 0, day 1)

### Community 66 - "sys"
Cohesion: 0.25
Nodes (5): Require gitmoji + Conventional Commit subjects, and cap length (stdlib only).…, re, Scan directory for images and report their properties., scan_images(), sys

### Community 67 - "export_onnx.py"
Cohesion: 0.50
Nodes (4): export(), main(), Path, Export an ultralytics `.pt` detector to ONNX for serving. Ultralytics (AGPL)…

### Community 68 - "Pilot: two brands, cans and glass bottles"
Cohesion: 0.50
Nodes (4): Current checkpoint (2026-10-11, end of day), Deferred, not dropped, Pilot: two brands, cans and glass bottles, Scope (decided 2026-09-27, metric narrowed 2026-09-29)

### Community 69 - "render"
Cohesion: 0.50
Nodes (4): main(), Image, Path, render()

### Community 73 - "UnknownContainer"
Cohesion: 0.67
Nodes (3): A drink row states no container and its brand has none on record., UnknownContainer, ValueError

## Knowledge Gaps
- **253 isolated node(s):** `face-counter`, `pull_photos.sh script`, `sync_from_hemin.sh script`, `sync_to_hemin.sh script`, `Decision recorded 2026-09-29 (changes the pilot's metric)` (+248 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 594 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `To do, in order` connect `gallery.py` to `make_splits.py`, `Pilot: two brands, cans and glass bottles`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `Pilot: two brands, cans and glass bottles` connect `Pilot: two brands, cans and glass bottles` to `ISSUE_FACES_NOT_OBJECTS.md`, `gallery.py`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `Serving pipeline` connect `predict_photos` to `Home.md`, `app.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `Detections` (e.g. with `test_count_endpoint_classifier_off()` and `test_count_endpoint_debug_true_includes_debug_field()`) actually correct?**
  _`Detections` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `face-counter`, `pull_photos.sh script`, `sync_from_hemin.sh script` to the rest of the system?**
  _253 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_identification.py` be split into smaller, more focused modules?**
  _Cohesion score 0.055218855218855216 - nodes in this community are weakly interconnected._
- **Should `Detections` be split into smaller, more focused modules?**
  _Cohesion score 0.0745637228979376 - nodes in this community are weakly interconnected._