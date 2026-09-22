"""Extract the per-product images embedded in the proforma invoice's
"Image" column and save them next to the class they belong to.

Excel embeds each picture as a floating shape anchored to a (row, col), not
as real cell content -- openpyxl's normal cell reading cannot see them. This
walks the underlying OOXML (drawing XML -> row anchor, drawing rels -> media
file) to recover which image belongs to which invoice row, then reuses
build_classes.py's own parsing so each image lands under the same
brand/category/sku the class list already uses.

The source .xlsm is never read for anything but the Image and Product
Description columns -- no pricing, no customer data. Output images (product
photos only) go to configs/Product/from_invoice/, which is gitignored like
the rest of configs/Product/.

Usage:
    uv run python scripts/extract_invoice_packshots.py \\
        "configs/050217- Proforma,Invoice,Packing.xlsm"
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_classes as bc  # noqa: E402

NS_XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

SHEET_XML = "xl/worksheets/sheet3.xml"  # "Proforma EN" (see xl/workbook.xml)
SHEET_RELS = "xl/worksheets/_rels/sheet3.xml.rels"
DRAWING_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def _drawing_path(z: zipfile.ZipFile) -> str:
    rels = ET.fromstring(z.read(SHEET_RELS))
    for rel in rels.findall(NS_REL + "Relationship"):
        if rel.get("Type") == DRAWING_REL_TYPE:
            # Target is relative to xl/worksheets/, so ../drawings/x.xml -> xl/drawings/x.xml
            return "xl/" + rel.get("Target").split("../", 1)[-1]
    raise SystemExit(f"no drawing relationship found for {SHEET_XML}")


def row_to_image(z: zipfile.ZipFile) -> dict[int, bytes]:
    """1-indexed spreadsheet row -> raw image bytes, for the first anchored
    picture on that row (a product's Image cell has exactly one)."""
    drawing_path = _drawing_path(z)
    drawing_dir = str(Path(drawing_path).parent)
    rels_path = f"{drawing_dir}/_rels/{Path(drawing_path).name}.rels"

    rid_to_target = {}
    rels = ET.fromstring(z.read(rels_path))
    for rel in rels.findall(NS_REL + "Relationship"):
        if rel.get("Type") == IMAGE_REL_TYPE:
            target = rel.get("Target")  # e.g. ../media/image42.jpeg
            rid_to_target[rel.get("Id")] = f"xl/{target.split('../', 1)[-1]}"

    out: dict[int, bytes] = {}
    tree = ET.fromstring(z.read(drawing_path))
    for anchor in tree.findall(NS_XDR + "twoCellAnchor"):
        pic = anchor.find(NS_XDR + "pic")
        if pic is None:
            continue  # shape/text box, not a picture
        frm = anchor.find(NS_XDR + "from")
        row0 = int(frm.find(NS_XDR + "row").text)  # 0-indexed
        blip = pic.find(f"{NS_XDR}blipFill/{NS_A}blip")
        rid = blip.get(NS_R + "embed") if blip is not None else None
        if not rid or rid not in rid_to_target:
            continue
        row1 = row0 + 1  # openpyxl-style 1-indexed row, matches build_classes' iter_rows
        if row1 not in out:  # first picture anchored to the row wins
            out[row1] = z.read(rid_to_target[rid])
    return out


def guess_ext(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    return ".bin"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <path to proforma .xlsm>")
    xlsm_path = Path(sys.argv[1])

    with zipfile.ZipFile(xlsm_path) as z:
        images_by_row = row_to_image(z)

    # Re-walk the same rows build_classes.py reads, so each image lines up
    # with the exact class_name already computed for that row.
    import openpyxl
    wb = openpyxl.load_workbook(xlsm_path, data_only=True, read_only=True)
    ws = wb["Proforma EN"]

    out_dir = Path(__file__).resolve().parents[1] / "configs" / "Product" / "from_invoice"
    out_dir.mkdir(parents=True, exist_ok=True)

    saved, skipped_no_image, skipped_no_brand = 0, 0, 0
    seen_classes: set[str] = set()
    for row_idx, row in enumerate(ws.iter_rows(min_row=17, values_only=True), start=17):
        desc = row[6] if len(row) > 6 else None
        if not desc or not isinstance(desc, str):
            continue
        desc = " ".join(desc.split())
        if not desc or desc.strip().upper().startswith("TOTAL"):
            continue

        clean = bc.strip_wholesale_packaging(desc)
        guessed = bc.guess_brand(clean)
        if not guessed:
            skipped_no_brand += 1
            continue
        brand, brand_raw = guessed
        category = bc.guess_category(clean)
        sku = bc.guess_sku(clean, brand_raw)
        class_name = f"{brand}_{category}_{sku}"

        data = images_by_row.get(row_idx)
        if not data:
            skipped_no_image += 1
            continue

        # Multiple invoice rows collapse to one class (wholesale packaging
        # variants) -- keep the first image found per class, number extras.
        n = sum(1 for c in seen_classes if c == class_name)
        suffix = "" if n == 0 else f"_{n + 1}"
        seen_classes.add(class_name)
        ext = guess_ext(data)
        (out_dir / f"{class_name}{suffix}{ext}").write_bytes(data)
        saved += 1

    print(f"saved {saved} images -> {out_dir}")
    print(f"skipped {skipped_no_image} rows with no anchored image, "
          f"{skipped_no_brand} rows with no recognised brand")


if __name__ == "__main__":
    main()
