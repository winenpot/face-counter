"""Build configs/classes.csv from a sales/export proforma invoice.

The invoice lists many rows per product because of WHOLESALE packaging
variants (Middle Box vs Card board vs Dispenser Box, ...) -- B2B case
types, invisible on a shelf. Those collapse into one class. Retail-visible
differences (Can vs Glass, different flavors) stay separate classes.

The source .xlsm is never read for pricing or customer/buyer info -- only
the "Product Description" column. It is not committed to git (company
pricing + customer data); this script and its output (classes.csv,
containing only product/brand/flavor names) are.

Usage:
    uv run python scripts/build_classes.py configs/050217-\\ Proforma,Invoice,Packing.xlsm
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import openpyxl

# Wholesale case descriptors -- strip these, they're not a shelf-visible
# difference. Longest-first so "Dispenser Box" doesn't get cut short.
WHOLESALE_PACKAGING = [
    "Dispenser Box", "Middle Box", "Card board", "Pillow pack",
]

# Retail-visible container -> category. Order matters (checked in turn).
CONTAINER_CATEGORY = [
    (r"\bglass\b", "glass"),
    (r"\bcan\b", "canned"),
    (r"carbonated (soft drink|energy drink)", "canned"),  # can, unless "Glass" matched above first
]

BRAND_CANON = {
    "kix max": "Kix-Max",
    "kixmax": "Kix-Max",
    "torhx": "TorshX",
    "torshx": "TorshX",
    "my milk": "My-Milk",
    "picola": "Picola",
    "kix": "Kix",  # multi-vitamin straw / ice-pop sub-brand, distinct from Kix-Max
    "biskett": "Biskett",
    "tommy joy": "Tommy-Joy",
    "bomb": "Bomb",
}

FLAVOR_WORDS = re.compile(
    r"\b(Blue\s?berry|Sour\s?Cherry|Mix\s?[Bb]erry|Bubble\s?Gum|Passion\s?Fruit|"
    r"Strawberry|Limonad|Lemon|Lime|Pomegranate|Apple|Mango\s?passion\s?fruit|"
    r"Mohito|Pinacolada|Cherry|Chocolate|Coconut|Banana|Melon|Vanilla|Caramel|"
    r"Hazelnut|Grenadine|Raspberry|Green\s?Apple|Frosted\s?Mint|Forest\s?fruit(?:e|)s?|"
    r"Orange|Aloevera|Honey|Salty|Crunchy|Mint|"
    r"Moscow|Pattaya|Mexico|Tokyo|Berlin|Madrid|Paris)\b",
    re.IGNORECASE,
)


def load_descriptions(xlsm_path: Path, sheet: str = "Proforma EN") -> list[str]:
    wb = openpyxl.load_workbook(xlsm_path, data_only=True, read_only=True)
    ws = wb[sheet]
    out = []
    for row in ws.iter_rows(min_row=17, values_only=True):
        desc = row[6] if len(row) > 6 else None
        if not desc or not isinstance(desc, str):
            continue
        desc = " ".join(desc.split())
        if not desc or desc.strip().upper().startswith("TOTAL"):
            continue
        out.append(desc)
    return out


def strip_wholesale_packaging(desc: str) -> str:
    for kw in WHOLESALE_PACKAGING:
        desc = re.sub(re.escape(kw), "", desc, flags=re.IGNORECASE)
    return " ".join(desc.split())


def guess_brand(desc: str) -> tuple[str, str] | None:
    """Returns (canonical_brand, raw_text_as_it_appears) or None."""
    m = re.match(r'^"+([A-Za-z ]+?)"+', desc)
    raw = (m.group(1) if m else desc.split()[0]).strip()
    canon = BRAND_CANON.get(raw.lower())
    return (canon, raw) if canon else None


def guess_category(desc: str) -> str:
    low = desc.lower()
    for pattern, category in CONTAINER_CATEGORY:
        if re.search(pattern, low):
            return category
    if "chewing gum" in low:
        return "gum"
    if "ice-pop" in low:
        return "ice-pop"
    if "milk straw" in low or "magic milk" in low:
        return "milk-straw"
    if "sour candy" in low or "sour drajee" in low or "sour ganules" in low:
        return "sour-candy"
    if "biscuit" in low or "cookie" in low:
        return "biscuit"
    if "syrup" in low:
        return "syrup"
    if "peanut butter" in low or "spread" in low:
        return "spread"
    if "jelly powder" in low:
        return "jelly-powder"
    if "sauce" in low:
        return "sauce"
    if "gift box" in low or "party box" in low:
        return "gift-box"
    return "other"


def guess_sku(desc: str, brand_raw: str) -> str:
    flavors = [f.strip().lower().replace(" ", "-") for f in FLAVOR_WORDS.findall(desc)]
    flavors = sorted(set(flavors))  # alpha order: "A, B" and "B, A" collapse to one class
    if flavors:
        return flavors[0] if len(flavors) == 1 else "mix-" + "-".join(flavors)
    # no flavor word found: fall back to whatever's left after stripping
    # the brand name and packaging/size noise
    rest = desc
    rest = re.sub(re.escape(brand_raw), "", rest, flags=re.IGNORECASE)
    rest = re.sub(r'["\(\)]', " ", rest)
    rest = re.sub(r"\d+\s?(g|ml|kg)\b", " ", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\bcarbonated (soft|energy) drink\b", " ", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\b(can|glass|gift box|party box)\b", " ", rest, flags=re.IGNORECASE)
    rest = " ".join(rest.split()).strip("- ").lower().replace(" ", "-")
    return rest or "unspecified"


def build_classes(xlsm_path: Path) -> list[dict]:
    seen: dict[tuple[str, str, str], dict] = {}
    for desc in load_descriptions(xlsm_path):
        clean = strip_wholesale_packaging(desc)
        guessed = guess_brand(clean)
        if not guessed:
            continue  # not one of our recognised brands; skip rather than guess wrong
        brand, brand_raw = guessed
        category = guess_category(clean)
        sku = guess_sku(clean, brand_raw)
        class_name = f"{brand}_{category}_{sku}"
        key = (brand, category, sku)
        if key not in seen:
            seen[key] = {
                "class_name": class_name,
                "brand": brand,
                "category": category,
                "sku": sku,
                "is_ours": 1,
            }
    return sorted(seen.values(), key=lambda r: (r["brand"], r["category"], r["sku"]))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <path to proforma .xlsm>")
    xlsm_path = Path(sys.argv[1])
    rows = build_classes(xlsm_path)
    out_path = Path(__file__).resolve().parents[1] / "configs" / "classes.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["class_name", "brand", "category", "sku", "is_ours"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} classes -> {out_path}")


if __name__ == "__main__":
    main()
