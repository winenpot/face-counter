"""Build configs/classes.csv from a sales/export proforma invoice.

The invoice lists many rows per product because of WHOLESALE packaging
variants (Middle Box vs Card board vs Dispenser Box, ...) -- B2B case
types, invisible on a shelf. Those collapse into one class. Retail-visible
differences (Can vs Glass, different flavors) stay separate classes.

The source .xlsm is never read for pricing or customer/buyer info -- only
the "Product Description" column. It is not committed to git (company
pricing + customer data); this script and its output (classes.csv,
containing only product/brand/flavor names) are.

classes.csv is MERGED, never overwritten: rows with `source=manual` (added
by hand: competitors, out_of_scope, products no invoice lists) are always
kept, and invoice rows that a newer invoice no longer lists are kept too
unless --drop-missing is given. `pack_type` is what is physically on the
shelf (the container for drinks, the product family otherwise); which pack
types count toward which share-of-shelf category is configs/reporting.yaml's
job, not this file's.

Usage:
    uv run python scripts/build_classes.py configs/050217-\\ Proforma,Invoice,Packing.xlsm
    uv run python scripts/build_classes.py <invoice.xlsm> --drop-missing
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path

import openpyxl

FIELDS = ["class_name", "brand", "pack_type", "sku", "is_ours", "source"]

# Wholesale case descriptors -- strip these, they're not a shelf-visible
# difference. Longest-first so "Dispenser Box" doesn't get cut short.
WHOLESALE_PACKAGING = [
    "Dispenser Box",
    "Middle Box",
    "Card board",
    "Pillow pack",
]

# Retail-visible container -> pack type. Order matters (checked in turn).
CONTAINER_CATEGORY = [
    (r"\bglass\b", "glass"),
    (r"\bcan\b", "canned"),
]

# Drinks whose invoice rows never say Can or Glass. The container is a fact
# about the product line, confirmed by the invoice's own embedded images and
# by the business (2026-09-27): every TorshX soft-drink flavor is sold in
# BOTH a glass bottle and a can, so one invoice row becomes two classes; the
# TorshX energy drink is a can. A drink that is not listed here and
# does not state its container raises UnknownContainer -- guessing wrong would
# silently put a product in the wrong share-of-shelf category.
DRINK_CONTAINERS = {
    ("TorshX", "soft"): ["canned", "glass"],
    ("TorshX", "energy"): ["canned"],
}


class UnknownContainer(ValueError):
    """A drink row states no container and its brand has none on record."""


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


def drink_kind(desc: str) -> str | None:
    low = desc.lower()
    if "carbonated" not in low:
        return None
    if "energy drink" in low:
        return "energy"
    if "soft drink" in low:
        return "soft"
    return None


def guess_category(desc: str) -> str | None:
    """Pack type stated by the text, or None for a drink that states no container."""
    low = desc.lower()
    for pattern, category in CONTAINER_CATEGORY:
        if re.search(pattern, low):
            return category
    if drink_kind(desc):
        return None  # container not in the text; classes_for resolves it
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
    flavors = sorted(
        set(flavors)
    )  # alpha order: "A, B" and "B, A" collapse to one class
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


def pack_types_for(desc: str, brand: str) -> list[str]:
    """Every shelf-visible pack type one invoice row stands for."""
    stated = guess_category(desc)
    if stated:
        return [stated]
    kind = drink_kind(desc) or ""
    containers = DRINK_CONTAINERS.get((brand, kind))
    if not containers:
        raise UnknownContainer(
            f"{desc!r}: a {kind} drink with no Can/Glass in the text, and no "
            f"({brand!r}, {kind!r}) entry in DRINK_CONTAINERS. Find out how it is "
            "sold and add it there; do not guess."
        )
    return list(containers)


def classes_for(desc: str) -> list[dict]:
    """Class rows for one (wholesale-stripped) invoice description; [] if not our brand."""
    clean = strip_wholesale_packaging(desc)
    guessed = guess_brand(clean)
    if not guessed:
        return []  # not one of our recognised brands; skip rather than guess wrong
    brand, brand_raw = guessed
    sku = guess_sku(clean, brand_raw)
    if sku == "unspecified" and drink_kind(clean) == "energy":
        sku = "energy-drink"
    return [
        {
            "class_name": f"{brand}_{pack}_{sku}",
            "brand": brand,
            "pack_type": pack,
            "sku": sku,
            "is_ours": 1,
            "source": "invoice",
        }
        for pack in pack_types_for(clean, brand)
    ]


def build_classes(xlsm_path: Path) -> list[dict]:
    seen: dict[str, dict] = {}
    for desc in load_descriptions(xlsm_path):
        for row in classes_for(desc):
            seen.setdefault(row["class_name"], row)
    return sorted(seen.values(), key=lambda r: (r["brand"], r["pack_type"], r["sku"]))


def read_existing(path: Path) -> list[dict]:
    """Current classes.csv rows. Files from before `source`/`pack_type` existed
    were fully invoice-generated and called the pack type `category`."""
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("class_name") or "").strip()]
    out = []
    for r in rows:
        r = {k: (v or "").strip() for k, v in r.items() if k}
        if "pack_type" not in r:
            r["pack_type"] = r.pop("category", "")
        r.pop("category", None)
        r.setdefault("source", "invoice")
        out.append({k: r.get(k, "") for k in FIELDS})
    return out


def _sort_key(r: dict) -> tuple:
    # Ours first (the labeling config lists classes in file order), then by name.
    return (
        str(r["is_ours"]) != "1",
        r["brand"],
        r["pack_type"],
        r["sku"],
        r["class_name"],
    )


def merge(
    existing: list[dict], fresh: list[dict], drop_missing: bool
) -> tuple[list[dict], dict]:
    """Merge a new invoice into the current class list without losing anything by accident.

    - `source=manual` rows are always kept, and win over an invoice row of the same name.
    - invoice rows the new invoice no longer lists are kept unless drop_missing.
    """
    fresh_by_name = {r["class_name"]: r for r in fresh}
    existing_names = {r["class_name"] for r in existing}
    merged, kept, dropped = [], [], []
    for r in existing:
        name = r["class_name"]
        if r["source"] == "manual" or name in fresh_by_name:
            merged.append(r if r["source"] == "manual" else fresh_by_name[name])
        elif drop_missing:
            dropped.append(name)
        else:
            merged.append(r)
            kept.append(name)
    added = [r for r in fresh if r["class_name"] not in existing_names]
    merged.extend(added)
    report = {
        "added": [r["class_name"] for r in added],
        "kept_not_on_invoice": kept,
        "dropped": dropped,
    }
    return sorted(merged, key=_sort_key), report


def write_classes(path: Path, rows: list[dict]) -> None:
    """Write via a temp file and rename, so a crash never leaves a half-written list."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("invoice", help="path to the proforma .xlsm")
    ap.add_argument(
        "--drop-missing",
        action="store_true",
        help="remove invoice-sourced classes this invoice no longer lists "
        "(manual rows are never removed)",
    )
    args = ap.parse_args()

    out_path = Path(__file__).resolve().parents[1] / "configs" / "classes.csv"
    try:
        fresh = build_classes(Path(args.invoice))
    except UnknownContainer as e:
        raise SystemExit(f"classes.csv left unchanged: {e}")
    rows, report = merge(read_existing(out_path), fresh, args.drop_missing)
    write_classes(out_path, rows)
    print(f"wrote {len(rows)} classes -> {out_path}")
    for key, names in report.items():
        print(f"  {key}: {len(names)}" + "".join(f"\n    {n}" for n in names))


if __name__ == "__main__":
    main()
