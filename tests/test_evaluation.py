"""Evaluation against Label Studio exports: parsing, box matching, detector
metrics, and share of shelf. Hand-made fixtures with known answers.

The share tests also pin the extensibility promise: brands, targeted
competitors and categories come from config files only, so a business
decision like "Coca-Cola is now a targeted competitor" is a config edit that
changes the number, with no code change.
"""
import json

import pytest

from face_counter.evaluation import detector, ls_export, match, share
from face_counter.evaluation.bootstrap import bootstrap_ci
from face_counter.utils import taxonomy


# --- fixtures ----------------------------------------------------------------

def _box(x, y, w, h, label: str | None = "product", W=1000, H=2000, **extra):
    """A Label Studio rectangle in percent of a W x H displayed image, given in pixels."""
    value = {"x": 100 * x / W, "y": 100 * y / H, "width": 100 * w / W, "height": 100 * h / H,
             "rotation": 0}
    if label is not None:
        value["rectanglelabels"] = [label]
    return {"type": "rectanglelabels", "from_name": "label", "to_name": "image",
            "original_width": W, "original_height": H, "value": value, **extra}


def _choice(name, *values):
    return {"type": "choices", "from_name": name, "to_name": "image", "value": {"choices": list(values)}}


def _ann(result, updated="2026-09-28T10:00:00Z", cancelled=False, id=1):
    return {"id": id, "result": result, "was_cancelled": cancelled, "updated_at": updated,
            "created_at": updated}


def _task(tid, inner, file_name, annotations, drafts=()):
    return {"id": tid, "inner_id": inner, "annotations": annotations, "drafts": list(drafts),
            "data": {"photo_id": file_name.rsplit(".", 1)[0], "file_name": file_name,
                     "image": f"/data/local-files/?d=raw/images/{file_name}"}}


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")
    return p


# --- ls_export ---------------------------------------------------------------

def test_boxes_are_converted_from_percent_to_displayed_pixels(tmp_path):
    export = [_task(101, 1, "a.jpg", [_ann([_box(100, 200, 50, 80, "Kix-Max_canned"),
                                           _choice("scene", "open-fridge")])])]
    [p] = ls_export.load(_write(tmp_path, "e.json", export))
    assert (p.width, p.height) == (1000, 2000)
    [b] = p.boxes
    assert b.xyxy == pytest.approx((100, 200, 150, 280))
    assert b.label == "Kix-Max_canned"
    assert p.scene == "open-fridge"
    assert (p.task_id, p.inner_id, p.file_name) == (101, 1, "a.jpg")


def test_a_box_with_no_label_counts_as_product(tmp_path):
    export = [_task(1, 1, "a.jpg", [_ann([_box(0, 0, 10, 10, None), _box(0, 0, 10, 10, "")])])]
    [p] = ls_export.load(_write(tmp_path, "e.json", export))
    assert [b.label for b in p.boxes] == [taxonomy.PRODUCT, taxonomy.PRODUCT]


def test_the_latest_submitted_annotation_wins_and_cancelled_ones_are_ignored(tmp_path):
    old = _ann([_box(0, 0, 10, 10)], updated="2026-09-28T10:00:00Z", id=1)
    new = _ann([_box(0, 0, 10, 10), _box(20, 20, 10, 10)], updated="2026-09-28T11:00:00Z", id=2)
    skipped = _ann([], updated="2026-09-28T12:00:00Z", cancelled=True, id=3)
    export = [_task(1, 1, "a.jpg", [old, skipped, new])]
    [p] = ls_export.load(_write(tmp_path, "e.json", export))
    assert len(p.boxes) == 2
    assert any("2 submitted annotations" in w for w in p.warnings)


def test_a_draft_newer_than_the_submission_is_warned_about(tmp_path):
    draft = {"updated_at": "2026-09-28T12:00:00Z", "result": []}
    export = [_task(1, 1, "a.jpg", [_ann([_box(0, 0, 10, 10)])], drafts=[draft])]
    [p] = ls_export.load(_write(tmp_path, "e.json", export))
    assert any("draft" in w for w in p.warnings)


def test_photos_with_no_submitted_annotation_are_skipped(tmp_path):
    export = [_task(1, 1, "a.jpg", []), _task(2, 2, "b.jpg", [_ann([_box(0, 0, 10, 10)])])]
    assert [p.file_name for p in ls_export.load(_write(tmp_path, "e.json", export))] == ["b.jpg"]


def test_rotated_boxes_are_refused(tmp_path):
    b = _box(0, 0, 10, 10)
    b["value"]["rotation"] = 15
    with pytest.raises(ValueError, match="rotat"):
        ls_export.load(_write(tmp_path, "e.json", [_task(1, 1, "a.jpg", [_ann([b])])]))


# --- match -------------------------------------------------------------------

