"""ONNX Runtime detector for serving: `ultralytics` is never imported here.

Ultralytics (AGPL) stays a training/export-time tool only (`scripts/export_onnx.py`,
run offline against a `.pt` file); the served process runs the exported graph
through onnxruntime and nothing else, so the AGPL code never ships inside the
API process (T6 plan, decision 2026-10-10).

**Verified on the real export, 2026-10-10 (hemin, `models/yolo26l-sku110k.onnx`,
imgsz 1280):** the graph has ONE output, `output0`, shaped ``(1, 4 + nc, A)``
-- here ``(1, 5, 33600)`` for the single-class ("object") SKU-110K detector.
This is the raw per-anchor grid (box in ``cx, cy, w, h`` + one score per
class, in letterboxed input-image pixel coordinates), not NMS'd. The
original plan (Task 1b) assumed a pre-filtered, pre-NMS'd ``(1, N, 6)``
output and was wrong -- this module does its own confidence filter,
cxcywh -> xyxy conversion, and greedy NMS before un-letterboxing.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image

from face_counter.training.detector_bakeoff import GEOMETRY_LABEL, Detections

DEFAULT_IOU = 0.45  # standard YOLO NMS threshold


def _letterbox(
    img: Image.Image, size: int, color: tuple[int, int, int] = (114, 114, 114)
) -> tuple[Image.Image, float, tuple[int, int]]:
    """Resize preserving aspect ratio onto a size x size canvas, ultralytics-style.

    Returns the padded image plus the scale factor and (left, top) padding,
    needed to map detected boxes back to the original image's pixels.
    """
    w, h = img.size
    scale = min(size / w, size / h)
    nw, nh = round(w * scale), round(h * scale)
    resized = img.resize((nw, nh), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), color)
    left, top = (size - nw) // 2, (size - nh) // 2
    canvas.paste(resized, (left, top))
    return canvas, scale, (left, top)


def _xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    cx, cy, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    return np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy NMS over one class's boxes. Returns kept indices, highest score first."""
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_rest = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / np.clip(area_i + area_rest - inter, 1e-9, None)
        order = rest[iou <= iou_threshold]
    return keep


def _session_options():
    """Options for a long-lived serving process on a shared CPU host.

    - CPU memory arena and memory-pattern planning off: with them on, the
      process grew from ~0.3 GB to 1.44 GB within two requests and never
      shrank; off, it idles at ~0.33 GB and peaks at ~0.8 GB per request,
      for ~3% more latency (hemin, imgsz 1280, 2026-10-10).
    - ``FACE_COUNTER_ORT_THREADS`` caps intra-op threads to the container's
      CPU allowance (onnxruntime otherwise sizes to the host's cores and
      over-subscribes a CPU quota). 0 / unset keeps onnxruntime's default.
    """
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.enable_cpu_mem_arena = False
    so.enable_mem_pattern = False
    so.intra_op_num_threads = int(os.environ.get("FACE_COUNTER_ORT_THREADS", "0") or 0)
    return so


def _load_session(onnx_path: Path):
    """Heavy import stays inside the function, like the rest of the codebase's
    model loaders, so this module imports instantly for tests (monkeypatched)."""
    import onnxruntime as ort

    return ort.InferenceSession(
        str(onnx_path), sess_options=_session_options(), providers=["CPUExecutionProvider"]
    )


def build(onnx_path: Path, imgsz: int, conf: float, iou_threshold: float = DEFAULT_IOU):
    """A `training.detector_bakeoff.Detector` backed by ONNX Runtime.

    Loads the session once; the returned closure runs one image per call,
    matching every other builder in `detector_bakeoff.py`.
    """
    session = _load_session(onnx_path)
    input_name = session.get_inputs()[0].name

    def detect(img: Image.Image) -> Detections:
        padded, scale, (left, top) = _letterbox(img, imgsz)
        arr = np.asarray(padded, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)[None, ...]  # HWC -> NCHW
        (out,) = session.run(None, {input_name: arr})
        preds = np.asarray(out)[0].T  # (A, 4 + nc)

        boxes_cxcywh = preds[:, :4]
        class_scores = preds[:, 4:]
        scores = class_scores.max(axis=1)
        mask = scores >= conf
        boxes_cxcywh = boxes_cxcywh[mask]
        scores = scores[mask]

        boxes: list[list[float]] = []
        out_scores: list[float] = []
        labels: list[str] = []
        if boxes_cxcywh.shape[0] > 0:
            xyxy = _xywh_to_xyxy(boxes_cxcywh)
            keep = _nms(xyxy, scores, iou_threshold)
            for i in keep:
                x1, y1, x2, y2 = xyxy[i]
                boxes.append(
                    [
                        (float(x1) - left) / scale,
                        (float(y1) - top) / scale,
                        (float(x2) - left) / scale,
                        (float(y2) - top) / scale,
                    ]
                )
                out_scores.append(float(scores[i]))
                labels.append(GEOMETRY_LABEL)
        return Detections(boxes=boxes, scores=out_scores, labels=labels)

    return detect
