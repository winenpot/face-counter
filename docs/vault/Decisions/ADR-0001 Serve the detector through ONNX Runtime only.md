---
type: adr
status: accepted
date: 2026-10-10
---

# ADR-0001 Serve the detector through ONNX Runtime only

## Context

The detector is an ultralytics YOLO26 model. Importing ultralytics in the API
would bring torch (GBs, CUDA wheels on Linux) into a CPU-only service and put
AGPL code inside the served process. The model is to be fine-tuned on the
project's own data, which makes it the project's property.

## Decision

Export the `.pt` to ONNX offline (`scripts/export_onnx.py`, `analytics`
group, on hemin) and serve it with `onnxruntime` on CPU
(`src/face_counter/serving/onnx_detector.py`). The served process never
imports ultralytics or torch.

## Consequences

- The `serve` environment stays small and CPU-only. The demo image is
  961 MB, mostly pandas, numpy and onnxruntime.
- Post-processing is our code. The export's raw `(1, 4+nc, A)` output needs
  confidence filtering, cxcywh to xyxy and NMS; that was missed at first and
  then fixed against the real export. Scores track the `.pt` model on normal
  photos.
- Every new detector version needs an export step and a sha256-checked copy
  to each host until there is an artifact store (issue #5).

See [[Serving pipeline]], [[Environments and dependency groups]].