def test_iou_of_identical_disjoint_and_half_overlapping_boxes():
    assert match.iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert match.iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert match.iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_greedy_matching_is_one_to_one_in_score_order():
    gt = [(0, 0, 10, 10)]
    preds = [(0, 0, 10, 10), (0, 0, 10, 9)]   # both overlap the one real product
    r = match.greedy(preds, [0.5, 0.9], gt, thr=0.5)
    assert r.tp == 1 and r.fp == 1 and r.fn == 0
    assert r.matched_pred == [1]              # the higher score takes it
    assert r.duplicates == 1                  # the other one is a second box on it


def test_ap_is_one_for_perfect_detections_and_lower_when_a_false_positive_ranks_first():
    gt = {"a": [(0, 0, 10, 10), (20, 0, 30, 10)]}
    perfect = {"a": ([(0, 0, 10, 10), (20, 0, 30, 10)], [0.9, 0.8])}
    assert match.average_precision(perfect, gt, 0.5) == pytest.approx(1.0)
    fp_first = {"a": ([(50, 50, 60, 60), (0, 0, 10, 10), (20, 0, 30, 10)], [0.99, 0.9, 0.8])}
    assert match.average_precision(fp_first, gt, 0.5) < 1.0


# --- detector ----------------------------------------------------------------

def _photo(file_name, boxes, scene="open-fridge", W=1000, H=2000):
    return ls_export.Photo(task_id=1, inner_id=1, photo_id=file_name.split(".")[0], file_name=file_name,
                           width=W, height=H, scene=scene, capture=[], photo_issue=[],
                           boxes=[ls_export.Box(b, taxonomy.PRODUCT) for b in boxes], warnings=[])


def _dets(model, file_name, boxes, scores, W=1000, H=2000):
    return {"model": model, "file_name": file_name, "width": W, "height": H,
            "boxes": boxes, "scores": scores}


def test_detector_metrics_count_tp_fp_fn_duplicates_and_count_error():
    photos = [_photo("a.jpg", [(0, 0, 10, 10), (20, 0, 30, 10)]),
              _photo("b.jpg", [(0, 0, 10, 10)], scene="shelf-aisle")]
    dets = [_dets("m", "a.jpg", [[0, 0, 10, 10], [0, 0, 10, 9.5]], [0.9, 0.8]),
            _dets("m", "b.jpg", [[0, 0, 10, 10], [50, 50, 60, 60]], [0.9, 0.3])]
    [row] = detector.evaluate(photos, dets, n_boot=50)
    assert (row["model"], row["tp"], row["fp"], row["fn"]) == ("m", 2, 2, 1)
    assert row["recall"] == pytest.approx(2 / 3)
    assert row["precision"] == pytest.approx(2 / 4)
    assert row["duplicate_rate"] == pytest.approx(1 / 4)
    assert row["count_mae"] == pytest.approx(0.5)      # a: 2 vs 2, b: 2 vs 1
    assert row["recall_open-fridge"] == pytest.approx(1 / 2)
    assert row["recall_shelf-aisle"] == pytest.approx(1.0)


def test_detector_refuses_detections_on_a_different_image_size():
    photos = [_photo("a.jpg", [(0, 0, 10, 10)])]
    with pytest.raises(ValueError, match="size"):
        detector.evaluate(photos, [_dets("m", "a.jpg", [], [], W=2000, H=1000)], n_boot=10)


def test_detector_refuses_a_model_missing_a_labeled_photo():
    photos = [_photo("a.jpg", [(0, 0, 10, 10)]), _photo("b.jpg", [])]
    with pytest.raises(ValueError, match="b.jpg"):
        detector.evaluate(photos, [_dets("m", "a.jpg", [], [])], n_boot=10)


# --- bootstrap ---------------------------------------------------------------

def test_bootstrap_is_deterministic_and_brackets_the_estimate():
    items = list(range(20))
    stat = lambda xs: sum(xs) / len(xs)
    lo, hi = bootstrap_ci(items, stat, n=200, seed=0)
    assert (lo, hi) == bootstrap_ci(items, stat, n=200, seed=0)
    assert lo < stat(items) < hi


# --- share of shelf ----------------------------------------------------------

CLASSES = """class_name,brand,pack_type,sku,is_ours,source
Kix-Max_canned_blue,Kix-Max,canned,blue,1,invoice
Kix-Max_glass_blue,Kix-Max,glass,blue,1,invoice
TorshX_canned_red,TorshX,canned,red,1,invoice
Tommy_canned_x,Tommy,canned,x,1,invoice
COMPETITOR_canned,COMPETITOR,canned,,0,manual
COMPETITOR_glass,COMPETITOR,glass,,0,manual
COMPETITOR_other,COMPETITOR,other,,0,manual
Icy-Monkey_canned,Icy-Monkey,canned,,0,manual
Coca-Cola_canned,Coca-Cola,canned,,0,manual
out_of_scope,out_of_scope,,,0,manual
"""
REPORTING = """categories:
  canned_drinks: {pack_types: [canned]}
  glass_drinks: {pack_types: [glass]}
"""


