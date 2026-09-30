"""shelf-eval: score detectors and compute share of shelf from a Label Studio export.

    uv run shelf-eval --labels data/label_studio/exports/pilot-test-final.json \\
        --detections runs/bakeoff/20260927-114232/detections.jsonl

Writes runs/eval/<stamp>/: detector.csv (one row per model), share.csv (one
row per category), share_per_photo.csv (with each photo's #inner_id and task
id, for spot checks in Label Studio), summary.md and run_args.json.

Brands, tracked competitors and categories come from configs/ (scope.yaml,
classes.csv, reporting.yaml). Change those and re-run; never edit this file
to change who counts as what.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from face_counter.evaluation import detector, ls_export, share
from face_counter.utils.config import (DEFAULT_CLASSES, DEFAULT_REPORTING, DEFAULT_RUNS_DIR,
                                       DEFAULT_SCOPE)

# The detector that pre-drew the boxes the labels were corrected from.
SEED_MODEL = "yolo26l-sku110k"


def _fmt(v) -> str:
    if isinstance(v, float):
        return "n/a" if math.isnan(v) else f"{v:.3f}"
    if isinstance(v, tuple):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return str(v)


def _pct(v: float) -> str:
    return "n/a" if math.isnan(v) else f"{100 * v:.1f}%"


def _write_csv(path: Path, rows: list[dict]) -> None:
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(v) for k, v in r.items()})


def summary(photos, det_rows, rep: share.ShareReport, tax: share.Taxonomy, labels: Path,
            labels_sha256: str = "") -> str:
    sc = tax.scope
    out = [f"# Evaluation: {labels.name}", "",
           f"Labels: `{labels}` (sha256 `{labels_sha256[:12]}`).", "",
           f"{len(photos)} labeled photos. Ours: {', '.join(sc.brands)}. "
           f"Tracked competitors: {', '.join(sc.competitors) or 'none'}.", ""]
    warns = [(p, w) for p in photos for w in p.warnings]
    if warns:
        out += ["## Label warnings (fix in Label Studio, then re-export)", ""]
        out += [f"- #{p.inner_id} (task {p.task_id}, {p.file_name}): {w}" for p, w in warns]
        out.append("")

    out += ["## Share of shelf", ""]
    if rep.share_against == "targeted":
        out += ["Headline = ours / (ours + tracked competitors). This is our share against "
                "the rivals we track, not our share of all cans or bottles on the shelf.", ""]
    else:
        out += ["Headline = ours / every named face in the category (ours, tracked and "
                "untracked competitors). Grey `product` boxes are in neither side.", ""]
    out += ["| Category | Photos | Ours | Tracked | Untracked | Our other brands | Headline share | 95% CI | vs tracked | vs all named |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for cat, r in rep.categories.items():
        out.append(f"| {cat} | {r.photos} | {r.ours} | {r.targeted} | {r.untargeted} | {r.ours_unreported} "
                   f"| {_pct(r.share)} | {_pct(r.share_ci[0])} to {_pct(r.share_ci[1])} "
                   f"| {_pct(r.share_targeted)} | {_pct(r.share_all)} |")
    out.append("")
    for cat, r in rep.categories.items():
        if r.per_brand:
            brands = ", ".join(f"{b} {n}" for b, n in sorted(r.per_brand.items(), key=lambda x: -x[1]))
            out.append(f"- {cat} faces by brand: {brands}")
    out += ["", "## Detector (every labeled box is a product)", "",
            "| Model | Recall | 95% CI | Precision | F1 | AP50 | AP50-95 | Duplicates | Count MAE |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for d in sorted(det_rows, key=lambda d: -d["recall"]):
        out.append(f"| {d['model']} | {_fmt(d['recall'])} | {_fmt(d['recall_ci'])} | {_fmt(d['precision'])} "
                   f"| {_fmt(d['f1'])} | {_fmt(d['ap50'])} | {_fmt(d['ap50_95'])} "
                   f"| {_fmt(d['duplicate_rate'])} | {_fmt(d['count_mae'])} |")
    scenes = sorted({k[len("recall_"):] for d in det_rows for k in d
                     if k.startswith("recall_") and k != "recall_ci"})
    if scenes:
        out += ["", "Recall by scene (photos in brackets):", "",
                "| Model | " + " | ".join(scenes) + " |", "| --- |" + " --- |" * len(scenes)]
        for d in det_rows:
            out.append(f"| {d['model']} | " + " | ".join(
                f"{_fmt(d.get('recall_' + s, float('nan')))} ({d.get('photos_' + s, 0)})" for s in scenes) + " |")
    if any(d["model"] == SEED_MODEL for d in det_rows):
        out += ["", f"Caveat: the labels were corrected from {SEED_MODEL}'s boxes, so its numbers are "
                "biased upward (labelers tend to keep what they are shown). The other models are the "
                "fairer comparison."]
    out += ["", "Detector metrics are at IoU 0.5 with the bake-off's confidence cutoff, so AP is only over "
            "the boxes that survived it. Intervals are a percentile bootstrap over photos."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True, help="Label Studio JSON export (full JSON, not JSON-MIN)")
    ap.add_argument("--detections", default=None, help="shelf-bakeoff detections.jsonl (optional)")
    ap.add_argument("--classes", default=str(DEFAULT_CLASSES))
    ap.add_argument("--reporting", default=str(DEFAULT_REPORTING))
    ap.add_argument("--scope", default=str(DEFAULT_SCOPE))
    ap.add_argument("--out-dir", default=None, help="default: runs/eval/<timestamp>")
    ap.add_argument("--n-boot", type=int, default=2000, help="bootstrap resamples")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    labels = Path(args.labels)
    photos = ls_export.load(labels)
    tax = share.Taxonomy.load(args.classes, args.reporting, args.scope)
    rep = share.evaluate(photos, tax, n_boot=args.n_boot, seed=args.seed)
    det_rows = []
    if args.detections:
        dets = [json.loads(line) for line in Path(args.detections).read_text(encoding="utf-8").splitlines()
                if line.strip()]
        det_rows = detector.evaluate(photos, dets, n_boot=args.n_boot, seed=args.seed)

    out = Path(args.out_dir) if args.out_dir else DEFAULT_RUNS_DIR / "eval" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    if det_rows:
        _write_csv(out / "detector.csv", det_rows)
    _write_csv(out / "share.csv", [{"category": c, "share_against": rep.share_against,
                                    **{k: v for k, v in vars(r).items() if k != "per_brand"},
                                    **{f"brand_{b}": n for b, n in r.per_brand.items()}}
                                   for c, r in rep.categories.items()])
    _write_csv(out / "share_per_photo.csv", rep.per_photo)
    digest = hashlib.sha256(labels.read_bytes()).hexdigest()
    text = summary(photos, det_rows, rep, tax, labels, digest)
    (out / "summary.md").write_text(text, encoding="utf-8")
    (out / "run_args.json").write_text(json.dumps({**vars(args), "labels_sha256": digest}, indent=1), encoding="utf-8")
    print(text)
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
