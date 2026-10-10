"""ONNX Runtime detector for serving: `ultralytics` is never imported here.

Ultralytics (AGPL) stays a training/export-time tool only (`scripts/export_onnx.py`,
run offline against a `.pt` file); the served process runs the exported graph
through onnxruntime and nothing else, so the AGPL code never ships inside the
API process (T6 plan, decision 2026-10-10).

YOLO26 is NMS-free by design (see `training.detector_bakeoff.build_yolo26l_sku110k`'s
docstring). The assumption this module is built on -- unverified until Task 6's
real smoke run against an actual exported graph, since this box has no copy of
`models/yolo26l-sku110k.pt` to export -- is that the exported ONNX graph has one
output tensor shaped ``(1, N, 6)``: rows of ``[x1, y1, x2, y2, confidence,
class_id]`` in letterboxed input-image pixel coordinates, already sorted and
NMS'd, with unused slots zero-padded (so a plain confidence cutoff is enough,
no extra NMS pass). If Task 6 finds a different export shape, fix it there
and update this note.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from face_counter.training.detector_bakeoff import GEOMETRY_LABEL, Detections


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


def _load_session(onnx_path: Path):
    """Heavy import stays inside the function, like the rest of the codebase's
    model loaders, so this module imports instantly for tests (monkeypatched)."""
    import onnxruntime as ort

    return ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])


def build(onnx_path: Path, imgsz: int, conf: float):
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
        rows = np.asarray(out)[0]  # (N, 6): x1, y1, x2, y2, confidence, class_id

        boxes: list[list[float]] = []
        scores: list[float] = []
        labels: list[str] = []
        for x1, y1, x2, y2, score, _cls in rows:
            if score < conf:
                continue
            boxes.append(
                [
                    (float(x1) - left) / scale,
                    (float(y1) - top) / scale,
                    (float(x2) - left) / scale,
                    (float(y2) - top) / scale,
                ]
            )
            scores.append(float(score))
            labels.append(GEOMETRY_LABEL)
        return Detections(boxes=boxes, scores=scores, labels=labels)

    return detect
