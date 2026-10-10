"""Pydantic response models for the serving API — mirror `pipeline.Result`
and `pipeline.DebugResult` exactly (T6 plan, Task 4, revised 2026-10-10).

The debug/matcher fields are opt-in and `exclude_none`-stripped from the
JSON when absent, so the default `/count` response carries no trace of
brand identity or share-of-shelf at all — see `pipeline.py`'s module
docstring for why.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, field_validator

from face_counter.serving.pipeline import DEBUG_CAVEATS

_FACES_CAVEAT = (
    'units_detected counts detected products, not labeling-guide "faces" '
    "(the frontmost unit of a lane) — see docs/ISSUE_FACES_NOT_OBJECTS.md."
)
_PACK_CAVEAT = (
    "pack_type is a binary canned/glass split (T4 classifier, 93.8% acc on "
    "the gold set); it does not identify brand or SKU."
)
_ONE_PHOTO_CAVEAT = (
    "One photo, no bootstrap confidence interval — compare across many "
    "photos before drawing a conclusion from a single count."
)
CLASSIFIER_OFF_CAVEAT = (
    "Pack-type classification is off on this deployment: every box is a "
    "generic product and categories is empty. units_detected is unaffected."
)

CAVEATS = [_FACES_CAVEAT, _PACK_CAVEAT, _ONE_PHOTO_CAVEAT]
CAVEATS_CLASSIFIER_OFF = [_FACES_CAVEAT, CLASSIFIER_OFF_CAVEAT, _ONE_PHOTO_CAVEAT]


def _nan_to_none(v: float) -> float | None:
    return None if isinstance(v, float) and math.isnan(v) else v


class BoxResponse(BaseModel):
    xyxy: tuple[float, float, float, float]
    pack_type: str | None = None
    category: str | None
    score: float


class ModelInfo(BaseModel):
    detector: str
    pack_classifier: str | None = None  # None: classifier off


class DebugBoxResponse(BaseModel):
    xyxy: tuple[float, float, float, float]
    label: str
    role: str | None
    similarity: float


class DebugCategoryShare(BaseModel):
    ours: int
    ours_unreported: int
    targeted: int
    untargeted: int
    share: float | None

    @field_validator("share", mode="before")
    @classmethod
    def _share_nan_to_none(cls, v):
        return _nan_to_none(v)


class DebugResponse(BaseModel):
    boxes: list[DebugBoxResponse]
    share: dict[str, DebugCategoryShare]
    caveats: list[str] = list(DEBUG_CAVEATS)


class CountResponse(BaseModel):
    units_detected: int
    categories: dict[str, int]
    boxes: list[BoxResponse]
    model: ModelInfo
    timings_ms: dict[str, float]
    caveats: list[str] = list(CAVEATS)
    debug: DebugResponse | None = None


def from_result(result, model: ModelInfo) -> CountResponse:
    """Build a `CountResponse` from a `pipeline.Result` (and its optional
    `pipeline.DebugResult`), converting NaN shares to `None` along the way."""
    debug = None
    if result.debug is not None:
        debug = DebugResponse(
            boxes=[
                DebugBoxResponse(xyxy=b.xyxy, label=b.label, role=b.role, similarity=b.similarity)
                for b in result.debug.boxes
            ],
            share={
                cat: DebugCategoryShare(
                    ours=r.ours,
                    ours_unreported=r.ours_unreported,
                    targeted=r.targeted,
                    untargeted=r.untargeted,
                    share=r.share,
                )
                for cat, r in result.debug.share.categories.items()
            },
            caveats=list(result.debug.caveats),
        )
    return CountResponse(
        units_detected=result.units_detected,
        categories=result.categories,
        boxes=[
            BoxResponse(xyxy=b.xyxy, pack_type=b.pack_type, category=b.category, score=b.score)
            for b in result.boxes
        ],
        model=model,
        timings_ms=result.timings_ms,
        caveats=list(CAVEATS if model.pack_classifier else CAVEATS_CLASSIFIER_OFF),
        debug=debug,
    )
