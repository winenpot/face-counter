"""Class list <-> reporting categories: the rules that keep labels valid as the business evolves."""
import csv

import pytest

from face_counter.utils import taxonomy
from face_counter.utils.config import DEFAULT_CLASSES, DEFAULT_REPORTING


def _row(name, brand, pack, is_ours, source="manual", sku=""):
    return {"class_name": name, "brand": brand, "pack_type": pack, "sku": sku,
            "is_ours": str(is_ours), "source": source}


def _reporting(tmp_path, text):
    p = tmp_path / "reporting.yaml"
    p.write_text(text, encoding="utf-8")
    return taxonomy.load_reporting(p)


REPORTING = """
categories:
  canned_drinks: {pack_types: [canned]}
  oils: {pack_types: [oil]}
"""

GOOD = [
    _row("Kix-Max_canned_x", "Kix-Max", "canned", 1, "invoice", "x"),
    _row("Kix_gum_y", "Kix", "gum", 1, "invoice", "y"),
    _row("COMPETITOR_canned", "COMPETITOR", "canned", 0),
    _row("COMPETITOR_gum", "COMPETITOR", "gum", 0),
    _row("COMPETITOR_oil", "COMPETITOR", "oil", 0),
    _row("COMPETITOR_other", "COMPETITOR", "other", 0),
    _row("out_of_scope", "out_of_scope", "", 0),
]


def test_category_of_maps_pack_type_and_returns_none_outside_reporting(tmp_path):
    rep = _reporting(tmp_path, REPORTING)
    assert taxonomy.category_of("canned", rep) == "canned_drinks"
    assert taxonomy.category_of("gum", rep) is None


def test_a_pack_type_in_two_categories_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="canned"):
        _reporting(tmp_path, "categories:\n  a: {pack_types: [canned]}\n  b: {pack_types: [canned]}\n")


def test_consistent_class_list_has_no_problems(tmp_path):
    assert taxonomy.problems(GOOD, _reporting(tmp_path, REPORTING)) == []


def test_reporting_pack_type_without_competitor_class_is_a_problem(tmp_path):
    rows = [r for r in GOOD if r["class_name"] != "COMPETITOR_oil"]
    assert any("COMPETITOR_oil" in p for p in taxonomy.problems(rows, _reporting(tmp_path, REPORTING)))


def test_our_pack_type_without_competitor_class_is_a_problem(tmp_path):
    # A future category is almost always built around something we sell; the
    # competitor vocabulary must already distinguish it, or old labels need redoing.
    rows = [r for r in GOOD if r["class_name"] != "COMPETITOR_gum"]
    assert any("COMPETITOR_gum" in p for p in taxonomy.problems(rows, _reporting(tmp_path, REPORTING)))


def test_duplicate_and_malformed_rows_are_problems(tmp_path):
    rep = _reporting(tmp_path, REPORTING)
    rows = GOOD + [GOOD[0]]
    assert any("duplicate" in p for p in taxonomy.problems(rows, rep))
    bad = [dict(r) for r in GOOD]
    bad[2]["is_ours"] = "1"  # a competitor marked ours would inflate our share
    assert any("COMPETITOR_canned" in p for p in taxonomy.problems(bad, rep))
    bad = [dict(r) for r in GOOD]
    bad[0]["pack_type"] = ""
    assert any("Kix-Max_canned_x" in p for p in taxonomy.problems(bad, rep))
    bad = [dict(r) for r in GOOD]
    bad[0]["source"] = "typo"
    assert any("source" in p for p in taxonomy.problems(bad, rep))


def test_shipped_class_list_is_consistent_with_shipped_reporting():
    with open(DEFAULT_CLASSES, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rep = taxonomy.load_reporting(DEFAULT_REPORTING)
    assert taxonomy.problems(rows, rep) == []
    # The four categories the business decided on 2026-09-27.
    assert set(rep) == {"canned_drinks", "glass_drinks", "oils", "dressings"}
    assert taxonomy.category_of("glass", rep) == "glass_drinks"
    # "glass drinks" means glass bottles only; plastic bottles are not in it.
    assert taxonomy.category_of("plastic-bottle", rep) is None
