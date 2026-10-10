"""Tests for the ONNX Runtime detector (serving/onnx_detector.py).

No real ONNX Runtime session is ever created: `_load_session` is monkeypatched,
the same way the rest of the codebase keeps heavy-model loaders out of tests
(e.g. test_bakeoff.py, test_identification.py). Importing `onnxruntime` or
`ultralytics` for real is never exercised here.
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
        self._rows = rows
        self.feeds: list[dict] = []

    def get_inputs(self):
        return [_FakeInput()]

    def run(self, output_names, feed):
        self.feeds.append(feed)
        return [self._rows[None, ...]]  # (1, N, 6), as the real graph would


def test_letterbox_preserves_aspect_and_centers_padding():
    img = Image.new("RGB", (100, 50), "red")  # 2:1, wider than tall
    padded, scale, (left, top) = od._letterbox(img, 64)
    assert padded.size == (64, 64)
    assert scale == 64 / 100
    assert left == 0          # full width used, no horizontal padding
    assert top == 16          # (64 - 50*0.64) / 2 = 16


def test_build_filters_by_confidence_and_unletterboxes(monkeypatch):
    rows = np.array(
        [
            [10.0, 26.0, 20.0, 36.0, 0.9, 0.0],  # keep
            [5.0, 5.0, 8.0, 8.0, 0.1, 0.0],  # below threshold, dropped
        ],
        dtype=np.float32,
    )
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
    assert x1 == (10.0 - left) / scale
    assert y1 == (26.0 - top) / scale
    assert x2 == (20.0 - left) / scale
    assert y2 == (36.0 - top) / scale

    # fed array is NCHW, batch of 1, 3 channels
    fed = fake.feeds[0]["images"]
    assert fed.shape == (1, 3, 64, 64)


def test_build_returns_nothing_below_zero_rows(monkeypatch):
    rows = np.zeros((0, 6), dtype=np.float32)
    monkeypatch.setattr(od, "_load_session", lambda path: _FakeSession(rows))
    detect = od.build(onnx_path="fake.onnx", imgsz=64, conf=0.25)
    dets = detect(Image.new("RGB", (10, 10)))
    assert dets.boxes == [] and dets.scores == [] and dets.labels == []


def test_build_never_imports_ultralytics(monkeypatch):
    sys.modules.pop("ultralytics", None)
    rows = np.zeros((0, 6), dtype=np.float32)
    monkeypatch.setattr(od, "_load_session", lambda path: _FakeSession(rows))

    detect = od.build(onnx_path="fake.onnx", imgsz=64, conf=0.25)
    detect(Image.new("RGB", (10, 10)))

    assert "ultralytics" not in sys.modules