def _taxonomy(tmp_path, competitors, brands=("Kix-Max", "TorshX"), detail="brand"):
    c = _write(tmp_path, "classes.csv", CLASSES)
    r = _write(tmp_path, "reporting.yaml", REPORTING)
    s = _write(tmp_path, "scope.yaml",
               f"brands: {list(brands)}\ncategories: [canned_drinks, glass_drinks]\n"
               f"detail: {detail}\ncompetitors: {list(competitors)}\n")
    return share.Taxonomy.load(c, r, s)


def _labeled(file_name, labels, scene="open-fridge"):
    return ls_export.Photo(task_id=1, inner_id=1, photo_id=file_name, file_name=file_name,
                           width=10, height=10, scene=scene, capture=[], photo_issue=[],
                           boxes=[ls_export.Box((0, 0, 1, 1), l) for l in labels], warnings=[])


def test_labels_resolve_to_brand_pack_and_role(tmp_path):
    tax = _taxonomy(tmp_path, ["Icy-Monkey"])
    assert tax.resolve("Kix-Max_canned") == ("Kix-Max", "canned", "ours")          # brand level
    assert tax.resolve("Kix-Max_canned_blue") == ("Kix-Max", "canned", "ours")     # sku level
    assert tax.resolve("Tommy_canned_x") == ("Tommy", "canned", "ours_unreported")
    assert tax.resolve("Icy-Monkey_canned") == ("Icy-Monkey", "canned", "targeted")
    assert tax.resolve("Coca-Cola_canned") == ("Coca-Cola", "canned", "untargeted")
    assert tax.resolve("COMPETITOR_canned") == ("COMPETITOR", "canned", "untargeted")
    assert tax.resolve("product") is None
    assert tax.resolve("out_of_scope") is None


def test_an_unknown_label_stops_the_evaluation(tmp_path):
    # Silently counting a typo as `product` would drop it from the share.
    with pytest.raises(ValueError, match="Pepsi_canned"):
        _taxonomy(tmp_path, []).resolve("Pepsi_canned")


def test_share_is_ours_over_ours_plus_targeted_per_category(tmp_path):
    tax = _taxonomy(tmp_path, ["Icy-Monkey"])
    photos = [_labeled("a", ["Kix-Max_canned"] * 3 + ["Icy-Monkey_canned"] + ["Coca-Cola_canned"] * 5
                       + ["COMPETITOR_canned", "product", "Tommy_canned_x"]),
              _labeled("b", ["TorshX_canned", "Icy-Monkey_canned", "Icy-Monkey_canned", "Kix-Max_glass"]),
              _labeled("c", ["product"] * 4)]
    rep = share.evaluate(photos, tax, n_boot=50)
    cans = rep.categories["canned_drinks"]
    assert (cans.ours, cans.targeted, cans.untargeted, cans.ours_unreported) == (4, 3, 6, 1)
    assert cans.share == pytest.approx(4 / 7)
    assert cans.photos == 2                       # "c" has nothing in the category: left out
    assert cans.per_brand == {"Kix-Max": 3, "TorshX": 1, "Icy-Monkey": 3}
    glass = rep.categories["glass_drinks"]
    assert (glass.ours, glass.targeted, glass.share, glass.photos) == (1, 0, 1.0, 1)


def test_adding_a_targeted_competitor_is_a_config_edit_that_changes_the_share(tmp_path):
    """The BI manager says "Coca-Cola is a competitor now": scope.yaml gains one
    entry (classes.csv already has the row); boxes already labeled Coca-Cola
    move from untargeted to targeted, and no code changes."""
    photos = [_labeled("a", ["Kix-Max_canned"] * 2 + ["Icy-Monkey_canned"] + ["Coca-Cola_canned"] * 2)]
    before = share.evaluate(photos, _taxonomy(tmp_path, ["Icy-Monkey"]), n_boot=10)
    after = share.evaluate(photos, _taxonomy(tmp_path, ["Icy-Monkey", "Coca-Cola"]), n_boot=10)
    assert before.categories["canned_drinks"].share == pytest.approx(2 / 3)
    assert after.categories["canned_drinks"].share == pytest.approx(2 / 5)


