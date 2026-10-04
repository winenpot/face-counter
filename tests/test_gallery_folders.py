"""scripts/make_gallery_folders.py: the gallery folders follow config, not code.

The matcher looks for a folder per `<Brand>_<pack_type>` the scope tracks, so a
folder name this script would not produce is a rival the matcher never names.
The point of these tests is the extensibility promise in docs/PILOT.md step 8:
adding a tracked competitor is a config edit, and a new folder falls out of it.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_gallery_folders as mgf  # noqa: E402

REPORTING = """
categories:
  canned_drinks: {pack_types: [canned]}
  glass_drinks: {pack_types: [glass]}
"""

CLASSES = """class_name,brand,pack_type,sku,is_ours,source
Kix-Max_canned_x,Kix-Max,canned,x,1,invoice
COMPETITOR_canned,COMPETITOR,canned,,0,manual
COMPETITOR_glass,COMPETITOR,glass,,0,manual
Icy-Monkey_canned,Icy-Monkey,canned,,0,manual
Icy-Monkey_glass,Icy-Monkey,glass,,0,manual
Genius_glass,Genius,glass,,0,manual
"""

SCOPE = """
brands: [Kix-Max]
categories: [canned_drinks, glass_drinks]
competitors: [Icy-Monkey]
share_against: targeted
detail: brand
"""


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "reporting.yaml").write_text(REPORTING, encoding="utf-8")
    (tmp_path / "classes.csv").write_text(CLASSES, encoding="utf-8")
    (tmp_path / "scope.yaml").write_text(SCOPE, encoding="utf-8")
    return tmp_path


def _labels(cfg, scope_text=None):
    if scope_text is not None:
        (cfg / "scope.yaml").write_text(scope_text, encoding="utf-8")
    return mgf.gallery_labels(cfg / "scope.yaml", cfg / "classes.csv", cfg / "reporting.yaml")


def test_one_folder_per_tracked_competitor_pack_type(cfg):
    assert [row[0] for row in _labels(cfg)] == ["Icy-Monkey_canned", "Icy-Monkey_glass"]


def test_each_label_carries_its_reporting_category(cfg):
    assert {label: cat for label, _, _, cat in _labels(cfg)} == {
        "Icy-Monkey_canned": "canned_drinks",
        "Icy-Monkey_glass": "glass_drinks",
    }


def test_untracked_competitors_get_no_gallery(cfg):
    """Genius is a named competitor in classes.csv but not tracked by this scope:
    not ours and not tracked means not counted, so nothing has to name it."""
    assert all("Genius" not in label for label, *_ in _labels(cfg))


def test_our_own_brands_get_no_competitor_gallery(cfg):
    assert all("Kix-Max" not in label for label, *_ in _labels(cfg))


def test_adding_a_tracked_competitor_is_a_config_edit(cfg):
    """The extensibility test: one line in scope.yaml, one more folder, no code."""
    before = [row[0] for row in _labels(cfg)]
    after = [row[0] for row in _labels(cfg, SCOPE.replace("[Icy-Monkey]",
                                                          "[Icy-Monkey, Genius]"))]
    assert set(after) - set(before) == {"Genius_glass"}


def test_creates_a_folder_and_a_readme_per_label(cfg, tmp_path):
    gallery = tmp_path / "gallery"
    sys.argv = ["make_gallery_folders.py",
                "--gallery-dir", str(gallery),
                "--scope", str(cfg / "scope.yaml"),
                "--classes", str(cfg / "classes.csv"),
                "--reporting", str(cfg / "reporting.yaml")]
    assert mgf.main() == 0
    for label in ("Icy-Monkey_canned", "Icy-Monkey_glass"):
        readme = gallery / label / "README.md"
        assert readme.exists()
        text = readme.read_text(encoding="utf-8")
        assert label in text
        # The one rule that would silently invalidate every accuracy number.
        assert "frozen test set" in text


def test_check_mode_creates_nothing(cfg, tmp_path):
    gallery = tmp_path / "gallery-check"
    sys.argv = ["make_gallery_folders.py", "--check",
                "--gallery-dir", str(gallery),
                "--scope", str(cfg / "scope.yaml"),
                "--classes", str(cfg / "classes.csv"),
                "--reporting", str(cfg / "reporting.yaml")]
    assert mgf.main() == 0
    assert not gallery.exists()


def test_count_images_ignores_readme_and_counts_photos(tmp_path):
    folder = tmp_path / "Icy-Monkey_glass"
    folder.mkdir()
    (folder / "README.md").write_text("x", encoding="utf-8")
    assert mgf.count_images(folder) == 0
    (folder / "front.jpg").write_bytes(b"")
    (folder / "angle.PNG").write_bytes(b"")
    assert mgf.count_images(folder) == 2


def test_live_config_produces_the_ten_pilot_galleries():
    """Guards the real configs/: the pilot tracks 7 rivals over 10 pack types."""
    labels = [row[0] for row in mgf.gallery_labels()]
    assert len(labels) == 10
    assert "Icy-Monkey_canned" in labels and "Sunich-Cool_glass" in labels
