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


# --- scope: the active pilot, a filter over the full taxonomy -----------------

SCOPE_ROWS = [
    _row("Kix-Max_canned_x", "Kix-Max", "canned", 1, "invoice", "x"),
    _row("Kix-Max_gum_y", "Kix-Max", "gum", 1, "invoice", "y"),
    _row("TorshX_glass_z", "TorshX", "glass", 1, "invoice", "z"),
    _row("Bomb_canned_e", "Bomb", "canned", 1, "invoice", "e"),
    _row("COMPETITOR_canned", "COMPETITOR", "canned", 0),
    _row("COMPETITOR_glass", "COMPETITOR", "glass", 0),
    _row("COMPETITOR_gum", "COMPETITOR", "gum", 0),
    _row("COMPETITOR_other", "COMPETITOR", "other", 0),
    _row("out_of_scope", "out_of_scope", "", 0),
]
SCOPE_REPORTING = """
categories:
  canned_drinks: {pack_types: [canned]}
  glass_drinks: {pack_types: [glass]}
  oils: {pack_types: [oil]}
"""


def _scope(tmp_path, text):
    p = tmp_path / "scope.yaml"
    p.write_text(text, encoding="utf-8")
    return taxonomy.load_scope(p, _reporting(tmp_path, SCOPE_REPORTING))


def test_scope_labels_every_product_of_a_scoped_pack_type_even_other_brands(tmp_path):
    # A Bomb can is a can: calling it a competitor, or leaving it out, would make
    # the denominator wrong. Brand scope limits reporting, never what gets named.
    scope = _scope(tmp_path, "brands: [Kix-Max, TorshX]\ncategories: [canned_drinks, glass_drinks]\n")
    names = taxonomy.scoped_label_names(SCOPE_ROWS, scope)
    assert names == ["Bomb_canned_e", "Kix-Max_canned_x", "TorshX_glass_z",
                     "COMPETITOR_canned", "COMPETITOR_glass", "product"]


def test_scope_reports_only_its_brands(tmp_path):
    scope = _scope(tmp_path, "brands: [Kix-Max, TorshX]\ncategories: [canned_drinks, glass_drinks]\n")
    assert scope.brands == ["Kix-Max", "TorshX"]
    assert scope.pack_types == ["canned", "glass"]


def test_scope_with_unknown_category_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="dressings"):
        _scope(tmp_path, "brands: [Kix-Max]\ncategories: [dressings]\n")


def test_shipped_scope_is_the_two_brand_drinks_pilot():
    from face_counter.utils.config import DEFAULT_SCOPE

    scope = taxonomy.load_scope(DEFAULT_SCOPE, taxonomy.load_reporting(DEFAULT_REPORTING))
    assert scope.brands == ["Kix-Max", "TorshX"]
    assert scope.categories == ["canned_drinks", "glass_drinks"]
    with open(DEFAULT_CLASSES, newline="", encoding="utf-8") as f:
        names = taxonomy.scoped_label_names(list(csv.DictReader(f)), scope)
    assert "COMPETITOR_canned" in names and "COMPETITOR_glass" in names
    assert "product" in names
    assert not any("_gum_" in n or "_sour-candy_" in n for n in names)


def test_label_prep_scope_level_emits_the_scoped_label_set(tmp_path):
    from face_counter.label_studio import prepare_label_studio as pls

    classes = tmp_path / "classes.csv"
    with open(classes, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(SCOPE_ROWS[0]))
        w.writeheader()
        w.writerows(SCOPE_ROWS)
    (tmp_path / "reporting.yaml").write_text(SCOPE_REPORTING, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(
        "brands: [Kix-Max, TorshX]\ncategories: [canned_drinks]\n", encoding="utf-8")
    got = pls.read_classes(classes, "scope", scope=tmp_path / "scope.yaml",
                           reporting=tmp_path / "reporting.yaml")
    assert [c["name"] for c in got] == ["Bomb_canned_e", "Kix-Max_canned_x",
                                        "COMPETITOR_canned", "product"]


def test_label_prep_geometry_level_is_the_single_product_label(tmp_path):
    from face_counter.label_studio import prepare_label_studio as pls
    from face_counter.training import detector_bakeoff as bk

    classes = tmp_path / "classes.csv"
    with open(classes, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(SCOPE_ROWS[0]))
        w.writeheader()
        w.writerows(SCOPE_ROWS)
    got = pls.read_classes(classes, "geometry")
    # Must equal the label the bake-off writes into its predictions, or they won't load.
    assert [c["name"] for c in got] == [bk.GEOMETRY_LABEL] == ["product"]


# --- scope detail: the pilot names brand + pack type, not flavours -----------

def test_brand_detail_scope_names_brand_and_pack_type_not_skus(tmp_path):
    scope = _scope(tmp_path, "brands: [Kix-Max, TorshX]\ncategories: [canned_drinks, glass_drinks]\n"
                             "detail: brand\n")
    names = taxonomy.scoped_label_names(SCOPE_ROWS, scope)
    # Brand_packtype is the prefix of every SKU class name (Brand_packtype_sku), so a
    # later SKU pass refines these labels rather than contradicting them.
    assert names == ["Bomb_canned", "Kix-Max_canned", "TorshX_glass",
                     "COMPETITOR_canned", "COMPETITOR_glass", "product"]


def test_scope_detail_defaults_to_sku(tmp_path):
    scope = _scope(tmp_path, "brands: [Kix-Max]\ncategories: [canned_drinks]\n")
    assert scope.detail == "sku"


def test_unknown_scope_detail_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="flavour"):
        _scope(tmp_path, "brands: [Kix-Max]\ncategories: [canned_drinks]\ndetail: flavour\n")


def test_shipped_pilot_labels_are_the_eight_brand_level_labels():
    from face_counter.utils.config import DEFAULT_SCOPE

    scope = taxonomy.load_scope(DEFAULT_SCOPE, taxonomy.load_reporting(DEFAULT_REPORTING))
    with open(DEFAULT_CLASSES, newline="", encoding="utf-8") as f:
        names = taxonomy.scoped_label_names(list(csv.DictReader(f)), scope)
    assert names == ["Bomb_canned", "Kix-Max_canned", "Kix-Max_glass", "TorshX_canned",
                     "TorshX_glass", "COMPETITOR_canned", "COMPETITOR_glass", "product"]
