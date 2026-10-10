"""Wire the gallery matcher and pack-type classifier onto raw detector output
to produce predicted Photo objects (PILOT.md T5).

The detector finds generic faces; this module names them.  For each detected
box:

1. Crop the box from the actual image file.
2. Embed all crops in one DINOv2 forward pass.
3. Match against the gallery (nearest cosine, with the tuned threshold).
4. Matched crop  → gallery label (``<brand>_<pack>`` for ours, named
   competitor class_name for targeted rivals; both are valid Taxonomy labels).
5. Unmatched crop → ``COMPETITOR_<pack_type>`` from the T4 CLIP classifier.

The returned Photos use the ground-truth photo's metadata (scene, capture
tags, dimensions) so that ``share.evaluate()`` produces a like-for-like
comparison with the ground-truth run.  Photos present in *gt_photos* but
absent from *detections* get an empty box list (the detector found nothing
there; those photos drop out of the share denominator, same as GT photos with
no named faces).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from face_counter.evaluation.ls_export import Box, Photo, UNTAGGED
from face_counter.identification import embedder as emb
from face_counter.identification import matcher as mat
from face_counter.identification import pack_type as pt
from face_counter.identification.gallery import GalleryImage

log = logging.getLogger("predict")


def crop_box(img: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    """Pixel-coordinate box → crop, clipped to the image boundary."""
    w, h = img.size
    x1, y1, x2, y2 = box
    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(w, int(x2) + 1)
    y2 = min(h, int(y2) + 1)
    if x2 <= x1 or y2 <= y1:
        return img.crop((0, 0, max(1, w), max(1, h)))   # degenerate: return full image
    return img.crop((x1, y1, x2, y2))


def name_crops(
    crops: list[Image.Image],
    gallery_labels: list[str],
    gallery_embeddings: np.ndarray,
    threshold: float,
    device: str | None = None,
) -> list[mat.Match]:
    """Name a list of crops: embed, match against the gallery, and classify
    whatever doesn't match as ``COMPETITOR_<pack_type>`` (T4's CLIP classifier).

    Shared by ``predict_photos`` (bulk, from a ``detections.jsonl`` file) and
    the serving pipeline (one photo's crops at request time) — the naming
    step is identical either way, only the crop source differs.
    """
    n_crops = len(crops)
    if n_crops == 0:
        log.warning("no crops to embed; nothing to name")
        crop_embs = np.empty((0, gallery_embeddings.shape[1] if gallery_embeddings.ndim == 2 else 1))
    else:
        log.info("embedding %d crops (device=%s)...", n_crops, device or "auto")
        crop_embs = emb.embed_images(crops, device=device)

    if n_crops > 0 and len(gallery_labels) > 0:
        matches = mat.nearest_batch(crop_embs, gallery_embeddings, gallery_labels, threshold)
    else:
        matches = []

    # Unmatched crops need pack-type classification.
    unmatched_indices = [i for i, m in enumerate(matches) if m.label is None]
    if unmatched_indices:
        unmatched_crops = [crops[i] for i in unmatched_indices]
        log.info("classifying %d unmatched crops as canned/glass...", len(unmatched_crops))
        packs = pt.pack_types(unmatched_crops, device=device)
        for pos, i in enumerate(unmatched_indices):
            pack = packs[pos]
            matches[i] = mat.Match(
                label=f"COMPETITOR_{pack}",
                similarity=matches[i].similarity,
                nearest_label=matches[i].nearest_label,
            )
    return matches


def predict_photos(
    detections: list[dict],
    gt_photos: list[Photo],
    images_dir: Path,
    gallery_images: list[GalleryImage],
    gallery_embeddings: np.ndarray,
    threshold: float,
    device: str | None = None,
) -> list[Photo]:
    """Predict labels for every box in *detections* and return one Photo per
    GT photo.

    Parameters
    ----------
    detections:
        One dict per photo, as read from a ``detections.jsonl`` file
        (keys: ``file_name``, ``boxes`` [[x1,y1,x2,y2], ...], ``scores``).
    gt_photos:
        Ground-truth Photo objects (label information is ignored; only
        ``file_name``, ``scene``, ``capture``, ``photo_issue``, ``width``,
        ``height``, ``inner_id``, ``task_id``, ``photo_id`` are used).
    images_dir:
        Directory that contains the raw image files.
    gallery_images:
        As returned by ``gallery.build()``.
    gallery_embeddings:
        Pre-computed (N_gallery, D) array, in the same order as
        ``gallery_images``.
    threshold:
        Cosine similarity threshold from ``matcher.best_threshold`` /
        ``shelf-match tune``.
    device:
        ``\"cuda\"``, ``\"cpu\"``, or None for auto.
    """
    gt_by_name: dict[str, Photo] = {p.file_name: p for p in gt_photos}
    det_by_name: dict[str, dict] = {d["file_name"]: d for d in detections}
    gallery_labels = [g.label for g in gallery_images]

    # ---- collect all crops in (file_name, box_index) order ----------------
    photo_order: list[str] = list(gt_by_name)   # stable; Photos we'll return
    all_crops: list[Image.Image] = []
    # For each file: list of box pixel coords (may be empty).
    file_boxes: dict[str, list[tuple[float, float, float, float]]] = {}

    for fname in photo_order:
        det = det_by_name.get(fname)
        if det is None or not det.get("boxes"):
            file_boxes[fname] = []
            continue
        img_path = images_dir / fname
        try:
            img = ImageOps.exif_transpose(Image.open(img_path)).convert("RGB")
        except Exception as e:
            log.warning("cannot open %s: %s — photo will have 0 predicted boxes", img_path, e)
            file_boxes[fname] = []
            continue
        raw_boxes: list[list[float]] = det["boxes"]
        coords: list[tuple[float, float, float, float]] = [
            (float(b[0]), float(b[1]), float(b[2]), float(b[3])) for b in raw_boxes
        ]
        file_boxes[fname] = coords
        all_crops.extend(crop_box(img, c) for c in coords)

    n_crops = len(all_crops)
    matches = name_crops(all_crops, gallery_labels, gallery_embeddings, threshold, device)

    # ---- assemble Photo objects --------------------------------------------
    crop_cursor = 0
    photos = []
    for fname in photo_order:
        gt = gt_by_name[fname]
        coords = file_boxes.get(fname, [])
        boxes = []
        for coord in coords:
            m = matches[crop_cursor]
            crop_cursor += 1
            boxes.append(Box(xyxy=coord, label=m.label or "product"))
        photos.append(Photo(
            task_id=gt.task_id,
            inner_id=gt.inner_id,
            photo_id=gt.photo_id,
            file_name=gt.file_name,
            width=gt.width,
            height=gt.height,
            scene=gt.scene,
            capture=gt.capture,
            photo_issue=gt.photo_issue,
            boxes=boxes,
        ))

    assert crop_cursor == n_crops, f"crop cursor mismatch: {crop_cursor} vs {n_crops}"
    return photos
