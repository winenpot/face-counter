# Graph Report - face-counter  (2026-10-26)

## Corpus Check
- 107 files · ~108,021 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 5, .example 2, .csv 1)

## Summary
- 1365 nodes · 2458 edges · 87 communities (75 shown, 12 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 164 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `05cfd690`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- export_photos.py
- Detections
- test_bakeoff.py
- test_phase0.py
- setup_project.py
- face-counter — Vault Home
- test_evaluation.py
- detector_bakeoff.py
- test_onnx_detector.py
- pipeline.py
- Serving strategy: from a synchronous demo API to a queue-backed counting pipeline
- db
- test_predict.py
- test_setup_project.py
- json
- make_splits.py
- make_splits.py
- My track
- build
- export_photos.py
- LOGS
- test_build_classes.py
- export
- prepare_label_studio.py
- test_onnx_detector.py
- score_model
- pipeline.py
- cmd_tune
- build_classes.py
- 1. Error analysis
- identification/cli.py
- match.py
- Photo
- pathlib
- face_counter_identification
- argparse
- Labeling the test set for the pilot: step by step
- Shelf Detector Roadmap
- predict_photos
- face-counter (Shelf Detector)
- main
- راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه
- Detector alternatives — the knobs we deliberately left reachable
- categories
- Home.md
- classes_for
- extract_invoice_packshots.py
- load
- [x] Task 2: Extract crop naming from predict.py (refactor, no behaviour change) — DONE 2026-10-10 (commit 25666bc)
- numpy
- build_classes.py
- Test-set label review, 2026-09-28
- verify_atpg_claims.py
- deploy_label_studio.sh
- score_crops
- Tasks
- evaluate
- ISSUE_FACES_NOT_OBJECTS.md
- Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14
- face_counter_serving
- face_counter_serving_pipeline
- make_gallery_folders.py
- score_crops
- Demo API on the apps server
- Requests to send (Phase 0, day 1)
- sys
- export_onnx.py
- scope.yaml
- Frozen: pilot test-set labels, v1 (2026-09-30)
- investigations/
- UnknownContainer
- face_counter/__init__.py
- yolo26l-sku110k
- 2026-10-26 Training batch labeling status
- onnx_detector.py
- ADR-0001 Serve the detector through ONNX Runtime only
- ADR-0002 Pack-type stage off by default
- face_counter_evaluation
- ADR-0003 Async intake and pull workers (proposed)
- Environments and dependency groups
- Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14
- build
- 2026-10-26 Best-practice audit (web research vs this repo)
- 2026-10-10 Serving investigation

## God Nodes (most connected - your core abstractions)
1. `Detections` - 49 edges
2. `_make_pipeline()` - 23 edges
3. `fake_detector()` - 20 edges
4. `Proposal: AI-Based Product Face Counting Web Service` - 19 edges
5. `Box` - 16 edges
6. `main()` - 16 edges
7. `create_app()` - 16 edges
8. `Photo` - 15 edges
9. `evaluate()` - 15 edges
10. `GalleryImage` - 14 edges

## Surprising Connections (you probably didn't know these)
- `What the stage has to do, and what it costs today` --references--> `score_crops()`  [INFERRED]
  docs/PACK_TYPE_ALTERNATIVES.md → src/face_counter/identification/pack_type.py
- `[x] Task 6b: Pack-type classifier off for the demo — DONE 2026-10-10` --references--> `name_crops()`  [INFERRED]
  .hermes/plans/2026-10-10_111130-t6-fastapi-service.md → src/face_counter/identification/predict.py
- `1. Fix the test set` --references--> `diverse_sample()`  [INFERRED]
  docs/PHASE0_REMAINING.md → src/face_counter/label_studio/make_splits.py
- `[ ] Y4. Gold-val selection (pilot step 3b; independent)` --references--> `diverse_sample()`  [INFERRED]
  .hermes/plans/2026-09-29_pilot-parallel-tracks.md → src/face_counter/label_studio/make_splits.py
- `Task 2: `demo_page.py` + the route` --references--> `create_app()`  [INFERRED]
  .hermes/plans/2026-10-11_101419-t8a-demo-upload-page.md → src/face_counter/serving/app.py

## Import Cycles
- None detected.

## Communities (87 total, 12 thin omitted)

### Community 0 - "export_photos.py"
Cohesion: 0.16
Nodes (11): export(), _ext_for(), iter_photo_records(), load_existing(), load_join_map(), main(), _parse_date(), validate_config() (+3 more)

### Community 1 - "Detections"
Cohesion: 0.06
Nodes (35): To do, in order, [x] Y1. Named targeted competitors in the taxonomy (after U1), Current handoff (2026-10-26, end of day). Replace this section; do not append., Demo path: upload a photo, get ours vs tracked rivals (2026-10-04), Not blocking the demo, Risk of T0, Tasks, in order, Where we are (+27 more)

### Community 2 - "test_bakeoff.py"
Cohesion: 0.05
Nodes (29): _ann(), _box(), cfg(), _choice(), _FakeBatchEncoding, _FakeClipModel, _FakeClipProcessor, _FakeImageProcessor (+21 more)

### Community 3 - "test_phase0.py"
Cohesion: 0.09
Nodes (9): _sideways_jpeg(), test_load_image_applies_exif_orientation(), test_main_records_the_prompts_it_used(), test_missing_weights_fail_fast_with_download_instructions(), test_run_writes_counts_jsonl_overlays_and_tasks(), test_weights_path_is_resolved_against_the_project_root(), test_yolo26_builder_loads_the_configured_weights(), test_yoloe_builder_passes_the_prompts_to_the_model() (+1 more)

### Community 4 - "setup_project.py"
Cohesion: 0.09
Nodes (25): Done, build_fake_db(), _cfg(), fake_db(), _gold_setup(), _jpeg(), _sha(), test_date_filter() (+17 more)

### Community 5 - "face-counter — Vault Home"
Cohesion: 0.17
Nodes (12): apps server, db server, face-counter — Vault Home, FastAPI inference service (Phase 2), Infrastructure, Label Studio deployment, Map, Status (2026-09-28, superseded) (+4 more)

### Community 6 - "test_evaluation.py"
Cohesion: 0.08
Nodes (17): copy_photos(), ensure_project(), ensure_storage(), existing_photo_ids(), _free_port(), import_tasks(), is_personal_access_token(), LabelStudio (+9 more)

### Community 7 - "detector_bakeoff.py"
Cohesion: 0.07
Nodes (58): _ann(), _box(), _choice(), _dets(), _labeled(), _photo(), _task(), _taxonomy() (+50 more)

### Community 8 - "test_onnx_detector.py"
Cohesion: 0.14
Nodes (6): _FakeInput, _FakeSession, _row(), test_build_filters_by_confidence_and_unletterboxes(), test_build_never_imports_ultralytics(), test_build_returns_nothing_below_zero_rows()

### Community 9 - "pipeline.py"
Cohesion: 0.10
Nodes (20): [x] Task 1b: Detector as ONNX, not ultralytics, inside the service — DONE 2026-10-10 (commit efe921b), build_detr_r50_sku110k(), detect(), build_sku110k_yolo11s(), build_yolo26l_sku110k(), build_yoloe_26s(), clean_legacy_config(), _detr_config() (+12 more)

### Community 10 - "Serving strategy: from a synchronous demo API to a queue-backed counting pipeline"
Cohesion: 0.22
Nodes (8): 1. What the measurements say, 2. Reframing the requirement, 3. Target shape, 4. Phased path, 6. Gradio and hosted platforms, 7. Open decisions, Serving strategy: from a synchronous demo API to a queue-backed counting pipeline, Sources

### Community 11 - "db"
Cohesion: 0.07
Nodes (29): command, condition, cpus, environment, healthcheck, image, mem_limit, restart (+21 more)

### Community 12 - "test_predict.py"
Cohesion: 0.07
Nodes (27): 10. Deployment, 11. Performance Considerations, 12. Security, 13. Monitoring and Logging, 14. Evaluation Metrics, 15. Development Phases, 16. Risks and Limitations, 17. Expected Result (+19 more)

### Community 13 - "test_setup_project.py"
Cohesion: 0.12
Nodes (13): FakeLS, _task(), test_a_frozen_project_is_never_written_to(), test_a_task_file_listing_a_photo_twice_is_rejected(), test_creates_the_project_with_prelabeling_on_when_missing(), test_existing_project_with_a_different_config_is_updated_not_duplicated(), test_existing_project_with_the_same_config_is_left_alone(), test_import_skips_photos_already_in_the_project() (+5 more)

### Community 14 - "json"
Cohesion: 0.07
Nodes (31): analyse(), boxes(), diff(), fmt(), get(), iou(), pull(), report() (+23 more)

### Community 15 - "make_splits.py"
Cohesion: 0.21
Nodes (11): _already_sent(), diverse_sample(), group_key(), main(), make_gold_val(), make_splits(), split_for(), _split_frame() (+3 more)

### Community 16 - "make_splits.py"
Cohesion: 0.09
Nodes (22): Decision recorded 2026-09-29 (changes the pilot's metric), My track, Open questions, Risks, Two tracks, [ ] U5. Review the gold-val contact sheet (after Y4), [ ] U6. Gallery images for targeted competitors (after Y1, any time), [ ] U7. Label the gold-val set (after U5 and Y4's project exists) (+14 more)

### Community 17 - "My track"
Cohesion: 0.13
Nodes (33): Task 1: Failing tests for `GET /`, Detections, _make_pipeline(), test_count_endpoint_missing_api_key_rejected(), fake_detector(), test_count_endpoint_rejects_undecodable_bytes(), fake_detector(), test_count_endpoint_wrong_api_key_rejected() (+25 more)

### Community 19 - "export_photos.py"
Cohesion: 0.11
Nodes (16): _boom(), _png_bytes(), test_classifier_off_serving_never_imports_torch(), test_count_endpoint_classifier_off(), fake_detector(), test_count_endpoint_debug_true_includes_debug_field(), fake_detector(), test_count_endpoint_omits_debug_by_default() (+8 more)

### Community 20 - "LOGS"
Cohesion: 0.16
Nodes (8): Request path, create_app(), health(), _git_sha(), main(), _pack_classifier_name(), require_api_key(), require_demo_password()

### Community 21 - "test_build_classes.py"
Cohesion: 0.13
Nodes (10): _make_photo(), _make_share_report(), test_cli_predict_smoke(), test_predict_matched_box_uses_gallery_label(), test_predict_missing_detection_gives_empty_boxes(), test_predict_missing_image_gives_empty_boxes(), test_predict_unmatched_box_uses_pack_type(), test_summary_predict_comparison_caveat_present() (+2 more)

### Community 22 - "export"
Cohesion: 0.08
Nodes (25): export, batch_size, date_from, date_to, out_dir, throttle_seconds, store_id, taken_at (+17 more)

### Community 23 - "prepare_label_studio.py"
Cohesion: 0.24
Nodes (4): embed_images(), embed_paths(), load_image(), _load_model()

### Community 24 - "test_onnx_detector.py"
Cohesion: 0.13
Nodes (15): count_images(), gallery_labels(), main(), cfg(), _labels(), test_adding_a_tracked_competitor_is_a_config_edit(), test_check_mode_creates_nothing(), test_count_images_ignores_readme_and_counts_photos() (+7 more)

### Community 25 - "score_model"
Cohesion: 0.22
Nodes (9): count(), BoxResponse, CountResponse, DebugBoxResponse, DebugCategoryShare, DebugResponse, from_result(), ModelInfo (+1 more)

### Community 26 - "pipeline.py"
Cohesion: 0.16
Nodes (6): [x] Task 4: Response schema (serving/schemas.py) — DONE 2026-10-10 (commit 9d5dc0e), crop_box(), BoxResult, DebugBoxResult, DebugResult, Result

### Community 27 - "cmd_tune"
Cohesion: 0.25
Nodes (5): _choices(), load(), parse_task(), Photo, test_predict_gt_metadata_preserved()

### Community 28 - "build_classes.py"
Cohesion: 0.18
Nodes (11): Context the implementer needs, Not in T6, Open questions — resolved 2026-10-10 by the user, T6 FastAPI service Implementation Plan, CategoryResult, _denominator(), evaluate(), pooled() (+3 more)

### Community 29 - "1. Error analysis"
Cohesion: 0.14
Nodes (14): 1. The job is not "label 9,500 photos", 2. Separate *where* from *what*, 3. Cluster labeling — how identity scales, 4. Competitors: category, not SKU, 5. Tools: which free options fit, and which do not, 6. Guardrails, 7. Starting sequence, 8. Weekly rounds, and what survives a wider taxonomy (+6 more)

### Community 30 - "identification/cli.py"
Cohesion: 0.21
Nodes (6): run(), cmd_gallery(), cmd_tune(), collect_crops(), main(), _open()

### Community 31 - "match.py"
Cohesion: 0.15
Nodes (13): 1. Error analysis, 2. Hyperparameter tuning, 3. Human-in-the-loop — and why it is *not* RLHF, Back-row is the headline error here, Error analysis, tuning, and the human-in-the-loop, Honesty rules, Practices that matter more than the algorithm, RLHF is a different tool for a different problem (+5 more)

### Community 32 - "Photo"
Cohesion: 0.15
Nodes (12): 1. What was done, 2. Measured results (no ground truth yet), 3. Visual review of the overlays, 4. Interpretation, 5. Limitations, 6. Next steps, 7. Evaluation metrics, Business output (+4 more)

### Community 33 - "pathlib"
Cohesion: 0.15
Nodes (9): auc(), collect_crops(), main(), _open(), score_model(), feats(), image_emb(), text_emb() (+1 more)

### Community 34 - "face_counter_identification"
Cohesion: 0.15
Nodes (12): Code entry points, Current state of every task, Decision needed at the start of tomorrow, hemin notes, Key numbers to remember, Repo layout (what's where), Session Summary — 2026-10-05, T3 — Embedding matcher (commit b114061) (+4 more)

### Community 35 - "argparse"
Cohesion: 0.20
Nodes (4): main(), render(), export(), main()

### Community 36 - "Labeling the test set for the pilot: step by step"
Cohesion: 0.17
Nodes (11): Deploying changes, First run, Label Studio deployment, Labeling in batches on the server, Later: serving from GridFS instead of copies, Loading photos, Migrating an existing instance, Network exposure (+3 more)

### Community 37 - "Shelf Detector Roadmap"
Cohesion: 0.17
Nodes (11): 0. Build the files (on this machine), 1-4. Put it on the server: one command, 1. Upload the photos to the server, 2. Create the project (in the browser, once), 3. Project settings, 4. Import the tasks, 5. Label, 6. The three labeling-guide screenshots (done 2026-09-27) (+3 more)

### Community 38 - "predict_photos"
Cohesion: 0.17
Nodes (12): Approach, Architecture, Phase 0 — Foundations (days 1–3), Phase 1 — Working pipeline (days 4–10), Phase 2 — MVP demo (days 11–15), Phase 3 — Error analysis and the data flywheel (month 2), Phase 4 — Production (month 3+), Resources and dependencies (+4 more)

### Community 39 - "face-counter (Shelf Detector)"
Cohesion: 0.17
Nodes (11): Commit messages, Data, Disk, face-counter (Shelf Detector), Finding your field paths, Labeling (Label Studio), Layout, Phase 0 workflow (+3 more)

### Community 40 - "main"
Cohesion: 0.24
Nodes (7): _fmt(), main(), _pct(), summary(), summary_predict_comparison(), _write_csv(), predict_photos()

### Community 41 - "راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه"
Cohesion: 0.33
Nodes (6): Box, ap50_95(), average_precision(), greedy(), iou(), MatchResult

### Community 42 - "Detector alternatives — the knobs we deliberately left reachable"
Cohesion: 0.18
Nodes (11): دکمه‌ها و تنظیمات Label Studio (انگلیسی می‌مانند), راهنمای برچسب‌گذاری: چهره‌ی محصولات روی قفسه, سه بخش پایین عکس, موارد خاص, نمونه‌ها, پایلوت: قوطی‌ها و بطری‌های شیشه‌ای, پیش از ثبت (Submit), چه چیزی را کادر بکشیم (+3 more)

### Community 43 - "categories"
Cohesion: 0.20
Nodes (9): pack_types, categories, canned_drinks, dressings, glass_drinks, oils, pack_types, pack_types (+1 more)

### Community 45 - "classes_for"
Cohesion: 0.20
Nodes (10): Constraints, Detector alternatives — the knobs we deliberately left reachable, First, three things the roadmap's phrasing hides, Open-vocabulary detection: YOLOE-26 as a third candidate, Sources, The candidates, The landscape, and why it moved, The shortcut we should try before training anything (+2 more)

### Community 46 - "extract_invoice_packshots.py"
Cohesion: 0.20
Nodes (10): Before you submit, Class names, Edge cases, Examples, Face or the unit behind it?, Labeling guide: shelf product faces, Pilot: cans and glass bottles (test set, from 2026-09-27), Pre-drawn boxes and their numbers (+2 more)

### Community 47 - "load"
Cohesion: 0.33
Nodes (4): [x] Task 3: Pipeline object (serving/pipeline.py) — DONE 2026-10-10 (commit efd27ff), REVISED SCOPE, _lifespan(), Pipeline, ServeConfig

### Community 48 - "[x] Task 2: Extract crop naming from predict.py (refactor, no behaviour change) — DONE 2026-10-10 (commit 25666bc)"
Cohesion: 0.38
Nodes (4): overlay(), _decode_image(), _draw_overlay(), _run_locked()

### Community 49 - "numpy"
Cohesion: 0.24
Nodes (5): best_threshold(), Match, nearest(), nearest_batch(), name_crops()

### Community 50 - "build_classes.py"
Cohesion: 0.06
Nodes (26): build_classes(), classes_for(), drink_kind(), guess_brand(), guess_category(), guess_sku(), load_descriptions(), main() (+18 more)

### Community 51 - "Test-set label review, 2026-09-28"
Cohesion: 0.17
Nodes (6): bootstrap_ci(), evaluate(), _per_photo(), _precision(), _recall(), test_bootstrap_is_deterministic_and_brackets_the_estimate()

### Community 52 - "verify_atpg_claims.py"
Cohesion: 0.22
Nodes (8): 1. Data Collection, 2. Organization & Initial Preprocessing, 3. Annotation, 4. Annotation Validation & Dataset Quality Checks, 5. Dataset Splitting, 6. Dataset Versioning, Dataset Preparation, Recommended Tooling

### Community 53 - "deploy_label_studio.sh"
Cohesion: 0.22
Nodes (9): 1. The problem, 2. What a face is, 3. Where the plan goes wrong today, 4. What "done" means, 5. Open decisions (need the BI analyst), 6. Approach options, 7. Plan, 8. Where this is written down (+1 more)

### Community 54 - "score_crops"
Cohesion: 0.22
Nodes (8): 1. Name the unnamed cans and glass bottles, 2. Small fixes, 3. Then, Already good, Numbers from this export (for reference, not final), Test-set label review, 2026-09-28, To do, in order, Verdict: labels not final yet

### Community 55 - "Tasks"
Cohesion: 0.20
Nodes (9): Decisions and risk (brief, per the user's convention), Open questions, T8a: Demo upload page at "/" (overlay only) Implementation Plan, Task 2: `demo_page.py` + the route, Task 3: Try it locally in a browser, Task 4: Docs, Task 5: Redeploy on the apps server (ask before running), Task 6: Checkpoint (+1 more)

### Community 56 - "evaluate"
Cohesion: 0.28
Nodes (3): main(), mongo_uri(), row()

### Community 57 - "ISSUE_FACES_NOT_OBJECTS.md"
Cohesion: 0.39
Nodes (7): die(), images_of(), on_server(), say(), deploy_label_studio.sh script, step(), warn()

### Community 58 - "Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14"
Cohesion: 0.25
Nodes (6): Architecture notes, Commands, Data pipeline, Label Studio is a separate app, Project state, Taxonomy: labels, categories, scope

### Community 60 - "face_counter_serving"
Cohesion: 0.13
Nodes (12): Follow-up proposal (not started, awaiting decisions), Tasks, [x] Task 1: Dependencies — DONE 2026-10-10 (commit b9b9fa7), [x] Task 2: Extract crop naming from predict.py (refactor, no behaviour change) — DONE 2026-10-10 (commit 25666bc), [x] Task 5: App and endpoints (serving/app.py) — DONE 2026-10-10 (commit 7b2a923), [x] Task 5b: API key auth (placeholder) — DONE 2026-10-10 (commit a0ae449), [x] Task 6: Real smoke run (hemin, only when the user says it is up) — DONE 2026-10-10, [x] Task 6b: Pack-type classifier off for the demo — DONE 2026-10-10 (+4 more)

### Community 61 - "face_counter_serving_pipeline"
Cohesion: 0.33
Nodes (5): 1. Fix the test set, 2. Data quality, 3. Blocked on the business, 4. Then Phase 1, Phase 0 — what is left

### Community 62 - "make_gallery_folders.py"
Cohesion: 0.40
Nodes (4): 1. Class list (to sales / business analysts), 2. Packshots (to marketing), 3. Original uploads before recompression (to the field app developer), Requests to send (Phase 0, day 1)

### Community 63 - "score_crops"
Cohesion: 0.24
Nodes (9): 5. Making each count cheaper, ranked by return on atpg, Guarantees and how they are enforced, Known defects, Serving pipeline, _load_model(), score_crops(), feats(), image_emb() (+1 more)

### Community 64 - "Demo API on the apps server"
Cohesion: 0.25
Nodes (8): Before anyone else uses it, Binding rule, Demo API on the apps server, How to look at it, Rebuild after a code change, Remove, Server `.env`, What is running

### Community 65 - "Requests to send (Phase 0, day 1)"
Cohesion: 0.50
Nodes (4): Current checkpoint (2026-10-26, end of day), Deferred, not dropped, Pilot: two brands, cans and glass bottles, Scope (decided 2026-09-27, metric narrowed 2026-09-29)

### Community 68 - "scope.yaml"
Cohesion: 0.29
Nodes (6): brands, categories, competitors, detail, retired, share_against

### Community 75 - "yolo26l-sku110k"
Cohesion: 0.33
Nodes (5): yolo26l-sku110k, onnx, weights, yoloe, prompts

### Community 76 - "2026-10-26 Training batch labeling status"
Cohesion: 0.29
Nodes (6): 2026-10-26 Training batch labeling status, Per-labeler report (16:55 same day), Progress, Quality findings, Reproduce, What it means for training

### Community 77 - "onnx_detector.py"
Cohesion: 0.27
Nodes (4): detect(), _letterbox(), _nms(), _xywh_to_xyxy()

### Community 78 - "ADR-0001 Serve the detector through ONNX Runtime only"
Cohesion: 0.50
Nodes (4): ADR-0001 Serve the detector through ONNX Runtime only, Consequences, Context, Decision

### Community 79 - "ADR-0002 Pack-type stage off by default"
Cohesion: 0.50
Nodes (4): ADR-0002 Pack-type stage off by default, Consequences, Context, Decision

### Community 81 - "ADR-0003 Async intake and pull workers (proposed)"
Cohesion: 0.50
Nodes (4): ADR-0003 Async intake and pull workers (proposed), Context, Open before accepting, Proposal

### Community 82 - "Environments and dependency groups"
Cohesion: 0.67
Nodes (3): Environments and dependency groups, Known gaps, Rules

### Community 83 - "Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14"
Cohesion: 0.25
Nodes (7): Candidates, How much the 93.8% actually tells us, Measured: box shape alone (zero ML), Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14, Proposed order, Sources, What the stage has to do, and what it costs today

### Community 84 - "build"
Cohesion: 0.29
Nodes (4): Latency and memory, build(), _load_session(), _session_options()

### Community 85 - "2026-10-26 Best-practice audit (web research vs this repo)"
Cohesion: 0.33
Nodes (5): 2026-10-26 Best-practice audit (web research vs this repo), Aligned (or beyond common practice), Critical findings, Gaps, Recommendations, by value for effort

### Community 86 - "2026-10-10 Serving investigation"
Cohesion: 0.40
Nodes (5): 2026-10-10 Serving investigation, Accuracy, Corrections to statements made during the session, Machines, Things that turned out different from what was assumed

## Knowledge Gaps
- **1 isolated node(s):** `face-counter`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 645 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `To do, in order` connect `Detections` to `Requests to send (Phase 0, day 1)`, `build_classes.py`, `make_splits.py`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Detections` (e.g. with `test_count_endpoint_classifier_off()` and `test_count_endpoint_debug_true_includes_debug_field()`) actually correct?**
  _`Detections` has 21 INFERRED edges - model-reasoned connections that need verification._
- **What connects `face-counter` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Detections` be split into smaller, more focused modules?**
  _Cohesion score 0.05605499735589635 - nodes in this community are weakly interconnected._
- **Why does `Pilot: two brands, cans and glass bottles` connect `Requests to send (Phase 0, day 1)` to `Detections`, `Tasks`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Should `test_bakeoff.py` be split into smaller, more focused modules?**
  _Cohesion score 0.053246753246753244 - nodes in this community are weakly interconnected._
- **Why does `Serving pipeline` connect `score_crops` to `Home.md`, `LOGS`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._