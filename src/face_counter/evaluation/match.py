"""Box matching and average precision (COCO-style, one class)."""
from __future__ import annotations

from dataclasses import dataclass

Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


def iou(a: Box, b: Box) -> float:
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class MatchResult:
    tp: int
    fp: int
    fn: int
    pred_tp: list[bool]      # per prediction, in input order
    matched_pred: list[int]  # indices of predictions that matched a labeled box
    duplicates: int          # false positives sitting on an already-matched labeled box


def greedy(preds: list[Box], scores: list[float], gt: list[Box], thr: float = 0.5) -> MatchResult:
    """Highest score first; each prediction takes the best still-free labeled box
    with IoU >= thr. One labeled box matches at most one prediction."""
    order = sorted(range(len(preds)), key=lambda i: -scores[i])
    taken = [False] * len(gt)
    pred_tp = [False] * len(preds)
    dup = 0
    for i in order:
        best, best_j = thr, -1
        overlaps_taken = False
        for j, g in enumerate(gt):
            o = iou(preds[i], g)
            if taken[j]:
                overlaps_taken |= o >= thr
            elif o >= best:
                best, best_j = o, j
        if best_j >= 0:
            taken[best_j] = True
            pred_tp[i] = True
        elif overlaps_taken:
            dup += 1
    tp = sum(pred_tp)
    return MatchResult(tp=tp, fp=len(preds) - tp, fn=len(gt) - tp, pred_tp=pred_tp,
                       matched_pred=sorted(i for i, t in enumerate(pred_tp) if t), duplicates=dup)


def average_precision(dets: dict[str, tuple[list[Box], list[float]]],
                      gt: dict[str, list[Box]], thr: float = 0.5) -> float:
    """Area under the precision-recall curve over all photos, 101-point interpolated."""
    scored: list[tuple[float, bool]] = []
    for key, g in gt.items():
        boxes, scores = dets.get(key, ([], []))
        m = greedy(boxes, scores, g, thr)
        scored += list(zip(scores, m.pred_tp))
    n_gt = sum(len(g) for g in gt.values())
    if n_gt == 0:
        return float("nan")
    scored.sort(key=lambda s: -s[0])
    precision, recall, tp = [], [], 0
    for k, (_, hit) in enumerate(scored, 1):
        tp += hit
        precision.append(tp / k)
        recall.append(tp / n_gt)
    # Make precision monotonically non-increasing from the right.
    for k in range(len(precision) - 2, -1, -1):
        precision[k] = max(precision[k], precision[k + 1])
    total, k = 0.0, 0
    for r in (i / 100 for i in range(101)):
        while k < len(recall) and recall[k] < r:
            k += 1
        total += precision[k] if k < len(recall) else 0.0
    return total / 101


def ap50_95(dets, gt) -> float:
    thrs = [0.5 + 0.05 * i for i in range(10)]
    return sum(average_precision(dets, gt, t) for t in thrs) / len(thrs)
