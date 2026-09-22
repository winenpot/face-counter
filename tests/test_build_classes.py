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
