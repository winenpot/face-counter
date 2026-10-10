"""The serving pipeline: one photo in, counts out (T6 plan, revised 2026-10-10).

Default path — detection only:
    detect (ONNX YOLO26l-sku110k) -> one generic box per unit -> units_detected.
No torch, no transformers, no CLIP: the process stays at the ONNX detector's
footprint (docs/SERVING_STRATEGY.md §1 for why that matters on atpg).

Optional pack-type stage — ``ServeConfig.classify`` (env
``FACE_COUNTER_CLASSIFY=1``), off by default since 2026-10-10:
    crop -> classify canned/glass (T4's CLIP ViT-L/14, 93.8% acc on gold)
    -> count per category (configs/reporting.yaml).
Off because it costs ~15 s per 44-crop photo and a ~2 GB resident floor on
CPU. Alternatives are tracked in docs/PACK_TYPE_ALTERNATIVES.md.

Optional ``debug=True`` path — the brand-identity matcher (T3) and the
share-of-shelf calculation (T5), lazily loaded on first use: EXPERIMENTAL,
not demo-ready. Identity accuracy is 65.3% on the gold set and the T5 verdict
found the predicted share has a large, well-understood architectural gap
(embedding separability, not a code bug). This exists for internal poking,
never the demo's headline numbers — see ``DebugResult.caveats``. It loads
DINOv2, and CLIP too (``predict.name_crops`` names unmatched crops'
pack type), whatever ``classify`` says.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from PIL import Image

from face_counter.evaluation import share
from face_counter.evaluation.ls_export import UNTAGGED as _UNTAGGED
from face_counter.evaluation.ls_export import Box, Photo
from face_counter.identification import embedder as emb
from face_counter.identification import gallery as gal
from face_counter.identification import pack_type as pt
from face_counter.identification import predict as pred_mod
from face_counter.serving import onnx_detector as onnx_det
from face_counter.training import detector_bakeoff as bk
from face_counter.utils import taxonomy as tax_mod
from face_counter.utils.config import (
    DEFAULT_BAKEOFF_CONFIG,
    DEFAULT_CLASSES,
    DEFAULT_REPORTING,
    DEFAULT_SCOPE,
)

DEBUG_CAVEATS = [
    (
        "EXPERIMENTAL, not demo-ready: brand-identity matching is only 65.3% "
        "accurate on the gold set (PILOT.md T3)."
    ),
    (
        "Predicted share has a large, well-understood gap (embedding "
        "separability, not a code bug — PILOT.md T5 verdict). Do not use these "
        "numbers for business decisions."
    ),
]


@dataclass
class ServeConfig:
    classes_path: Path = DEFAULT_CLASSES
    reporting_path: Path = DEFAULT_REPORTING
    scope_path: Path = DEFAULT_SCOPE
    bakeoff_config: Path = DEFAULT_BAKEOFF_CONFIG
    detector_model: str = "yolo26l-sku110k"
    imgsz: int = 1280
    conf: float = 0.25
    match_threshold: float = 0.7115  # debug-path only; see T6 plan's resolved questions
    device: str | None = "cpu"
    api_key: str = "12345678"  # placeholder, see Task 5b; rotate before non-local use
    classify: bool = False  # CLIP pack-type stage; see module docstring

    @classmethod
    def from_env(cls) -> ServeConfig:
        def _s(name: str, default: str) -> str:
            return os.environ.get(name, default)

        return cls(
            classes_path=Path(_s("FACE_COUNTER_CLASSES", str(DEFAULT_CLASSES))),
            reporting_path=Path(_s("FACE_COUNTER_REPORTING", str(DEFAULT_REPORTING))),
            scope_path=Path(_s("FACE_COUNTER_SCOPE", str(DEFAULT_SCOPE))),
            bakeoff_config=Path(_s("FACE_COUNTER_BAKEOFF_CONFIG", str(DEFAULT_BAKEOFF_CONFIG))),
            detector_model=_s("FACE_COUNTER_DETECTOR_MODEL", "yolo26l-sku110k"),
            imgsz=int(_s("FACE_COUNTER_IMGSZ", "1280")),
            conf=float(_s("FACE_COUNTER_CONF", "0.25")),
            match_threshold=float(_s("FACE_COUNTER_MATCH_THRESHOLD", "0.7115")),
            device=_s("FACE_COUNTER_DEVICE", "cpu"),
            api_key=_s("FACE_COUNTER_API_KEY", "12345678"),
            classify=_s("FACE_COUNTER_CLASSIFY", "0").strip().lower() in {"1", "true", "yes", "on"},
        )


@dataclass
class BoxResult:
    xyxy: tuple[float, float, float, float]
    pack_type: str | None  # "canned"/"glass" (T4 classifier); None when classify is off
    category: str | None  # via configs/reporting.yaml; None if unmapped or classify is off
    score: float  # detector confidence


@dataclass
class DebugBoxResult:
    xyxy: tuple[float, float, float, float]
    label: str  # gallery label or COMPETITOR_<pack>
    role: str | None  # ours / ours_unreported / targeted / untargeted / None
    similarity: float


@dataclass
class DebugResult:
    boxes: list[DebugBoxResult]
    share: share.ShareReport
    caveats: list[str] = field(default_factory=lambda: list(DEBUG_CAVEATS))


@dataclass
class Result:
    units_detected: int
    categories: dict[str, int]  # category -> count, reliable path only
    boxes: list[BoxResult]
    timings_ms: dict[str, float]
    debug: DebugResult | None = None


class Pipeline:
    def __init__(self, cfg: ServeConfig, detector, reporting: dict[str, list[str]]):
        self.cfg = cfg
        self.detector = detector
        self.reporting = reporting
        # Debug-only deps: lazy, so a deployment that never asks for `debug`
        # never pays for the gallery or DINOv2.
        self._gallery_images: list | None = None
        self._gallery_embeddings = None
        self._taxonomy: share.Taxonomy | None = None

    @classmethod
    def load(cls, cfg: ServeConfig) -> Pipeline:
        onnx_path = bk.resolve_onnx(cfg.detector_model, cfg.bakeoff_config)
        detector = onnx_det.build(onnx_path, cfg.imgsz, cfg.conf)
        reporting = tax_mod.load_reporting(cfg.reporting_path)
        return cls(cfg, detector, reporting)

    def _ensure_debug_deps(self) -> None:
        if self._taxonomy is not None:
            return
        self._gallery_images = gal.build(
            classes_path=self.cfg.classes_path,
            reporting_path=self.cfg.reporting_path,
            scope_path=self.cfg.scope_path,
        )
        if not self._gallery_images:
            raise RuntimeError("empty gallery — debug matching unavailable")
        self._gallery_embeddings = emb.embed_paths(
            [g.path for g in self._gallery_images], device=self.cfg.device
        )
        self._taxonomy = share.Taxonomy.load(
            self.cfg.classes_path, self.cfg.reporting_path, self.cfg.scope_path
        )

    def run(self, img: Image.Image, debug: bool = False) -> Result:
        t0 = perf_counter()
        dets = self.detector(img)
        t1 = perf_counter()

        # Crops only when a stage needs them: the detection-only default
        # never holds per-box image copies.
        need_crops = self.cfg.classify or debug
        crops = [pred_mod.crop_box(img, tuple(b)) for b in dets.boxes] if need_crops else []
        if self.cfg.classify and crops:
            packs: list[str | None] = list(pt.pack_types(crops, device=self.cfg.device))
        else:
            packs = [None] * len(dets.boxes)
        t2 = perf_counter()

        box_results: list[BoxResult] = []
        cat_counts: Counter = Counter()
        for box, score, pack in zip(dets.boxes, dets.scores, packs):
            category = tax_mod.category_of(pack, self.reporting) if pack else None
            box_results.append(
                BoxResult(xyxy=tuple(box), pack_type=pack, category=category, score=score)
            )
            if category:
                cat_counts[category] += 1

        debug_result: DebugResult | None = None
        if debug:
            self._ensure_debug_deps()
            assert self._taxonomy is not None and self._gallery_images is not None
            gallery_labels = [g.label for g in self._gallery_images]
            matches = pred_mod.name_crops(
                crops, gallery_labels, self._gallery_embeddings,
                self.cfg.match_threshold, self.cfg.device,
            )
            debug_boxes: list[DebugBoxResult] = []
            photo_boxes: list[Box] = []
            for box, m in zip(dets.boxes, matches):
                label = m.label or tax_mod.PRODUCT
                resolved = self._taxonomy.resolve(label)
                role = resolved[2] if resolved else None
                debug_boxes.append(
                    DebugBoxResult(xyxy=tuple(box), label=label, role=role, similarity=m.similarity)
                )
                photo_boxes.append(Box(xyxy=tuple(box), label=label))
            photo = Photo(
                task_id=0, inner_id=0, photo_id="upload", file_name="upload",
                width=img.width, height=img.height, scene=_UNTAGGED,
                capture=[], photo_issue=[], boxes=photo_boxes,
            )
            rep = share.evaluate([photo], self._taxonomy, n_boot=0)
            debug_result = DebugResult(boxes=debug_boxes, share=rep)
        t3 = perf_counter()

        timings = {"detect_ms": (t1 - t0) * 1000}
        if self.cfg.classify:
            timings["classify_ms"] = (t2 - t1) * 1000
        timings["total_ms"] = (t3 - t0) * 1000
        return Result(
            units_detected=len(dets.boxes),
            categories=dict(cat_counts),
            boxes=box_results,
            timings_ms=timings,
            debug=debug_result,
        )
