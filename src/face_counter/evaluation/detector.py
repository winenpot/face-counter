"""Stage 1: how well each detector finds products, against the labeled boxes.

Every labeled box counts as a product, whatever its name (a grey `product`
box is ground truth for the detector too). Inputs are shelf-bakeoff's
detections.jsonl and a Label Studio export; both are in displayed pixels.
"""
from __future__ import annotations

from collections import defaultdict

from face_counter.evaluation import match
from face_counter.evaluation.bootstrap import bootstrap_ci
from face_counter.evaluation.ls_export import Photo

IOU = 0.5


def _per_photo(photos: list[Photo], dets: dict[str, dict]) -> list[dict]:
    out = []
    for p in photos:
        d = dets[p.file_name]
        gt = [b.xyxy for b in p.boxes]
        m = match.greedy([tuple(b) for b in d["boxes"]], d["scores"], gt, IOU)
        out.append({"photo": p, "tp": m.tp, "fp": m.fp, "fn": m.fn, "dup": m.duplicates,
                    "n_pred": len(d["boxes"]), "n_gt": len(gt)})
    return out


def _recall(rows) -> float:
    tp, fn = sum(r["tp"] for r in rows), sum(r["fn"] for r in rows)
    return tp / (tp + fn) if tp + fn else float("nan")


def _precision(rows) -> float:
    tp, fp = sum(r["tp"] for r in rows), sum(r["fp"] for r in rows)
    return tp / (tp + fp) if tp + fp else float("nan")


def evaluate(photos: list[Photo], detections: list[dict], n_boot: int = 2000,
             seed: int = 0) -> list[dict]:
    """One row per model: recall, precision, F1, AP50, AP50-95, duplicate rate,
    count MAE, bootstrap CIs, and recall per scene tag."""
    by_model: dict[str, dict[str, dict]] = defaultdict(dict)
    for d in detections:
        by_model[d["model"]][d["file_name"]] = d

    rows = []
    for model, dets in by_model.items():
        missing = [p.file_name for p in photos if p.file_name not in dets]
        if missing:
            raise ValueError(f"{model}: no detections for labeled photos {missing}")
        for p in photos:
            d = dets[p.file_name]
            if (d["width"], d["height"]) != (p.width, p.height) and p.boxes:
                raise ValueError(f"{model} {p.file_name}: detections are on a {d['width']}x{d['height']} "
                                 f"image, labels on {p.width}x{p.height}; image size differs "
                                 "(EXIF rotation applied on one side only?)")
        per = _per_photo(photos, dets)
        gt = {p.file_name: [b.xyxy for b in p.boxes] for p in photos}
        pd = {p.file_name: ([tuple(b) for b in dets[p.file_name]["boxes"]], dets[p.file_name]["scores"])
              for p in photos}
        tp, fp, fn = (sum(r[k] for r in per) for k in ("tp", "fp", "fn"))
        rec, prec = _recall(per), _precision(per)
        n_pred = sum(r["n_pred"] for r in per)
        row = {
            "model": model, "photos": len(per), "labeled_boxes": tp + fn, "predicted_boxes": n_pred,
            "tp": tp, "fp": fp, "fn": fn,
            "recall": rec, "precision": prec,
            "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "ap50": match.average_precision(pd, gt, 0.5),
            "ap50_95": match.ap50_95(pd, gt),
            "duplicate_rate": sum(r["dup"] for r in per) / n_pred if n_pred else 0.0,
            "count_mae": sum(abs(r["n_pred"] - r["n_gt"]) for r in per) / len(per),
        }
        row["recall_ci"] = bootstrap_ci(per, _recall, n=n_boot, seed=seed)
        row["precision_ci"] = bootstrap_ci(per, _precision, n=n_boot, seed=seed)
        scenes = defaultdict(list)
        for r in per:
            scenes[r["photo"].scene].append(r)
        for scene, rs in sorted(scenes.items()):
            row[f"recall_{scene}"] = _recall(rs)
            row[f"photos_{scene}"] = len(rs)
        rows.append(row)
    return rows
