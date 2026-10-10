"""Percentile bootstrap over photos. 30 test photos make small differences noise;
every headline number is reported with this interval."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def bootstrap_ci(
    items: Sequence[T],
    stat: Callable[[Sequence[T]], float],
    n: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float]:
    """(low, high) of `stat` over `n` resamples of `items` with replacement.
    Resamples where `stat` is undefined (NaN) are dropped."""
    if not items:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    vals = sorted(
        v
        for v in (stat([rng.choice(items) for _ in items]) for _ in range(n))
        if v == v
    )
    if not vals:
        return float("nan"), float("nan")
    lo = vals[int((1 - level) / 2 * (len(vals) - 1))]
    hi = vals[int((1 + level) / 2 * (len(vals) - 1))]
    return lo, hi
