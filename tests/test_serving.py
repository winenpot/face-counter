"""Tests for the serving pipeline (serving/pipeline.py, T6 plan).

All model calls are monkeypatched; nothing is downloaded or run on GPU.
Pipeline is constructed directly (not via .load()) so these tests never
touch the real ONNX detector, DINOv2 embedder, or CLIP classifier.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from face_counter.evaluation import share
from face_counter.identification import embedder, gallery, pack_type
from face_counter.identification.gallery import GalleryImage
from face_counter.serving import pipeline as pipe
from face_counter.serving import schemas
from face_counter.training.detector_bakeoff import Detections
from face_counter.utils import taxonomy as tax_mod

CLASSES = """\
class_name,brand,pack_type,sku,is_ours,source
Kix-Max_canned,Kix-Max,canned,,1,invoice
Kix-Max_glass,Kix-Max,glass,,1,invoice
COMPETITOR_canned,COMPETITOR,canned,,0,manual
COMPETITOR_glass,COMPETITOR,glass,,0,manual
out_of_scope,out_of_scope,,,0,manual
"""

REPORTING = """\
categories:
  canned_drinks:
    pack_types: [canned]
  glass_drinks:
    pack_types: [glass]
"""

SCOPE = """\
brands: [Kix-Max]
categories: [canned_drinks, glass_drinks]
share_against: targeted
detail: brand
"""


def _write_configs(tmp_path):
    classes = tmp_path / "classes.csv"
    reporting = tmp_path / "reporting.yaml"
    scope = tmp_path / "scope.yaml"
    classes.write_text(CLASSES, encoding="utf-8")
    reporting.write_text(REPORTING, encoding="utf-8")
    scope.write_text(SCOPE, encoding="utf-8")
    return classes, reporting, scope


def _make_pipeline(tmp_path, detector, pack_types_result):
    classes, reporting_path, scope = _write_configs(tmp_path)
    cfg = pipe.ServeConfig(classes_path=classes, reporting_path=reporting_path, scope_path=scope)
    reporting = tax_mod.load_reporting(reporting_path)
    p = pipe.Pipeline(cfg, detector, reporting)
    return p


# ---------------------------------------------------------------------------
# Default path: detection + pack-type counting, no gallery/matcher touched
# ---------------------------------------------------------------------------

def test_run_counts_by_pack_type_without_debug(tmp_path, monkeypatch):
    def fake_detector(img):
        return Detections(boxes=[[0, 0, 10, 10], [10, 10, 20, 20]], scores=[0.9, 0.8], labels=["product"] * 2)

    p = _make_pipeline(tmp_path, fake_detector, None)
    monkeypatch.setattr(pack_type, "pack_types", lambda crops, **kw: ["canned", "glass"])

    result = p.run(Image.new("RGB", (100, 100)))

    assert result.units_detected == 2
    assert result.categories == {"canned_drinks": 1, "glass_drinks": 1}
    assert [b.pack_type for b in result.boxes] == ["canned", "glass"]
    assert [b.category for b in result.boxes] == ["canned_drinks", "glass_drinks"]
    assert result.debug is None


def test_run_zero_boxes_no_crash(tmp_path, monkeypatch):
    def empty_detector(img):
        return Detections(boxes=[], scores=[], labels=[])

    p = _make_pipeline(tmp_path, empty_detector, None)
    monkeypatch.setattr(pack_type, "pack_types", lambda crops, **kw: [])

    result = p.run(Image.new("RGB", (50, 50)))

    assert result.units_detected == 0
    assert result.categories == {}
    assert result.boxes == []
    assert result.debug is None


def test_run_without_debug_never_touches_gallery(tmp_path, monkeypatch):
    def fake_detector(img):
        return Detections(boxes=[[0, 0, 5, 5]], scores=[0.9], labels=["product"])

    p = _make_pipeline(tmp_path, fake_detector, None)
    monkeypatch.setattr(pack_type, "pack_types", lambda crops, **kw: ["canned"])

    def boom(**kw):
        raise AssertionError("gallery.build must not be called when debug=False")

    monkeypatch.setattr(gallery, "build", boom)

    result = p.run(Image.new("RGB", (20, 20)), debug=False)
    assert result.units_detected == 1


# ---------------------------------------------------------------------------
# Debug path: opt-in matcher + share, heavily caveated
# ---------------------------------------------------------------------------

def test_run_debug_adds_caveated_share(tmp_path, monkeypatch):
    def fake_detector(img):
        return Detections(boxes=[[0, 0, 10, 10]], scores=[0.9], labels=["product"])

    p = _make_pipeline(tmp_path, fake_detector, None)
    monkeypatch.setattr(pack_type, "pack_types", lambda crops, **kw: ["canned"])
    monkeypatch.setattr(pack_type, "score_crops", lambda crops, **kw: [0.5] * len(crops))

    invoice_dir = tmp_path / "invoice"
    invoice_dir.mkdir()
    Image.new("RGB", (10, 10)).save(invoice_dir / "ref.png")
    monkeypatch.setattr(gallery, "build", lambda **kw: [
        GalleryImage(path=invoice_dir / "ref.png", label="Kix-Max_canned", ours=True)
    ])
    monkeypatch.setattr(embedder, "embed_paths", lambda paths, **kw: np.array([[1.0, 0.0]]))
    monkeypatch.setattr(embedder, "embed_images", lambda imgs, **kw: np.array([[1.0, 0.0]] * len(imgs)))

    result = p.run(Image.new("RGB", (100, 100)), debug=True)

    assert result.debug is not None
    assert result.debug.boxes[0].label == "Kix-Max_canned"
    assert result.debug.boxes[0].role == "ours"
    assert isinstance(result.debug.share.categories, dict)
    assert any("EXPERIMENTAL" in c for c in result.debug.caveats)
    # the reliable, non-debug numbers are still computed the same way
    assert result.categories == {"canned_drinks": 1}


def test_serve_config_from_env_reads_defaults(monkeypatch):
    monkeypatch.delenv("FACE_COUNTER_API_KEY", raising=False)
    cfg = pipe.ServeConfig.from_env()
    assert cfg.api_key == "12345678"
    assert cfg.match_threshold == pytest.approx(0.7115)


# ---------------------------------------------------------------------------
# schemas.py: CountResponse / DebugResponse, NaN -> null, debug omitted
# ---------------------------------------------------------------------------

def test_from_result_omits_debug_when_absent():
    result = pipe.Result(
        units_detected=1,
        categories={"canned_drinks": 1},
        boxes=[pipe.BoxResult(xyxy=(0, 0, 10, 10), pack_type="canned", category="canned_drinks", score=0.9)],
        timings_ms={"total_ms": 5.0},
    )
    resp = schemas.from_result(result, schemas.ModelInfo(detector="yolo26l-sku110k", pack_classifier="clip-vit-l14"))
    assert resp.debug is None
    dumped = resp.model_dump(exclude_none=True)
    assert "debug" not in dumped
    assert dumped["units_detected"] == 1


def test_from_result_converts_nan_share_to_none():
    cat_result = share.CategoryResult(ours=0, targeted=0, share=float("nan"))
    rep = share.ShareReport(share_against="targeted", categories={"canned_drinks": cat_result}, per_photo=[])
    debug = pipe.DebugResult(
        boxes=[pipe.DebugBoxResult(xyxy=(0, 0, 5, 5), label="product", role=None, similarity=0.1)],
        share=rep,
    )
    result = pipe.Result(units_detected=1, categories={}, boxes=[], timings_ms={}, debug=debug)
    resp = schemas.from_result(result, schemas.ModelInfo(detector="d", pack_classifier="c"))
    assert resp.debug is not None
    assert resp.debug.share["canned_drinks"].share is None
    assert any("EXPERIMENTAL" in c for c in resp.debug.caveats)
