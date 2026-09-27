"""The class list and the reporting categories, and the rules that keep them apart.

Labels record what is physically on the shelf: our SKU, or a competitor by
pack type (`COMPETITOR_<pack_type>`), or `out_of_scope`. Which pack types count
toward which share-of-shelf category lives in configs/reporting.yaml and is
applied at report time. So when the business adds, renames or splits a
category, that file changes and every existing annotation stays valid.

`problems()` is what keeps that promise: the competitor vocabulary must cover
every pack type we sell and every pack type a category reports on, or labelers
would have to lump a future category into `other` and it would need relabeling.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from face_counter.utils.config import load_config

COMPETITOR = "COMPETITOR"
OUT_OF_SCOPE = "out_of_scope"
# Pass-one geometry label, and the label a scoped identity pass leaves on every
# box it does not name: "not identified yet", NOT "irrelevant". A later scope
# names these boxes; nothing already labeled has to change.
PRODUCT = "product"
SOURCES = {"invoice", "manual"}


def load_reporting(path: str | Path) -> dict[str, list[str]]:
    """{category: [pack_type, ...]}. A pack type may belong to at most one category."""
    cats = {name: list(spec.get("pack_types") or [])
            for name, spec in (load_config(path).get("categories") or {}).items()}
    owner: dict[str, str] = {}
    for name, packs in cats.items():
        for p in packs:
            if p in owner:
                raise ValueError(f"pack type {p!r} is in both {owner[p]!r} and {name!r}")
            owner[p] = name
    return cats


def category_of(pack_type: str, reporting: dict[str, list[str]]) -> str | None:
    """The reporting category a pack type counts toward, or None if none does."""
    for name, packs in reporting.items():
        if pack_type in packs:
            return name
    return None


def problems(rows: list[dict], reporting: dict[str, list[str]]) -> list[str]:
    """Everything wrong with a class list, as readable sentences. Empty means consistent."""
    out: list[str] = []
    names = Counter((r.get("class_name") or "").strip() for r in rows)
    out += [f"duplicate class_name {n!r}" for n, c in names.items() if c > 1]

    competitor_packs = set()
    our_packs = set()
    for r in rows:
        name = (r.get("class_name") or "").strip()
        brand = (r.get("brand") or "").strip()
        pack = (r.get("pack_type") or "").strip()
        ours = str(r.get("is_ours", "")).strip()
        source = (r.get("source") or "").strip()
        if source not in SOURCES:
            out.append(f"{name}: source must be one of {sorted(SOURCES)}, got {source!r}")
        if name == OUT_OF_SCOPE:
            if ours != "0":
                out.append(f"{name}: is_ours must be 0")
            continue
        if not pack:
            out.append(f"{name}: empty pack_type")
        if brand == COMPETITOR:
            competitor_packs.add(pack)
            if name != f"{COMPETITOR}_{pack}":
                out.append(f"{name}: competitor rows must be named {COMPETITOR}_<pack_type>")
            if ours != "0":
                out.append(f"{name}: a competitor must have is_ours=0")
        else:
            our_packs.add(pack)
            if ours != "1":
                out.append(f"{name}: is_ours must be 1 (competitors use brand {COMPETITOR})")

    if OUT_OF_SCOPE not in names:
        out.append(f"missing {OUT_OF_SCOPE!r} class")
    if "other" not in competitor_packs:
        out.append(f"missing {COMPETITOR}_other (catch-all for a pack type nobody listed yet)")
    for pack in sorted(our_packs):
        if pack not in competitor_packs:
            out.append(f"we sell pack type {pack!r} but there is no {COMPETITOR}_{pack}")
    for cat, packs in reporting.items():
        for pack in packs:
            if pack not in competitor_packs:
                out.append(f"category {cat!r} reports on {pack!r} but there is no {COMPETITOR}_{pack}")
    return out


# --- scope ------------------------------------------------------------------
# The full taxonomy (classes.csv + reporting.yaml) describes everything the
# system can know. A scope (configs/scope.yaml) is the slice being worked on
# now: which categories get labeled and reported, and whose share is reported.
# It filters; it never deletes or renames anything, so widening it later is a
# config edit.


# How finely our own products are named. "brand" gives `<brand>_<pack_type>`,
# which is the prefix of every SKU class name (`<brand>_<pack_type>_<sku>`), so
# moving a scope from brand to sku later refines existing labels, never
# contradicts them.
DETAILS = ("sku", "brand")


@dataclass(frozen=True)
class Scope:
    brands: list[str]          # "ours" in the reported share
    categories: list[str]      # reporting categories in play
    pack_types: list[str]      # union of those categories' pack types
    detail: str = "sku"        # one of DETAILS


def load_scope(path: str | Path, reporting: dict[str, list[str]]) -> Scope:
    cfg = load_config(path) or {}
    brands = list(cfg.get("brands") or [])
    cats = list(cfg.get("categories") or [])
    detail = str(cfg.get("detail") or "sku")
    unknown = [c for c in cats if c not in reporting]
    if unknown:
        raise ValueError(f"scope names categories not in reporting.yaml: {unknown}")
    if not brands or not cats:
        raise ValueError("scope needs at least one brand and one category")
    if detail not in DETAILS:
        raise ValueError(f"scope detail must be one of {DETAILS}, got {detail!r}")
    packs = [p for c in cats for p in reporting[c]]
    return Scope(brands=brands, categories=cats, pack_types=packs, detail=detail)


def scoped_label_names(rows: list[dict], scope: Scope) -> list[str]:
    """Identity-pass labels for a scope: every one of OUR classes whose pack type
    is in scope (any brand -- a third brand's can is still a can, and calling it
    a competitor would corrupt the share), the competitor class per scoped pack
    type, and PRODUCT for every box left unnamed. At detail "brand" our classes
    collapse to `<brand>_<pack_type>`."""
    ours = [r for r in rows
            if str(r.get("is_ours", "")).strip() == "1"
            and (r.get("pack_type") or "").strip() in scope.pack_types]
    if scope.detail == "brand":
        names = {f"{r['brand'].strip()}_{r['pack_type'].strip()}" for r in ours}
    else:
        names = {r["class_name"].strip() for r in ours}
    comps = [f"{COMPETITOR}_{p}" for p in scope.pack_types]
    return sorted(names) + comps + [PRODUCT]
