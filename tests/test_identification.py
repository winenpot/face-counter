"""Tests for the identification package (gallery, embedder, matcher, pack_type,
cli): the stage-2 identifier (PILOT.md 4b/5). Heavy models (DINOv2, CLIP) are
never downloaded here -- `embedder._load_model` and `pack_type._load_model`
are monkeypatched with tiny fakes, same pattern as test_bakeoff.py's fake
ultralytics/transformers modules.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from face_counter.evaluation import share
from face_counter.identification import cli as match_cli
from face_counter.identification import embedder, gallery, matcher, pack_type

# --- gallery -----------------------------------------------------------------

CLASSES = """class_name,brand,pack_type,sku,is_ours,source
Kix-Max_canned_blue,Kix-Max,canned,blue,1,invoice
Kix-Max_canned_red,Kix-Max,canned,red,1,invoice
Kix-Max_glass_blue,Kix-Max,glass,blue,1,invoice
TorshX_canned_x,TorshX,canned,x,1,invoice
COMPETITOR_canned,COMPETITOR,canned,,0,manual
COMPETITOR_glass,COMPETITOR,glass,,0,manual
COMPETITOR_other,COMPETITOR,other,,0,manual
Icy-Monkey_canned,Icy-Monkey,canned,,0,manual
Icy-Monkey_glass,Icy-Monkey,glass,,0,manual
Genius_glass,Genius,glass,,0,manual
out_of_scope,out_of_scope,,,0,manual
"""
REPORTING = "categories:\n  canned_drinks: {pack_types: [canned]}\n  glass_drinks: {pack_types: [glass]}\n"
SCOPE = ("brands: [Kix-Max]\ncategories: [canned_drinks, glass_drinks]\n"
        "competitors: [Icy-Monkey]\nshare_against: targeted\ndetail: brand\n")


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")
    return tmp_path


def _png(path, color=(255, 0, 0)):
    Image.new("RGB", (8, 8), color).save(path)


def test_our_invoice_images_roll_up_to_brand_level(cfg):
    invoice = cfg / "invoice"
    invoice.mkdir()
    _png(invoice / "Kix-Max_canned_blue.png")    # row exists, in scope
    _png(invoice / "Kix-Max_canned_blue_2.png")  # second image, same class, trailing index
    _png(invoice / "Kix-Max_canned_red.png")     # different sku, same brand+pack
    _png(invoice / "Kix-Max_glass_blue.png")     # different pack type
    _png(invoice / "TorshX_canned_x.png")        # not a scoped brand
    competitors = cfg / "competitors"
    images = gallery.build(invoice, competitors, cfg / "classes.csv", cfg / "reporting.yaml",
                           cfg / "scope.yaml")
    ours = [g for g in images if g.ours]
    assert {g.label for g in ours} == {"Kix-Max_canned", "Kix-Max_glass"}
    assert sum(1 for g in ours if g.label == "Kix-Max_canned") == 3  # blue, blue_2, red


def test_untracked_competitor_and_non_class_files_are_excluded(cfg):
    invoice = cfg / "invoice"
    invoice.mkdir()
    competitors = cfg / "competitors"
    (competitors / "Icy-Monkey_canned").mkdir(parents=True)
    _png(competitors / "Icy-Monkey_canned" / "a.png")
    (competitors / "Icy-Monkey_canned" / "README.md").write_text("x", encoding="utf-8")
    (competitors / "Genius_glass").mkdir(parents=True)   # named, but not tracked by this scope
    _png(competitors / "Genius_glass" / "a.png")
    images = gallery.build(invoice, competitors, cfg / "classes.csv", cfg / "reporting.yaml",
                           cfg / "scope.yaml")
    assert [g.label for g in images if not g.ours] == ["Icy-Monkey_canned"]


def test_missing_gallery_folder_yields_no_images_not_an_error(cfg):
    invoice = cfg / "invoice"
    invoice.mkdir()
    competitors = cfg / "competitors"   # never created
    images = gallery.build(invoice, competitors, cfg / "classes.csv", cfg / "reporting.yaml",
                           cfg / "scope.yaml")
    assert images == []


def test_the_live_configs_build_a_non_empty_gallery():
    """Guards configs/: every tracked competitor plus our two pilot brands."""
    images = gallery.build()
    labels = {g.label for g in images}
    assert "Kix-Max_canned" in labels and "TorshX_glass" in labels
    assert "Icy-Monkey_glass" in labels and "Sunich-Cool_glass" in labels
    assert all(g.ours == (g.label.startswith(("Kix-Max_", "TorshX_"))) for g in images)


# --- embedder (model mocked) --------------------------------------------------

class _FakeImageProcessor:
    def __call__(self, images, return_tensors):
        import torch
        return _FakeBatchEncoding(torch.zeros(len(images), 3, 4, 4))


class _FakeBatchEncoding(dict):
    def __init__(self, pixel_values):
        super().__init__(pixel_values=pixel_values)

    def to(self, device):
        return self


class _FakeOutput:
    def __init__(self, pooler_output):
        self.pooler_output = pooler_output


class _FakeModel:
    """Embeds by average pixel colour, so distinct-coloured images get
    distinct, deterministic vectors without downloading a real model."""
    def eval(self):
        return self

    def to(self, device):
        return self

    def __call__(self, pixel_values):
        import torch
        n = pixel_values.shape[0]
        # A fixed, non-degenerate direction per image so normalize() is well
        # defined; real content doesn't matter, only that different calls
        # with different pixel content would plausibly differ.
        vecs = torch.arange(1, n + 1).float().unsqueeze(1) * torch.ones(n, 8)
        return _FakeOutput(vecs)


def test_embed_images_returns_l2_normalised_vectors(monkeypatch):
    monkeypatch.setattr(embedder, "_load_model",
                        lambda name, device: (_FakeImageProcessor(), _FakeModel()))
    images = [Image.new("RGB", (4, 4), c) for c in [(255, 0, 0), (0, 255, 0)]]
    embs = embedder.embed_images(images, device="cpu")
    assert embs.shape == (2, 8)
    norms = np.linalg.norm(embs, axis=1)
    assert norms == pytest.approx([1.0, 1.0])


def test_embed_paths_reports_the_bad_file(monkeypatch, tmp_path):
    monkeypatch.setattr(embedder, "_load_model",
                        lambda name, device: (_FakeImageProcessor(), _FakeModel()))
    bad = tmp_path / "not_an_image.txt"
    bad.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError, match=str(bad)):
        embedder.embed_paths([bad], device="cpu")


# --- matcher (pure vector math, no model) ------------------------------------

def _unit(v):
    v = np.array(v, dtype=float)
    return v / np.linalg.norm(v)


def test_nearest_batch_picks_the_closer_gallery_vector():
    gallery_emb = np.array([_unit([1, 0]), _unit([0, 1])])
    queries = np.array([_unit([0.9, 0.1]), _unit([0.1, 0.9])])
    out = matcher.nearest_batch(queries, gallery_emb, ["a", "b"], threshold=0.0)
    assert [m.label for m in out] == ["a", "b"]


def test_below_threshold_label_is_none_but_nearest_is_recorded():
    gallery_emb = np.array([_unit([1, 0])])
    query = np.array([_unit([0, 1])])   # orthogonal: similarity 0
    [m] = matcher.nearest_batch(query, gallery_emb, ["only"], threshold=0.5)
    assert m.label is None
    assert m.nearest_label == "only"
    assert m.similarity == pytest.approx(0.0, abs=1e-9)


def test_empty_gallery_is_rejected():
    with pytest.raises(ValueError, match="empty gallery"):
        matcher.nearest_batch(np.array([_unit([1, 0])]), np.empty((0, 2)), [], threshold=0.0)


def test_mismatched_gallery_embeddings_and_labels_are_rejected():
    with pytest.raises(ValueError, match="embeddings"):
        matcher.nearest_batch(np.array([_unit([1, 0])]), np.array([_unit([1, 0]), _unit([0, 1])]),
                             ["only-one-label"], threshold=0.0)


def test_best_threshold_separates_two_clean_clusters():
    scores = [0.9, 0.8, 0.7, 0.2, 0.1, 0.0]
    should_match = [True, True, True, False, False, False]
    best = matcher.best_threshold(scores, should_match)
    assert best["accuracy"] == pytest.approx(1.0)
    assert 0.2 < best["threshold"] <= 0.7


def test_best_threshold_picks_the_higher_threshold_on_a_tie():
    # Both 0.5 and 0.6 separate perfectly; ties favour fewer false matches.
    scores = [0.9, 0.6, 0.5, 0.1]
    should_match = [True, True, False, False]
    best = matcher.best_threshold(scores, should_match)
    assert best["accuracy"] == pytest.approx(1.0)
    assert best["threshold"] == pytest.approx(0.6)


def test_best_threshold_rejects_an_empty_score_list():
    with pytest.raises(ValueError, match="no scores"):
        matcher.best_threshold([], [])


# --- pack_type (CLIP mocked) --------------------------------------------------

class _FakeClipModel:
    def eval(self):
        return self

    def to(self, device):
        return self

    def get_image_features(self, pixel_values):
        return pixel_values   # pass-through: the fake processor encodes intent below

    def get_text_features(self, input_ids):
        return input_ids


class _FakeClipProcessor:
    """Encodes a crop's own (fake) "glassiness" into its feature vector, and
    prompts into fixed can/glass directions, so the scorer's sign is
    predictable without a real CLIP model."""
    def __call__(self, images=None, text=None, return_tensors=None, padding=None):
        import torch
        if images is not None:
            vecs = torch.stack([torch.tensor(im.size, dtype=torch.float32) for im in images])
            return _ToTensorDict("pixel_values", vecs)
        # Three prompt pairs; "glass" prompts share one direction, "can" another.
        is_glass = ["glass" in t or "bottle" in t for t in text]
        vecs = torch.tensor([[0.0, 1.0] if g else [1.0, 0.0] for g in is_glass])
        return _ToTensorDict("input_ids", vecs)


class _ToTensorDict(dict):
    def __init__(self, key, tensor):
        super().__init__({key: tensor})

    def to(self, device):
        return self


def test_glass_crop_scores_above_a_can_crop(monkeypatch):
    monkeypatch.setattr(pack_type, "_load_model",
                        lambda name, device: (_FakeClipProcessor(), _FakeClipModel()))
    # A square "crop" encodes as [1, 1] under the fake processor, which has no
    # inherent can/glass direction; instead pin PROMPTS directly for a clean
    # signal by using differently-shaped fakes as stand-ins for can vs glass.
    can_like = Image.new("RGB", (10, 1))    # size (10, 1) -> feature [10, 1]
    glass_like = Image.new("RGB", (1, 10))  # size (1, 10) -> feature [1, 10]
    scores = pack_type.score_crops([can_like, glass_like], device="cpu")
    assert scores[1] > scores[0]


def test_pack_types_thresholds_at_zero(monkeypatch):
    monkeypatch.setattr(pack_type, "score_crops", lambda crops, model_name=None, device=None: [1.0, -1.0])
    fake_crops = [Image.new("RGB", (1, 1)), Image.new("RGB", (1, 1))]
    assert pack_type.pack_types(fake_crops, device="cpu") == ["glass", "canned"]


# --- cli (tune): threshold tuning end to end, embedder mocked -----------------

def _box(x, y, w, h, label, W=100, H=100):
    value = {"x": 100 * x / W, "y": 100 * y / H, "width": 100 * w / W, "height": 100 * h / H,
            "rotation": 0, "rectanglelabels": [label]}
    return {"type": "rectanglelabels", "from_name": "label", "to_name": "image",
           "original_width": W, "original_height": H, "value": value}


def _choice(name, *values):
    return {"type": "choices", "from_name": name, "to_name": "image", "value": {"choices": list(values)}}


def _ann(result):
    return {"id": 1, "result": result, "was_cancelled": False,
           "updated_at": "2026-10-05T10:00:00Z", "created_at": "2026-10-05T10:00:00Z"}


def _task(tid, file_name, result):
    return {"id": tid, "inner_id": tid, "annotations": [_ann(result)], "drafts": [],
           "data": {"photo_id": file_name.split(".")[0], "file_name": file_name,
                    "image": f"/data/local-files/?d=raw/images/{file_name}"}}


def test_collect_crops_keeps_only_resolvable_boxes(tmp_path):
    Image.new("RGB", (100, 100), "white").save(tmp_path / "a.jpg")
    export = [_task(1, "a.jpg", [
        _box(0, 0, 20, 20, "Kix-Max_canned"),       # ours: should_match True
        _box(30, 0, 20, 20, "Icy-Monkey_canned"),   # targeted: should_match True
        _box(60, 0, 20, 20, "COMPETITOR_canned"),   # untargeted: should_match False
        _box(0, 60, 20, 20, "product"),             # unresolved: dropped entirely
        _box(30, 60, 2, 2, "Kix-Max_canned"),       # below MIN_SIDE: dropped
        _choice("scene", "open-fridge"),
    ])]
    labels = tmp_path / "e.json"
    labels.write_text(json.dumps(export), encoding="utf-8")
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")
    tax = share.Taxonomy.load(tmp_path / "classes.csv", tmp_path / "reporting.yaml",
                              tmp_path / "scope.yaml")
    crops, meta, skipped = match_cli.collect_crops(labels, tmp_path, tax)
    assert len(crops) == 3
    assert [m["should_match"] for m in meta] == [True, True, False]
    assert skipped == {}


def test_tune_cli_writes_a_threshold_and_confusion_counts(tmp_path, monkeypatch):
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")
    invoice = tmp_path / "invoice"
    invoice.mkdir()
    _png(invoice / "Kix-Max_canned_blue.png", (200, 0, 0))
    competitors = tmp_path / "competitors"
    (competitors / "Icy-Monkey_canned").mkdir(parents=True)
    _png(competitors / "Icy-Monkey_canned" / "a.png", (0, 200, 0))

    images_dir = tmp_path / "images"
    images_dir.mkdir()
    Image.new("RGB", (100, 100), "white").save(images_dir / "a.jpg")
    export = [_task(1, "a.jpg", [
        _box(0, 0, 20, 20, "Kix-Max_canned"),
        _box(30, 0, 20, 20, "Icy-Monkey_canned"),
        _box(60, 0, 20, 20, "COMPETITOR_canned"),
        _choice("scene", "open-fridge"),
    ])]
    labels = tmp_path / "e.json"
    labels.write_text(json.dumps(export), encoding="utf-8")

    def fake_embed_paths(paths, model_name=None, device=None, batch_size=32):
        # Gallery order is deterministic (gallery.build sorts by path):
        # Icy-Monkey_canned/a.png, Kix-Max_canned_blue.png.
        return np.array([_unit([0, 1]), _unit([1, 0])])

    def fake_embed_images(images, model_name=None, device=None, batch_size=32):
        # Three crops in box order: Kix-Max match, Icy-Monkey match, untracked (neither).
        return np.array([_unit([1, 0]), _unit([0, 1]), _unit([1, 1])])

    monkeypatch.setattr(embedder, "embed_paths", fake_embed_paths)
    monkeypatch.setattr(embedder, "embed_images", fake_embed_images)
    out = tmp_path / "out"
    match_cli.main(["--classes", str(tmp_path / "classes.csv"),
                   "--reporting", str(tmp_path / "reporting.yaml"),
                   "--scope", str(tmp_path / "scope.yaml"),
                   "--invoice-dir", str(invoice), "--competitors-dir", str(competitors),
                   "tune", "--labels", str(labels), "--images-dir", str(images_dir),
                   "--device", "cpu", "--out-dir", str(out)])
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["n_crops"] == 3
    assert results["best_threshold"]["accuracy"] == pytest.approx(1.0)
    assert (out / "crops.jsonl").exists()
    lines = [json.loads(line) for line in (out / "crops.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3


def test_gallery_cli_reports_each_label(tmp_path, capsys):
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")
    invoice = tmp_path / "invoice"
    invoice.mkdir()
    _png(invoice / "Kix-Max_canned_blue.png")
    competitors = tmp_path / "competitors"
    match_cli.main(["--classes", str(tmp_path / "classes.csv"),
                   "--reporting", str(tmp_path / "reporting.yaml"),
                   "--scope", str(tmp_path / "scope.yaml"),
                   "--invoice-dir", str(invoice), "--competitors-dir", str(competitors),
                   "gallery"])
    out = capsys.readouterr().out
    assert "Kix-Max_canned" in out


def test_gallery_cli_refuses_an_empty_gallery(tmp_path):
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")
    invoice = tmp_path / "invoice"
    invoice.mkdir()
    competitors = tmp_path / "competitors"
    with pytest.raises(SystemExit, match="empty gallery"):
        match_cli.main(["--classes", str(tmp_path / "classes.csv"),
                       "--reporting", str(tmp_path / "reporting.yaml"),
                       "--scope", str(tmp_path / "scope.yaml"),
                       "--invoice-dir", str(invoice), "--competitors-dir", str(competitors),
                       "gallery"])
