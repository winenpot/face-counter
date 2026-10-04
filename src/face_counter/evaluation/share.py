"""Business output: share of shelf per reporting category, from labeled boxes.

Nothing here knows a brand, a competitor or a category by name. A label is
resolved through configs/classes.csv to (brand, pack_type), the pack type to
a category through configs/reporting.yaml, and the brand to a role through
configs/scope.yaml:

    ours              is_ours=1 and brand in scope `brands`
    ours_unreported   is_ours=1, another brand of ours
    targeted          is_ours=0 and brand in scope `competitors`
    untargeted        is_ours=0 otherwise (incl. COMPETITOR_<pack_type>)

`product` and `out_of_scope` boxes are not named, so they are in no share.
Making Coca-Cola a tracked rival is one line in scope.yaml (plus its
classes.csv row if it has none): boxes already labeled Coca-Cola move from
untargeted to targeted, and the number is recomputed. Boxes still labeled
COMPETITOR_<pack> cannot move by themselves: that is a rename pass in Label
Studio, never a redraw.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from face_counter.evaluation.bootstrap import bootstrap_ci
from face_counter.evaluation.ls_export import Photo
from face_counter.utils import taxonomy

ROLES = ("ours", "ours_unreported", "targeted", "untargeted")


@dataclass
class Taxonomy:
    labels: dict[str, tuple[str, str, bool]]   # label -> (brand, pack_type, is_ours)
    reporting: dict[str, list[str]]
    scope: taxonomy.Scope

    @classmethod
    def load(cls, classes: str | Path, reporting: str | Path, scope: str | Path) -> "Taxonomy":
        with open(classes, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rep = taxonomy.load_reporting(reporting)
        sc = taxonomy.load_scope(scope, rep)
        taxonomy.targeted_label_names(rows, sc)   # raises on an unknown or own-brand competitor
        labels: dict[str, tuple[str, str, bool]] = {}
        for r in rows:
            brand, pack = r["brand"].strip(), (r["pack_type"] or "").strip()
            ours = str(r["is_ours"]).strip() == "1"
            labels[r["class_name"].strip()] = (brand, pack, ours)
            if ours:  # brand-level label, the prefix of every SKU class name
                labels.setdefault(f"{brand}_{pack}", (brand, pack, True))
        return cls(labels=labels, reporting=rep, scope=sc)

    def resolve(self, label: str) -> tuple[str, str, str] | None:
        """(brand, pack_type, role), or None for a box that names nothing."""
        if label in (taxonomy.PRODUCT, taxonomy.OUT_OF_SCOPE):
            return None
        if label in self.scope.retired and label in self.labels:
            return None   # no longer tracked: grey, in neither side of the share
        if label not in self.labels:
            raise ValueError(f"label {label!r} is not in classes.csv; add the row (or fix the "
                             "label) before evaluating, or it silently drops out of the share")
        brand, pack, ours = self.labels[label]
        if ours:
            role = "ours" if brand in self.scope.brands else "ours_unreported"
        else:
            role = "targeted" if brand in self.scope.competitors else "untargeted"
        return brand, pack, role


@dataclass
class CategoryResult:
    ours: int = 0
    ours_unreported: int = 0
    targeted: int = 0
    untargeted: int = 0
    photos: int = 0                      # photos with a non-empty headline denominator
    share_targeted: float = float("nan")
    share_all: float = float("nan")
    share: float = float("nan")          # the scope's headline (share_against)
    share_ci: tuple[float, float] = (float("nan"), float("nan"))
    per_brand: dict[str, int] = field(default_factory=dict)


@dataclass
class ShareReport:
    share_against: str
    categories: dict[str, CategoryResult]
    per_photo: list[dict]                # one row per (photo, category) with any named face


def _ratio(num: int, den: int) -> float:
    return num / den if den else float("nan")


def _denominator(c: Counter, against: str) -> int:
    if against == "targeted":
        return c["ours"] + c["targeted"]
    return sum(c[r] for r in ROLES)


def evaluate(photos: list[Photo], tax: Taxonomy, n_boot: int = 2000, seed: int = 0) -> ShareReport:
    against = tax.scope.share_against
    counts: dict[str, list[tuple[Photo, Counter, Counter]]] = defaultdict(list)
    per_photo = []
    for p in photos:
        by_cat: dict[str, Counter] = defaultdict(Counter)
        brands: dict[str, Counter] = defaultdict(Counter)
        for b in p.boxes:
            r = tax.resolve(b.label)
            if r is None:
                continue
            brand, pack, role = r
            cat = taxonomy.category_of(pack, tax.reporting)
            if cat not in tax.scope.categories:
                continue
            by_cat[cat][role] += 1
            if role in ("ours", "targeted"):
                brands[cat][brand] += 1
        for cat in tax.scope.categories:
            c = by_cat.get(cat, Counter())
            counts[cat].append((p, c, brands.get(cat, Counter())))
            if sum(c.values()):
                per_photo.append({
                    "inner_id": p.inner_id, "task_id": p.task_id, "file_name": p.file_name,
                    "scene": p.scene, "category": cat, **{r: c[r] for r in ROLES},
                    "share_targeted": _ratio(c["ours"], _denominator(c, "targeted")),
                    "share_all": _ratio(c["ours"], _denominator(c, "all")),
                })

    cats = {}
    for cat in tax.scope.categories:
        rows = counts.get(cat, [])
        total = sum((c for _, c, _ in rows), Counter())
        res = CategoryResult(ours=total["ours"], ours_unreported=total["ours_unreported"],
                             targeted=total["targeted"], untargeted=total["untargeted"])
        res.share_targeted = _ratio(total["ours"], _denominator(total, "targeted"))
        res.share_all = _ratio(total["ours"], _denominator(total, "all"))
        res.share = res.share_all if against == "all" else res.share_targeted
        # Photos with nothing in the category are left out, not scored 0.
        used = [c for _, c, _ in rows if _denominator(c, against)]
        res.photos = len(used)

        def pooled(sample, against=against):
            num = sum(c["ours"] for c in sample)
            return _ratio(num, sum(_denominator(c, against) for c in sample))

        res.share_ci = bootstrap_ci(used, pooled, n=n_boot, seed=seed)
        res.per_brand = dict(sum((b for _, _, b in rows), Counter()))
        cats[cat] = res
    return ShareReport(share_against=against, categories=cats, per_photo=per_photo)
