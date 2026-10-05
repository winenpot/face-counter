"""Tests for T5: predict.py and cli.py --predict path.

All model calls are monkeypatched; nothing is downloaded or run on GPU.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from face_counter.evaluation import ls_export, share
from face_counter.evaluation.cli import summary_predict_comparison
from face_counter.evaluation.ls_export import Box, Photo
from face_counter.identification import embedder, gallery, matcher
from face_counter.identification.gallery import GalleryImage
from face_counter.identification import predict as pred_mod


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CLASSES = """\
class_name,brand,pack_type,sku,is_ours,source
Kix-Max_canned,Kix-Max,canned,,1,invoice
Kix-Max_glass,Kix-Max,glass,,1,invoice
TorshX_canned,TorshX,canned,,1,invoice
TorshX_glass,TorshX,glass,,1,invoice
Icy-Monkey_canned,Icy-Monkey,canned,,0,manual
Icy-Monkey_glass,Icy-Monkey,glass,,0,manual
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
brands: [Kix-Max, TorshX]
categories: [canned_drinks, glass_drinks]
competitors:
  - Icy-Monkey
share_against: targeted
detail: brand
"""


def _make_photo(file_name: str, boxes: list[Box], task_id: int = 1) -> Photo:
    return Photo(task_id=task_id, inner_id=task_id, photo_id=file_name,
                 file_name=file_name, width=100, height=100, scene="open-fridge",
                 capture=[], photo_issue=[], boxes=boxes)


# ---------------------------------------------------------------------------
# predict_photos: crop -> embed -> match / pack_type pipeline
# ---------------------------------------------------------------------------

def test_predict_matched_box_uses_gallery_label(tmp_path, monkeypatch):
    """A box that matches the gallery above threshold gets the gallery label."""
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img_path = tmp_path / "a.jpg"
    img.save(str(img_path))

    gt = _make_photo("a.jpg", [Box((10, 10, 50, 50), "product")])
    det = {"file_name": "a.jpg", "boxes": [[10, 10, 50, 50]], "scores": [0.9]}
    gallery_images = [GalleryImage(path=tmp_path / "ref.jpg", label="Kix-Max_canned", ours=True)]

    # gallery embedding: unit vector along dim 0
    gallery_embs = np.array([[1.0, 0.0]])
    # embed_images returns same vector for any image -> similarity == 1.0 > threshold
    monkeypatch.setattr(embedder, "embed_images",
                        lambda imgs, **kw: np.array([[1.0, 0.0]] * len(imgs)))

    photos = pred_mod.predict_photos(
        detections=[det], gt_photos=[gt], images_dir=tmp_path,
        gallery_images=gallery_images, gallery_embeddings=gallery_embs,
        threshold=0.5,
    )
    assert len(photos) == 1
    assert photos[0].boxes[0].label == "Kix-Max_canned"


def test_predict_unmatched_box_uses_pack_type(tmp_path, monkeypatch):
    """A box below threshold gets COMPETITOR_<pack> from the T4 classifier."""
    img = Image.new("RGB", (100, 100))
    img_path = tmp_path / "b.jpg"
    img.save(str(img_path))

    gt = _make_photo("b.jpg", [Box((0, 0, 10, 10), "product")])
    det = {"file_name": "b.jpg", "boxes": [[0, 0, 10, 10]], "scores": [0.5]}
    gallery_images = [GalleryImage(path=tmp_path / "ref.jpg", label="Kix-Max_glass", ours=True)]

    gallery_embs = np.array([[1.0, 0.0]])
    # Crop embedding: orthogonal -> similarity 0 < threshold 0.9
    monkeypatch.setattr(embedder, "embed_images",
                        lambda imgs, **kw: np.array([[0.0, 1.0]] * len(imgs)))
    import face_counter.identification.pack_type as pt
    monkeypatch.setattr(pt, "score_crops", lambda crops, model_name=None, device=None: [2.0])  # > 0 -> glass

    photos = pred_mod.predict_photos(
        detections=[det], gt_photos=[gt], images_dir=tmp_path,
        gallery_images=gallery_images, gallery_embeddings=gallery_embs,
        threshold=0.9,
    )
    assert photos[0].boxes[0].label == "COMPETITOR_glass"


def test_predict_missing_image_gives_empty_boxes(tmp_path, monkeypatch):
    """A photo whose image file is missing yields 0 predicted boxes, not an error."""
    gt = _make_photo("missing.jpg", [Box((0, 0, 10, 10), "product")])
    det = {"file_name": "missing.jpg", "boxes": [[0, 0, 10, 10]], "scores": [0.9]}
    gallery_images = [GalleryImage(path=tmp_path / "ref.jpg", label="Kix-Max_canned", ours=True)]
    gallery_embs = np.array([[1.0, 0.0]])
    monkeypatch.setattr(embedder, "embed_images",
                        lambda imgs, **kw: np.empty((0, 2)))

    photos = pred_mod.predict_photos(
        detections=[det], gt_photos=[gt], images_dir=tmp_path,
        gallery_images=gallery_images, gallery_embeddings=gallery_embs,
        threshold=0.5,
    )
    assert photos[0].boxes == []


def test_predict_missing_detection_gives_empty_boxes(tmp_path, monkeypatch):
    """A GT photo with no matching detection entry yields 0 predicted boxes."""
    gt = _make_photo("no_det.jpg", [Box((0, 0, 10, 10), "product")])
    gallery_images = [GalleryImage(path=tmp_path / "ref.jpg", label="Kix-Max_canned", ours=True)]
    gallery_embs = np.array([[1.0, 0.0]])
    monkeypatch.setattr(embedder, "embed_images",
                        lambda imgs, **kw: np.empty((0, 2)))

    photos = pred_mod.predict_photos(
        detections=[], gt_photos=[gt], images_dir=tmp_path,
        gallery_images=gallery_images, gallery_embeddings=gallery_embs,
        threshold=0.5,
    )
    assert photos[0].boxes == []


def test_predict_gt_metadata_preserved(tmp_path, monkeypatch):
    """Scene/capture/task metadata from GT Photo is preserved in predicted Photo."""
    img = Image.new("RGB", (100, 100))
    img.save(str(tmp_path / "c.jpg"))

    gt = Photo(task_id=42, inner_id=7, photo_id="abc", file_name="c.jpg",
               width=200, height=300, scene="glass-door-fridge",
               capture=["reflection"], photo_issue=["multi-bay"],
               boxes=[Box((0, 0, 10, 10), "product")])
    det = {"file_name": "c.jpg", "boxes": [[0, 0, 10, 10]], "scores": [0.9]}
    gallery_images = [GalleryImage(path=tmp_path / "ref.jpg", label="Kix-Max_canned", ours=True)]
    gallery_embs = np.array([[1.0, 0.0]])
    monkeypatch.setattr(embedder, "embed_images",
                        lambda imgs, **kw: np.array([[1.0, 0.0]]))

    photos = pred_mod.predict_photos(
        detections=[det], gt_photos=[gt], images_dir=tmp_path,
        gallery_images=gallery_images, gallery_embeddings=gallery_embs,
        threshold=0.0,
    )
    p = photos[0]
    assert p.task_id == 42
    assert p.inner_id == 7
    assert p.scene == "glass-door-fridge"
    assert p.capture == ["reflection"]
    assert p.photo_issue == ["multi-bay"]
    assert p.width == 200
    assert p.height == 300


# ---------------------------------------------------------------------------
# summary_predict_comparison
# ---------------------------------------------------------------------------

def _make_share_report(ours: int, targeted: int) -> share.ShareReport:
    from collections import Counter
    from face_counter.evaluation.share import CategoryResult, ShareReport
    denom = ours + targeted
    cat = CategoryResult(
        ours=ours, targeted=targeted, share=ours / denom if denom else float("nan"),
        share_targeted=ours / denom if denom else float("nan"),
    )
    return ShareReport(share_against="targeted", categories={"canned_drinks": cat}, per_photo=[])


def test_summary_predict_comparison_includes_share_error():
    gt_rep = _make_share_report(ours=10, targeted=10)   # share 50%
    pred_rep = _make_share_report(ours=12, targeted=10)  # share 54.5%
    text = summary_predict_comparison(gt_rep, pred_rep)
    assert "canned_drinks" in text
    assert "50.0%" in text
    assert "54.5%" in text
    # share error = 54.5 - 50.0 = +4.5%, sign matters
    assert "4.5%" in text


def test_summary_predict_comparison_caveat_present():
    gt_rep = _make_share_report(ours=5, targeted=5)
    pred_rep = _make_share_report(ours=5, targeted=5)
    text = summary_predict_comparison(gt_rep, pred_rep)
    assert "65.3%" in text
    assert "92.2%" in text


# ---------------------------------------------------------------------------
# cli --predict path: smoke test (embedder and pack_type fully mocked)
# ---------------------------------------------------------------------------

def _write_gold_export(path: Path, photos: list[dict]) -> None:
    path.write_text(json.dumps(photos), encoding="utf-8")


def test_cli_predict_smoke(tmp_path, monkeypatch):
    """End-to-end --predict run with all GPU calls mocked out."""
    import face_counter.identification.pack_type as pt
    monkeypatch.setattr(embedder, "_load_model",
                        lambda name, device: (None, None))
    monkeypatch.setattr(embedder, "embed_images",
                        lambda imgs, **kw: np.ones((len(imgs), 4)) / 2)
    monkeypatch.setattr(embedder, "embed_paths",
                        lambda paths, **kw: np.ones((len(paths), 4)) / 2)
    monkeypatch.setattr(pt, "score_crops", lambda crops, **kw: [0.5] * len(crops))

    # Write a minimal LS export (1 photo, 1 Kix-Max_canned box)
    export = [{
        "id": 1, "inner_id": 1,
        "data": {"photo_id": "x", "file_name": "img.jpg", "no": 1},
        "annotations": [{
            "id": 1, "was_cancelled": False, "updated_at": "2026-10-05T00:00:00Z",
            "result": [
                {"type": "rectanglelabels", "value": {"x": 10, "y": 10, "width": 20,
                 "height": 20, "rectanglelabels": ["Kix-Max_canned"]},
                 "original_width": 100, "original_height": 100},
                {"type": "choices", "from_name": "scene",
                 "value": {"choices": ["open-fridge"]}},
            ],
        }],
    }]
    labels_path = tmp_path / "export.json"
    _write_gold_export(labels_path, export)

    # Write a minimal detections.jsonl (1 box for the same image)
    det_path = tmp_path / "dets.jsonl"
    det_path.write_text(json.dumps({
        "model": "yolo26l-sku110k", "file_name": "img.jpg",
        "width": 100, "height": 100, "seconds": 0.1,
        "boxes": [[10, 10, 30, 30]], "scores": [0.9], "labels": ["object"],
    }) + "\n", encoding="utf-8")

    # Write a tiny real image so PIL can open it
    img = Image.new("RGB", (100, 100), color=(128, 0, 0))
    img.save(str(tmp_path / "img.jpg"))

    # Write config files
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")

    # Write minimal gallery image (just needs to open)
    gallery_img = Image.new("RGB", (50, 50), color=(0, 128, 0))
    invoice_dir = tmp_path / "invoice"
    invoice_dir.mkdir()
    gallery_img.save(str(invoice_dir / "Kix-Max_canned.png"))

    from face_counter.evaluation import cli as eval_cli
    import face_counter.identification.gallery as gal_mod
    # Override gallery.build to use our tmp fixtures
    monkeypatch.setattr(gal_mod, "build", lambda **kw: [
        GalleryImage(path=invoice_dir / "Kix-Max_canned.png", label="Kix-Max_canned", ours=True)
    ])

    out_dir = tmp_path / "out"
    eval_cli.main([
        "--labels", str(labels_path),
        "--detections", str(det_path),
        "--classes", str(tmp_path / "classes.csv"),
        "--reporting", str(tmp_path / "reporting.yaml"),
        "--scope", str(tmp_path / "scope.yaml"),
        "--predict",
        "--images-dir", str(tmp_path),
        "--match-threshold", "0.0",
        "--out-dir", str(out_dir),
        "--n-boot", "10",
    ])

    assert (out_dir / "summary.md").exists()
    text = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "Predicted share vs ground truth" in text
    assert (out_dir / "predicted_share.csv").exists()
    assert (out_dir / "predicted_share_per_photo.csv").exists()
