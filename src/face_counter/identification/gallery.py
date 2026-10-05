"""The reference gallery: our own brand+pack packshots plus tracked
competitors (PILOT.md step 4), filtered to the active scope.

Sources, both config-only (``configs/Product/`` is gitignored real product
photography; these functions, not the folders, are the tracked artifact --
same split as ``scripts/make_gallery_folders.py``):

- ``configs/Product/from_invoice/``: our own packshots, named
  ``<class_name>`` or ``<class_name>_<n>`` (``scripts/build_classes.py``).
  Rolled up to brand level today (``<brand>_<pack_type>``), matching
  ``scope.yaml``'s ``detail: brand``. SKU-level matching is a smaller filter
  here later: keep the matched ``class_name`` instead of rolling it up, and
  point the matcher at scope.yaml's ``detail`` the way ``taxonomy.py`` already
  does for ground-truth labels.
- ``configs/Product/competitors/<brand>_<pack_type>/``: tracked-competitor
  packshots, already named by folder (``make_gallery_folders.py`` creates and
  names them from the same scope). A missing or empty folder yields no images
  for that label, same "cannot count it" outcome the matcher would hit at
  inference -- not an error here.

Raw marketing folders (``configs/Product/Kixmax/``, ``Torsh-X/``) are not
read: they don't follow the ``class_name`` filename convention this matches
images against, and their photos are composited mockups, not the plain
packshots the invoice folder holds.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from face_counter.utils.config import (DEFAULT_CLASSES, DEFAULT_REPORTING, DEFAULT_SCOPE,
                                       PROJECT_ROOT)
from face_counter.utils.taxonomy import Scope, load_reporting, load_scope, targeted_label_names

DEFAULT_INVOICE_DIR = PROJECT_ROOT / "configs" / "Product" / "from_invoice"
DEFAULT_COMPETITORS_DIR = PROJECT_ROOT / "configs" / "Product" / "competitors"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".avif", ".heic", ".gif"}
# A second (or third, ...) reference image for the same class: "<stem>_2.png".
_TRAILING_INDEX = re.compile(r"_\d+$")


@dataclass(frozen=True)
class GalleryImage:
    path: Path
    label: str    # <brand>_<pack_type>: brand-level today, see module docstring
    ours: bool


def _is_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES


def _our_images(invoice_dir: Path, rows: list[dict], scope: Scope) -> list[GalleryImage]:
    by_class = {r["class_name"].strip(): r for r in rows}
    out = []
    if not invoice_dir.is_dir():
        return out
    for p in sorted(invoice_dir.iterdir()):
        if not _is_image(p):
            continue
        row = by_class.get(p.stem) or by_class.get(_TRAILING_INDEX.sub("", p.stem))
        if row is None or str(row.get("is_ours", "")).strip() != "1":
            continue
        brand, pack = row["brand"].strip(), (row["pack_type"] or "").strip()
        if brand not in scope.brands or pack not in scope.pack_types:
            continue
        out.append(GalleryImage(path=p, label=f"{brand}_{pack}", ours=True))
    return out


def _competitor_images(competitors_dir: Path, rows: list[dict], scope: Scope) -> list[GalleryImage]:
    out = []
    for label in targeted_label_names(rows, scope):
        folder = competitors_dir / label
        if not folder.is_dir():
            continue
        for p in sorted(folder.iterdir()):
            if _is_image(p):
                out.append(GalleryImage(path=p, label=label, ours=False))
    return out


def build(invoice_dir: Path = DEFAULT_INVOICE_DIR, competitors_dir: Path = DEFAULT_COMPETITORS_DIR,
         classes_path: Path = DEFAULT_CLASSES, reporting_path: Path = DEFAULT_REPORTING,
         scope_path: Path = DEFAULT_SCOPE) -> list[GalleryImage]:
    """Every gallery image in the active scope: our brands (brand-level) then
    tracked competitors, each sorted by path for a deterministic order."""
    with open(classes_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    reporting = load_reporting(reporting_path)
    scope = load_scope(scope_path, reporting)
    return (_our_images(invoice_dir, rows, scope)
            + _competitor_images(competitors_dir, rows, scope))
