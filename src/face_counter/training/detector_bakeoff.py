"""Step zero of Phase 1: run candidate detectors over the frozen test set.

Runs on the GPU box. Each candidate finds generic "products" (stage 1 only; naming
is the gallery's job). For every model it writes what a human needs to judge it and
what Label Studio needs to pre-fill the geometry pass:

    runs/bakeoff/<stamp>/
        detections.jsonl         one line per (model, photo): boxes, scores, timing
        counts.csv               photo x model box counts, the first number to compare
        overlays/<model>/*.jpg   downscaled photos with boxes drawn, for eyeballing
        ls_predictions_<model>.json
                                 Label Studio tasks with that model's boxes as
                                 predictions (class "product"), for the geometry pass

Nothing here scores accuracy: the test set has no labels yet. Scoring (recall and
count error against corrected boxes) comes after the geometry pass, from these same
detections.jsonl files.

Pixels are always loaded through ImageOps.exif_transpose: 14 of the 30 test photos
are stored sideways, and every box, manifest width/height and Label Studio
percentage refers to the rotated (displayed) image.

Usage (GPU box, analytics group installed):
    uv run shelf-bakeoff
    uv run shelf-bakeoff --models sku110k-yolo11s,yoloe-26s --imgsz 1280 --conf 0.25
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageOps

from face_counter.utils.config import (
    DEFAULT_IMAGES_DIR,
    DEFAULT_RUNS_DIR,
    DEFAULT_SPLITS_DIR,
)

log = logging.getLogger("bakeoff")

GEOMETRY_LABEL = "product"
# Must match prepare_label_studio.build_tasks, which the geometry project's other
# tasks come from; tests/test_bakeoff.py checks the two stay in step.
LS_URL_PREFIX = "raw/images"

# Generic packaging nouns for the open-vocabulary candidate. Category words, never
# SKU or brand names: stage 1 only has to find products.
YOLOE_PROMPTS = ["can", "bottle", "carton", "juice box", "jar", "box", "packet",
                 "candy bag", "product package"]

# Ultralytics keeps at most 300 boxes per image by default; shelves hold up to ~500.
MAX_DET = 1000


@dataclass
class Detections:
    boxes: list[list[float]] = field(default_factory=list)   # [x1, y1, x2, y2], pixels
    scores: list[float] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)


Detector = Callable[[Image.Image], Detections]


def load_image(path: Path) -> Image.Image:
    """Decode (HEIF/MPO included) and apply EXIF orientation, as Label Studio displays it."""
    import pillow_heif

    pillow_heif.register_heif_opener()
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


# --- candidates -------------------------------------------------------------
# Heavy imports stay inside the builders so the module (and its tests) load without
# torch/ultralytics/transformers installed.

def _ultralytics_detector(model, imgsz: int, conf: float) -> Detector:
    import numpy as np

    def detect(img: Image.Image) -> Detections:
        bgr = np.asarray(img)[:, :, ::-1]  # ultralytics treats arrays as BGR
        r = model.predict(bgr, imgsz=imgsz, conf=conf, max_det=MAX_DET, verbose=False)[0]
        names = r.names
        return Detections(
            boxes=r.boxes.xyxy.cpu().tolist(),
            scores=r.boxes.conf.cpu().tolist(),
            labels=[str(names[int(c)]) for c in r.boxes.cls.cpu().tolist()],
        )

    return detect


def build_sku110k_yolo11s(imgsz: int, conf: float) -> Detector:
    """YOLO11s trained on SKU-110K at 640 (chistopat, HF)."""
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO

    weights = hf_hub_download("chistopat/sku110k-yolo11-object-detector",
                              "weights/sku110k-yolo11-s640.pt")
    return _ultralytics_detector(YOLO(weights), imgsz, conf)


def build_yoloe_26s(imgsz: int, conf: float) -> Detector:
    """YOLOE-26s, text-prompted with generic packaging nouns."""
    from ultralytics import YOLOE

    model = YOLOE("yoloe-26s-seg.pt")
    model.set_classes(YOLOE_PROMPTS)
    return _ultralytics_detector(model, imgsz, conf)


def clean_legacy_config(raw: dict) -> dict:
    """Drop null fields from a config saved by an older transformers.

    This checkpoint's config.json was written by transformers 4.38 with
    `"dilation": null` (and three other nulls). transformers 5 type-checks config
    fields strictly and rejects None for a bool; omitting the key falls back to the
    class default instead, which is what 4.x did with None anyway.
    """
    return {k: v for k, v in raw.items() if v is not None}


def _detr_config(repo: str):
    from huggingface_hub import hf_hub_download
    from transformers import DetrConfig

    with open(hf_hub_download(repo, "config.json"), encoding="utf-8") as f:
        return DetrConfig.from_dict(clean_legacy_config(json.load(f)))


def build_detr_r50_sku110k(imgsz: int, conf: float) -> Detector:
    """DETR-R50, 400 queries, trained on SKU-110K (is36e, HF). imgsz is ignored: the
    processor's own resize (shortest edge 800) applies. 400 queries caps it at 400
    boxes per photo, below our densest shelves."""
    import torch
    from transformers import AutoImageProcessor, DetrForObjectDetection

    repo = "is36e/detr-resnet-50-sku110k"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoImageProcessor.from_pretrained(repo)
    model = DetrForObjectDetection.from_pretrained(repo, config=_detr_config(repo))
    model = model.to(device).eval()

    def detect(img: Image.Image) -> Detections:
        inputs = processor(images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        r = processor.post_process_object_detection(
            outputs, threshold=conf, target_sizes=[(img.height, img.width)])[0]
        return Detections(
            boxes=r["boxes"].cpu().tolist(),
            scores=r["scores"].cpu().tolist(),
            labels=[model.config.id2label[int(i)] for i in r["labels"].cpu().tolist()],
        )

    return detect


CANDIDATES: dict[str, Callable[[int, float], Detector]] = {
    "sku110k-yolo11s": build_sku110k_yolo11s,
    "detr-r50-sku110k": build_detr_r50_sku110k,
    "yoloe-26s": build_yoloe_26s,
}


# --- outputs ----------------------------------------------------------------

def ls_prediction(dets: Detections, width: int, height: int, model_name: str) -> dict:
    """One Label Studio prediction: boxes as percentages of the displayed image."""
    result = []
    for (x1, y1, x2, y2), s in zip(dets.boxes, dets.scores):
        result.append({
            "from_name": "label", "to_name": "image", "type": "rectanglelabels",
            "original_width": width, "original_height": height, "image_rotation": 0,
            "score": round(float(s), 4),
            "value": {
                "x": 100 * x1 / width, "y": 100 * y1 / height,
                "width": 100 * (x2 - x1) / width, "height": 100 * (y2 - y1) / height,
                "rotation": 0, "rectanglelabels": [GEOMETRY_LABEL],
            },
        })
    mean = sum(dets.scores) / len(dets.scores) if dets.scores else 0.0
    return {"model_version": model_name, "score": round(mean, 4), "result": result}


def ls_task(file_name: str, prediction: dict) -> dict:
    image = f"/data/local-files/?d={quote(LS_URL_PREFIX + '/' + file_name)}"
    return {"data": {"image": image, "photo_id": Path(file_name).stem},
            "predictions": [prediction]}


def draw_overlay(img: Image.Image, dets: Detections, out: Path, max_side: int = 1600) -> None:
    im = img.copy()
    scale = min(1.0, max_side / max(im.size))
    if scale < 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)))
    d = ImageDraw.Draw(im)
    for x1, y1, x2, y2 in dets.boxes:
        d.rectangle([x1 * scale, y1 * scale, x2 * scale, y2 * scale], outline="#00ff00", width=2)
    d.rectangle([0, 0, 170, 24], fill="black")
    d.text((6, 5), f"{len(dets.boxes)} boxes", fill="white")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=85)


def run(names: list[str], images_dir: Path, models: dict[str, Detector], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, dict[str, int]] = {n: {} for n in names}
    with open(out_dir / "detections.jsonl", "w", encoding="utf-8") as jl:
        for model_name, detect in models.items():
            tasks = []
            for i, name in enumerate(names, 1):
                img = load_image(images_dir / name)
                t0 = time.perf_counter()
                dets = detect(img)
                secs = time.perf_counter() - t0
                counts[name][model_name] = len(dets.boxes)
                jl.write(json.dumps({
                    "model": model_name, "file_name": name,
                    "width": img.width, "height": img.height, "seconds": round(secs, 3),
                    "boxes": [[round(v, 1) for v in b] for b in dets.boxes],
                    "scores": [round(s, 4) for s in dets.scores], "labels": dets.labels,
                }) + "\n")
                draw_overlay(img, dets, out_dir / "overlays" / model_name / f"{Path(name).stem}.jpg")
                tasks.append(ls_task(name, ls_prediction(dets, img.width, img.height, model_name)))
                log.info("%s %2d/%d %s: %d boxes, %.2fs", model_name, i, len(names), name,
                         len(dets.boxes), secs)
            (out_dir / f"ls_predictions_{model_name}.json").write_text(
                json.dumps(tasks, ensure_ascii=False), encoding="utf-8")

    with open(out_dir / "counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_name", *models])
        for name in names:
            w.writerow([name, *(counts[name].get(m, "") for m in models)])
    log.info("done -> %s", out_dir)
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", default=str(DEFAULT_SPLITS_DIR / "test_labeling.txt"),
                    help="photo list (default: the frozen test set)")
    ap.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR))
    ap.add_argument("--models", default=",".join(CANDIDATES),
                    help=f"comma-separated subset of: {', '.join(CANDIDATES)}")
    ap.add_argument("--imgsz", type=int, default=1280,
                    help="inference size for Ultralytics models (default 1280: whole-aisle photos)")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--out-dir", default=None, help="default: runs/bakeoff/<timestamp>")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    wanted = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in wanted if m not in CANDIDATES]
    if unknown:
        raise SystemExit(f"unknown model(s): {unknown}; choose from {list(CANDIDATES)}")
    names = Path(args.list).read_text(encoding="utf-8").split()
    images_dir = Path(args.images_dir)
    missing = [n for n in names if not (images_dir / n).exists()]
    if missing:
        raise SystemExit(f"{len(missing)} photo(s) missing from {images_dir}, e.g. {missing[:3]}")

    out_dir = Path(args.out_dir) if args.out_dir else (
        DEFAULT_RUNS_DIR / "bakeoff" / datetime.now().astimezone().strftime("%Y%m%d-%H%M%S"))
    models = {m: CANDIDATES[m](args.imgsz, args.conf) for m in wanted}
    (out_dir / "run_args.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_args.json").write_text(json.dumps(vars(args), indent=1), encoding="utf-8")
    run(names, images_dir, models, out_dir)


if __name__ == "__main__":
    main()
