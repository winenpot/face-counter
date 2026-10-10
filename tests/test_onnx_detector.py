"""Tests for the ONNX Runtime detector (serving/onnx_detector.py).

No real ONNX Runtime session is ever created: `_load_session` is monkeypatched,
the same way the rest of the codebase keeps heavy-model loaders out of tests
(e.g. test_bakeoff.py, test_identification.py). Importing `onnxruntime` or
`ultralytics` for real is never exercised here.

The fake session returns rows shaped (4 + nc, A) -- the verified real export
shape (hemin, 2026-10-10): cx, cy, w, h, then one score per class, raw grid,
no NMS applied by the graph itself.
"""

from __future__ import annotations

import sys

import numpy as np
import pytest
from PIL import Image

from face_counter.serving import onnx_detector as od


class _FakeInput:
    name = "images"


class _FakeSession:
    def __init__(self, rows: np.ndarray):
        self._rows = rows  # (4 + nc, A), pre-transpose, matching the real graph
        self.feeds: list[dict] = []

    def get_inputs(self):
        return [_FakeInput()]

    def run(self, output_names, feed):
        self.feeds.append(feed)
        return [self._rows[None, ...]]  # (1, 4 + nc, A)


def _row(cx, cy, w, h, score):
    return [cx, cy, w, h, score]


def test_letterbox_preserves_aspect_and_centers_padding():
    img = Image.new("RGB", (100, 50), "red")  # 2:1, wider than tall
    padded, scale, (left, top) = od._letterbox(img, 64)
    assert padded.size == (64, 64)
    assert scale == 64 / 100
    assert left == 0          # full width used, no horizontal padding
    assert top == 16          # (64 - 50*0.64) / 2 = 16


def test_xywh_to_xyxy():
    boxes = np.array([[10.0, 10.0, 4.0, 2.0]])  # cx, cy, w, h
    xyxy = od._xywh_to_xyxy(boxes)
    assert xyxy.tolist() == [[8.0, 9.0, 12.0, 11.0]]


def test_nms_drops_heavily_overlapping_lower_score_box():
    boxes = np.array([
        [0.0, 0.0, 10.0, 10.0],   # high score
        [1.0, 1.0, 11.0, 11.0],   # near-identical box, lower score
        [50.0, 50.0, 60.0, 60.0],  # far away, independent
    ])
    scores = np.array([0.9, 0.8, 0.7])
    keep = od._nms(boxes, scores, iou_threshold=0.45)
    assert keep == [0, 2]  # box 1 suppressed by box 0; box 2 always kept


def test_build_filters_by_confidence_and_unletterboxes(monkeypatch):
    # Grid columns, pre-transpose: (4 + nc=1, A=2). cx, cy, w, h, score.
    rows = np.array([
        _row(15.0, 31.0, 10.0, 10.0, 0.9),  # keep: box [10,26,20,36]
        _row(6.5, 6.5, 3.0, 3.0, 0.1),       # below threshold, dropped
    ]).T.astype(np.float32)
    fake = _FakeSession(rows)
    monkeypatch.setattr(od, "_load_session", lambda path: fake)

    detect = od.build(onnx_path="fake.onnx", imgsz=64, conf=0.25)
    img = Image.new("RGB", (100, 50), "blue")
    dets = detect(img)

    assert dets.scores == pytest.approx([0.9])
    assert dets.labels == ["product"]
    # scale = 64/100 = 0.64; letterbox padding for this image: left=0, top=16
    scale, left, top = 64 / 100, 0, 16
    x1, y1, x2, y2 = dets.boxes[0]
    assert x1 == pytest.approx((10.0 - left) / scale)
    assert y1 == pytest.approx((26.0 - top) / scale)
    assert x2 == pytest.approx((20.0 - left) / scale)
    assert y2 == pytest.approx((36.0 - top) / scale)

    # fed array is NCHW, batch of 1, 3 channels
    fed = fake.feeds[0]["images"]
    assert fed.shape == (1, 3, 64, 64)


def test_build_returns_nothing_below_zero_rows(monkeypatch):
    rows = np.zeros((5, 0), dtype=np.float32)  # (4 + nc, A=0)
    monkeypatch.setattr(od, "_load_session", lambda path: _FakeSession(rows))
    detect = od.build(onnx_path="fake.onnx", imgsz=64, conf=0.25)
    dets = detect(Image.new("RGB", (10, 10)))
    assert dets.boxes == [] and dets.scores == [] and dets.labels == []


def test_build_never_imports_ultralytics(monkeypatch):
    sys.modules.pop("ultralytics", None)
    rows = np.zeros((5, 0), dtype=np.float32)
    monkeypatch.setattr(od, "_load_session", lambda path: _FakeSession(rows))

    detect = od.build(onnx_path="fake.onnx", imgsz=64, conf=0.25)
    detect(Image.new("RGB", (10, 10)))

    assert "ultralytics" not in sys.modules
