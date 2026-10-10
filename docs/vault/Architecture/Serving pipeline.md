---
type: architecture
---

# Serving pipeline

The demo API in `src/face_counter/serving/`, as it is in code on 2026-10-10.
Numbers are in [[2026-10-10 Serving investigation]]; decisions in
[[ADR-0001 Serve the detector through ONNX Runtime only]] and
[[ADR-0002 Pack-type stage off by default]].

## Request path

```
POST /count (multipart file, X-API-Key)
  app.py      decode + EXIF transpose, 20 MB cap, one-at-a-time lock
  pipeline.py detect ─┬─ classify off (default): boxes only, categories {}
                      ├─ classify on: crop → CLIP canned/glass → per-category counts
                      └─ debug=true: crop → DINOv2 matcher + share (experimental)
  schemas.py  CountResponse, caveats chosen by what actually ran
```

- **Detector:** `onnx_detector.build` (`src/face_counter/serving/onnx_detector.py:106`).
  It letterboxes to 1280, runs ONNX Runtime on CPU, then decodes the raw
  grid (`:120`), filters by confidence, converts cxcywh to xyxy, and runs
  greedy NMS (`:54`). Session options (`:76`) turn the CPU memory arena off
  and read a thread cap from `FACE_COUNTER_ORT_THREADS`.
- **Pipeline:** `ServeConfig` (`src/face_counter/serving/pipeline.py:66`) is
  built from env vars. `classify` defaults to False (`:77`, parsed at `:95`).
  `Pipeline.run` (`:166`) only crops when a stage needs crops (`:173`). The
  debug dependencies (gallery, DINOv2 embeddings, taxonomy) load lazily on
  the first debug request (`_ensure_debug_deps`, `:149`).
- **App:** `create_app` (`src/face_counter/serving/app.py:106`). Auth is
  `require_api_key` (`:74`), a static header compared with
  `hmac.compare_digest`, on `/count` and `/overlay` only. `/health` stays
  open. `_pack_classifier_name` (`:62`) reports `null` when the classifier is
  off, so `/health` and responses never claim a model that did not run.
  Inference runs in a worker thread under a lock (`_run_locked`, `:84`).

## Guarantees and how they are enforced

- **No torch, transformers or ultralytics in the served process when the
  classifier is off.** `tests/test_serving.py:240` runs a request in a fresh
  interpreter and asserts none of the three is in `sys.modules`. Heavy
  imports elsewhere are deferred into functions.
- **Caveats always match what ran.** With the classifier off, the response
  carries `CLASSIFIER_OFF_CAVEAT` and no 93.8% claim (`schemas.py`).

## Known defects

- The debug path loads CLIP even with `classify=False`, because
  `predict.name_crops` calls `pt.pack_types` for unmatched crops
  (`src/face_counter/identification/predict.py:83`).
- `pack_type.score_crops` reloads CLIP from disk on every call
  (`src/face_counter/identification/pack_type.py:37`, `:45`). Issue #3.
- Requests are serialised by one lock. That is fine for a demo, wrong for
  concurrent users; the production shape is in
  [[ADR-0003 Async intake and pull workers (proposed)]].
- Results are not stored and carry no store or time metadata. Issue #7.
