"""Tests for scripts/build_classes.py's parsing heuristics.

No .xlsm fixture (the real source is a company-confidential invoice and is
gitignored) -- these test the string-level functions directly with inline
sample descriptions shaped like the real invoice's Product Description column.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_classes as bc  # noqa: E402


def test_wholesale_packaging_is_stripped_not_a_shelf_difference():
    a = bc.strip_wholesale_packaging('"Kix max" sour ganules (15g) (strawberry) Card board')
    b = bc.strip_wholesale_packaging('"Kix max" sour ganules (15g) (strawberry) Middle Box')
    assert a == b  # same shelf-visible product, different B2B case type


def test_can_vs_glass_are_different_categories():
    can = bc.guess_category('"Kix max" Blue berry Carbonated Soft Drink (250ml) Can')
    glass = bc.guess_category('"Kix max" Blue berry Carbonated Soft Drink (250ml) Glass')
    assert can == "canned"
    assert glass == "glass"
    assert can != glass


def test_brand_is_recognised_and_canonicalised():
    guessed = bc.guess_brand('"Kix max" Blue berry Carbonated Soft Drink (250ml) Can')
    assert guessed is not None
    canon, raw = guessed
    assert canon == "Kix-Max"
    assert raw.lower() == "kix max"


def test_unknown_brand_returns_none_rather_than_guessing():
    assert bc.guess_brand("Some Unlisted Thing (250ml)") is None


def test_flavor_order_does_not_create_duplicate_skus():
    # same two flavors, different word order in the source text
    a = bc.guess_sku('"TorshX" Sour Candy (Moscow, Pattaya)', "TorshX")
    b = bc.guess_sku('"TorshX" Sour Candy (Pattaya, Moscow)', "TorshX")
    assert a == b


def test_drink_with_known_containers_expands_to_one_class_per_container():
    # TorshX soft-drink rows never say Can or Glass; both exist for every flavor.
    rows = bc.classes_for('"TorhX" Carbonated Soft Drink (Berlin) (250 ml)')
    assert [r["class_name"] for r in rows] == ["TorshX_canned_berlin", "TorshX_glass_berlin"]


def test_energy_drinks_are_cans_named_energy_drink():
    assert [r["class_name"] for r in bc.classes_for('"TorhX" Carbonated Energy drink (250 ml)')] \
        == ["TorshX_canned_energy-drink"]


def test_stated_container_wins_over_known_containers():
    rows = bc.classes_for('"Kix max" Blue berry Carbonated Soft Drink (250ml) Can')
    assert [r["class_name"] for r in rows] == ["Kix-Max_canned_blue-berry"]


def test_brands_we_no_longer_sell_are_not_imported():
    # Only brands in BRAND_CANON are ours; a discontinued brand is removed from
    # it, so an old invoice that still lists the brand adds nothing.
    assert set(bc.BRAND_CANON.values()) == {
        "Kix-Max", "TorshX", "My-Milk", "Picola", "Kix", "Biskett", "Tommy-Joy"}
    assert {brand for brand, _ in bc.DRINK_CONTAINERS} <= set(bc.BRAND_CANON.values())


def test_drink_with_unstated_unknown_container_fails_instead_of_guessing():
    import pytest

    with pytest.raises(bc.UnknownContainer):
        bc.classes_for('"Picola" Carbonated Soft Drink (Apple) (250 ml)')


def test_rows_carry_pack_type_and_invoice_source():
    (row,) = bc.classes_for('"Kix max" Blue berry Carbonated Soft Drink (250ml) Can')
    assert row["pack_type"] == "canned"
    assert row["source"] == "invoice"
    assert "category" not in row


def _write(path, rows):
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_merge_keeps_manual_rows_and_rows_missing_from_this_invoice():
    existing = [
        {"class_name": "COMPETITOR_oil", "brand": "COMPETITOR", "pack_type": "oil",
         "sku": "", "is_ours": "0", "source": "manual"},
        {"class_name": "Kix_gum_old", "brand": "Kix", "pack_type": "gum",
         "sku": "old", "is_ours": "1", "source": "invoice"},
    ]
    fresh = bc.classes_for('"Kix max" Blue berry Carbonated Soft Drink (250ml) Can')
    merged, report = bc.merge(existing, fresh, drop_missing=False)
    names = [r["class_name"] for r in merged]
    assert "COMPETITOR_oil" in names and "Kix_gum_old" in names
    assert "Kix-Max_canned_blue-berry" in names
    assert report["added"] == ["Kix-Max_canned_blue-berry"]
    assert report["kept_not_on_invoice"] == ["Kix_gum_old"]
    assert report["dropped"] == []


def test_merge_drop_missing_never_drops_manual_rows():
    existing = [
        {"class_name": "COMPETITOR_oil", "brand": "COMPETITOR", "pack_type": "oil",
         "sku": "", "is_ours": "0", "source": "manual"},
        {"class_name": "Kix_gum_old", "brand": "Kix", "pack_type": "gum",
         "sku": "old", "is_ours": "1", "source": "invoice"},
    ]
    merged, report = bc.merge(existing, [], drop_missing=True)
    assert [r["class_name"] for r in merged] == ["COMPETITOR_oil"]
    assert report["dropped"] == ["Kix_gum_old"]


def test_merge_manual_row_wins_over_invoice_row_with_same_name():
    existing = [{"class_name": "Kix-Max_canned_blue-berry", "brand": "Kix-Max",
                 "pack_type": "canned", "sku": "blue-berry", "is_ours": "1",
                 "source": "manual"}]
    fresh = bc.classes_for('"Kix max" Blue berry Carbonated Soft Drink (250ml) Can')
    merged, _ = bc.merge(existing, fresh, drop_missing=True)
    assert merged == existing


def test_legacy_file_without_source_or_pack_type_is_read_as_invoice_rows(tmp_path):
    p = tmp_path / "classes.csv"
    _write(p, [{"class_name": "Kix_gum_mint", "brand": "Kix", "category": "gum",
                "sku": "mint", "is_ours": "1"}])
    (row,) = bc.read_existing(p)
    assert row["pack_type"] == "gum"
    assert row["source"] == "invoice"
    assert "category" not in row


def test_write_is_atomic_and_keeps_column_order(tmp_path):
    p = tmp_path / "classes.csv"
    bc.write_classes(p, bc.classes_for('"TorhX" Carbonated Energy drink (250 ml)'))
    header = p.read_text(encoding="utf-8").splitlines()[0]
    assert header == "class_name,brand,pack_type,sku,is_ours,source"
    assert not list(tmp_path.glob("*.tmp"))


def test_build_classes_deduplicates_wholesale_variants(tmp_path, monkeypatch):
    # Same product, 3 wholesale packagings -> exactly 1 class.
    rows = [
        (None, None, None, None, None, None,
         '"Kix max" sour ganules (15g) (strawberry) Card board'),
        (None, None, None, None, None, None,
         '"Kix max" sour ganules (15g) (strawberry) Middle Box'),
        (None, None, None, None, None, None,
         '"Kix max" sour ganules (15g) (strawberry) Dispenser Box'),
    ]
    monkeypatch.setattr(bc, "load_descriptions", lambda path: [r[6] for r in rows])
    out = bc.build_classes(Path("unused.xlsm"))
    assert len(out) == 1
    assert out[0]["brand"] == "Kix-Max"
    assert out[0]["is_ours"] == 1


def test_invoice_listing_both_containers_twice_still_yields_one_class_each(monkeypatch):
    # The real invoice repeats each TorshX flavor row; it must not duplicate classes.
    descs = ['"TorhX" Carbonated Soft Drink (Paris) (250 ml)',
             '"TorhX"Carbonated Soft Drink (Paris) (250ml)']
    monkeypatch.setattr(bc, "load_descriptions", lambda path: descs)
    names = [r["class_name"] for r in bc.build_classes(Path("unused.xlsm"))]
    assert names == ["TorshX_canned_paris", "TorshX_glass_paris"]