def test_reporting_a_further_brand_of_ours_is_a_config_edit(tmp_path):
    photos = [_labeled("a", ["Kix-Max_canned", "Tommy_canned_x", "Icy-Monkey_canned"])]
    before = share.evaluate(photos, _taxonomy(tmp_path, ["Icy-Monkey"]), n_boot=10)
    after = share.evaluate(photos, _taxonomy(tmp_path, ["Icy-Monkey"],
                                             brands=("Kix-Max", "TorshX", "Tommy")), n_boot=10)
    assert before.categories["canned_drinks"].share == pytest.approx(1 / 2)
    assert after.categories["canned_drinks"].share == pytest.approx(2 / 3)


def test_the_share_denominator_is_a_scope_setting(tmp_path):
    """`share_against: all` gives ours / every named can, the generic metric;
    `targeted` (default) gives ours / (ours + tracked rivals). Both are always
    reported, so switching the headline is a config edit, not a relabel."""
    photos = [_labeled("a", ["Kix-Max_canned"] * 2 + ["Tommy_canned_x", "Icy-Monkey_canned",
                                                       "COMPETITOR_canned", "product"])]
    tax = _taxonomy(tmp_path, ["Icy-Monkey"])
    cans = share.evaluate(photos, tax, n_boot=10).categories["canned_drinks"]
    assert cans.share_targeted == pytest.approx(2 / 3)
    assert cans.share_all == pytest.approx(2 / 5)       # product boxes are not counted
    assert cans.share == cans.share_targeted
    s = tmp_path / "scope.yaml"
    s.write_text(s.read_text(encoding="utf-8") + "share_against: all\n", encoding="utf-8")
    tax_all = share.Taxonomy.load(tmp_path / "classes.csv", tmp_path / "reporting.yaml", s)
    assert share.evaluate(photos, tax_all, n_boot=10).categories["canned_drinks"].share == pytest.approx(2 / 5)


def test_an_unknown_share_denominator_is_rejected(tmp_path):
    _taxonomy(tmp_path, [])
    s = tmp_path / "scope.yaml"
    s.write_text(s.read_text(encoding="utf-8") + "share_against: everyone\n", encoding="utf-8")
    with pytest.raises(ValueError, match="share_against"):
        share.Taxonomy.load(tmp_path / "classes.csv", tmp_path / "reporting.yaml", s)


def test_the_shipped_configs_resolve_every_label_in_the_live_labeling_config():
    """Every label a labeler can pick today must be understood by the evaluator."""
    from xml.dom import minidom

    from face_counter.utils.config import (DEFAULT_CLASSES, DEFAULT_LABEL_STUDIO_DIR,
                                           DEFAULT_REPORTING, DEFAULT_SCOPE)
    cfg = DEFAULT_LABEL_STUDIO_DIR / "labeling_config_scope_fa.xml"
    if not cfg.exists():
        pytest.skip("live labeling config not on this machine")
    tax = share.Taxonomy.load(DEFAULT_CLASSES, DEFAULT_REPORTING, DEFAULT_SCOPE)
    for e in minidom.parse(str(cfg)).getElementsByTagName("Label"):
        tax.resolve(e.getAttribute("alias") or e.getAttribute("value"))   # raises if unknown


# --- cli ---------------------------------------------------------------------

def test_cli_writes_detector_and_share_tables_and_a_summary(tmp_path):
    from face_counter.evaluation import cli
    export = [_task(1, 1, "a.jpg", [_ann([_box(0, 0, 10, 10, "Kix-Max_canned", W=100, H=200),
                                         _box(20, 0, 10, 10, "Icy-Monkey_canned", W=100, H=200),
                                         _choice("scene", "open-fridge")])])]
    labels = _write(tmp_path, "export.json", export)
    dets = _write(tmp_path, "d.jsonl", json.dumps(_dets("m", "a.jpg", [[0, 0, 10, 10]], [0.9], W=100, H=200)) + "\n")
    _taxonomy(tmp_path, ["Icy-Monkey"])
    out = tmp_path / "out"
    cli.main(["--labels", str(labels), "--detections", str(dets), "--out-dir", str(out),
              "--classes", str(tmp_path / "classes.csv"), "--reporting", str(tmp_path / "reporting.yaml"),
              "--scope", str(tmp_path / "scope.yaml"), "--n-boot", "20"])
    assert (out / "detector.csv").read_text(encoding="utf-8").splitlines()[0].startswith("model,")
    assert "canned_drinks" in (out / "share.csv").read_text(encoding="utf-8")
    assert (out / "share_per_photo.csv").exists()
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "Icy-Monkey" in summary and "not our share of all" in summary
    assert json.loads((out / "run_args.json").read_text(encoding="utf-8"))["labels"] == str(labels)
    # The exact label file is recorded, so a number can be traced to a frozen export.
    import hashlib
    assert json.loads((out / "run_args.json").read_text(encoding="utf-8"))["labels_sha256"] == \
        hashlib.sha256(labels.read_bytes()).hexdigest()
    assert hashlib.sha256(labels.read_bytes()).hexdigest()[:12] in summary
