"""Nearest-match identification: label a crop from the gallery, or leave it
unmatched below a similarity threshold (PILOT.md step 4b).

Pure vector math -- no model here, so it is tested without downloading
anything. ``identification/embedder.py`` produces the vectors; the caller
(a future serving layer, or the tuning CLI) owns the threshold decision for
its use case.

An embedding below threshold is not ours and not a tracked rival, but it may
still be an *untracked* competitor the per-category share still needs a pack
type for (``evaluation/share.py``'s ``untargeted`` role): that is
``pack_type.py``'s job, not this module's.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Match:
    label: str | None     # the gallery label, or None when similarity < threshold
    similarity: float     # best similarity found, whatever the label
    nearest_label: str    # the gallery label that was nearest, even when rejected


def nearest_batch(embeddings: np.ndarray, gallery_embeddings: np.ndarray,
                  gallery_labels: list[str], threshold: float) -> list[Match]:
    """One Match per row of `embeddings`. Cosine similarity is a plain dot
    product because `embedder.py` L2-normalises every vector it produces."""
    if len(gallery_labels) == 0:
        raise ValueError("empty gallery: nothing to match against")
    if gallery_embeddings.shape[0] != len(gallery_labels):
        raise ValueError(f"{gallery_embeddings.shape[0]} gallery embeddings "
                         f"but {len(gallery_labels)} labels")
    sims = embeddings @ gallery_embeddings.T   # (n_queries, n_gallery)
    idx = np.argmax(sims, axis=1)
    out = []
    for row, i in zip(sims, idx):
        sim = float(row[i])
        out.append(Match(label=gallery_labels[i] if sim >= threshold else None,
                         similarity=sim, nearest_label=gallery_labels[i]))
    return out


def nearest(embedding: np.ndarray, gallery_embeddings: np.ndarray, gallery_labels: list[str],
           threshold: float) -> Match:
    """Single-query convenience wrapper around `nearest_batch`."""
    return nearest_batch(embedding[None, :], gallery_embeddings, gallery_labels, threshold)[0]


def best_threshold(scores: list[float], should_match: list[bool]) -> dict:
    """Sweep every score as a candidate threshold ("similarity >= t means
    matched") and report the one with the highest accuracy against
    `should_match` (ground truth: does this crop belong to something in the
    gallery at all). Ties keep the higher threshold -- fewer false matches
    costs less here than a few more "not tracked" calls on borderline crops.
    """
    if not scores:
        raise ValueError("no scores to tune a threshold from")
    # Every score as a candidate, plus just above the max (rejects everything)
    # and just below the min (accepts everything).
    candidates = sorted(set(scores), reverse=True)
    candidates = [candidates[0] + 1e-9, *candidates, candidates[-1] - 1e-9]
    n = len(scores)
    best: dict = {"threshold": candidates[0], "accuracy": -1.0}
    for t in candidates:
        correct = sum((s >= t) == want for s, want in zip(scores, should_match))
        acc = correct / n
        if acc > best["accuracy"] or (acc == best["accuracy"] and t > best["threshold"]):
            best = {"threshold": t, "accuracy": acc}
    return best
