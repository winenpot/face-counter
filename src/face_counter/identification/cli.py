"""shelf-match: build the reference gallery and tune the matcher's threshold
on labeled crops (never the frozen test set; PILOT.md 4b).

    uv run shelf-match gallery                          # report what's in the gallery
    uv run shelf-match tune --labels <gold export>       # embed gold crops, tune threshold
    uv run shelf-match tune --labels <gold export> --device cuda

``tune`` is read-only on the labels. Ground truth for "should this crop match
something in the gallery" comes from ``share.Taxonomy.resolve``: a crop whose
role is "ours" or "targeted" should match (the gallery covers exactly those);
"ours_unreported", "untargeted", `product` and `out_of_scope` should not.
Boxes under ``MIN_SIDE`` are skipped as noise, same cutoff as the T4 spike.

Writes runs/match/<timestamp>/{results.json,crops.jsonl}; runs/ is gitignored
and travels with scripts/sync_from_hemin.sh.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from face_counter.evaluation import ls_export, share
from face_counter.identification import embedder, gallery, matcher
from face_counter.utils.config import (
    DEFAULT_CLASSES,
    DEFAULT_IMAGES_DIR,
    DEFAULT_REPORTING,
    DEFAULT_RUNS_DIR,
    DEFAULT_SCOPE,
)

register_heif_opener()
log = logging.getLogger("shelf-match")

MIN_SIDE = 12  # px; smaller boxes are noise for an embedder too


def _open(images_dir: Path, name: str) -> Image.Image | None:
    p = images_dir / Path(name).name
    if not p.exists():
        hits = sorted(images_dir.glob(Path(name).stem + ".*"))
        if not hits:
            return None
        p = hits[0]
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def collect_crops(labels: Path, images_dir: Path, tax: share.Taxonomy,
                  include_product: bool = False):
    """Return (crops, meta, skipped): one crop per named box (not `product` /
    `out_of_scope` / retired) of every photo with ground truth attached.

    When *include_product* is True, grey `product` boxes are also included with
    ``should_match=False`` — they are faces the labeler couldn't name, so the
    matcher should reject them too.  This is needed to tune a threshold that
    works on the full detector output, not only on the pre-filtered named crops.
    """
    crops, meta, skipped = [], [], collections.Counter()
    for ph in ls_export.load(labels):
        im = _open(images_dir, ph.file_name)
        if im is None:
            skipped["missing"] += 1
            continue
        if abs(im.width - ph.width) > 1 or abs(im.height - ph.height) > 1:
            log.warning(
                "%s: image is %dx%d, export says %dx%d; skipped",
                ph.file_name,
                im.width,
                im.height,
                ph.width,
                ph.height,
            )
            skipped["size_mismatch"] += 1
            continue
        for b in ph.boxes:
            from face_counter.utils.taxonomy import PRODUCT, OUT_OF_SCOPE
            is_product = b.label in (PRODUCT, OUT_OF_SCOPE)
            if is_product:
                if not include_product:
                    continue
                # Grey product box: the labeler couldn't name it -> should not match
                x1, y1, x2, y2 = b.xyxy
                if x2 - x1 < MIN_SIDE or y2 - y1 < MIN_SIDE:
                    continue
                crops.append(
                    im.crop((max(x1, 0), max(y1, 0), min(x2, im.width), min(y2, im.height)))
                )
                meta.append({"photo": ph.file_name, "label": b.label, "brand": "",
                             "pack": "", "role": "untargeted", "should_match": False})
                continue
            resolved = tax.resolve(b.label)
            if resolved is None:
                continue
            brand, pack, role = resolved
            x1, y1, x2, y2 = b.xyxy
            if x2 - x1 < MIN_SIDE or y2 - y1 < MIN_SIDE:
                continue
            crops.append(
                im.crop((max(x1, 0), max(y1, 0), min(x2, im.width), min(y2, im.height)))
            )
            meta.append(
                {
                    "photo": ph.file_name,
                    "label": b.label,
                    "brand": brand,
                    "pack": pack,
                    "role": role,
                    "should_match": role in ("ours", "targeted"),
                }
            )
    return crops, meta, dict(skipped)


def cmd_gallery(args: argparse.Namespace) -> None:
    images = gallery.build(
        invoice_dir=Path(args.invoice_dir),
        competitors_dir=Path(args.competitors_dir),
        classes_path=Path(args.classes),
        reporting_path=Path(args.reporting),
        scope_path=Path(args.scope),
    )
    by_label = collections.Counter(g.label for g in images)
    print(
        f"{len(images)} gallery images, {len(by_label)} labels, under "
        f"{args.invoice_dir} and {args.competitors_dir}\n"
    )
    for label, n in sorted(by_label.items()):
        print(f"  {label:<24} {n} image(s)")
    if not images:
        raise SystemExit(
            "empty gallery: check scope.yaml brands/competitors "
            "and that the folders have images"
        )


def cmd_tune(args: argparse.Namespace) -> None:
    labels = Path(args.labels)
    tax = share.Taxonomy.load(args.classes, args.reporting, args.scope)
    include_product = getattr(args, "include_product_boxes", False)
    crops, meta, skipped = collect_crops(labels, Path(args.images_dir), tax,
                                         include_product=include_product)
    log.info(
        "crops=%d (%s) skipped photos=%s",
        len(crops),
        dict(collections.Counter(m["role"] for m in meta)),
        skipped or "none",
    )
    if not crops:
        raise SystemExit("no crops: check --labels and --images-dir")

    gallery_images = gallery.build(
        invoice_dir=Path(args.invoice_dir),
        competitors_dir=Path(args.competitors_dir),
        classes_path=Path(args.classes),
        reporting_path=Path(args.reporting),
        scope_path=Path(args.scope),
    )
    if not gallery_images:
        raise SystemExit("empty gallery: run `shelf-match gallery` first")
    gallery_labels = [g.label for g in gallery_images]

    log.info(
        "embedding %d gallery images + %d crops (device=%s)...",
        len(gallery_images),
        len(crops),
        args.device or "auto",
    )
    gallery_emb = embedder.embed_paths(
        [g.path for g in gallery_images], device=args.device
    )
    crop_emb = embedder.embed_images(crops, device=args.device)

    matches = matcher.nearest_batch(
        crop_emb, gallery_emb, gallery_labels, threshold=-2.0
    )
    scores = [m.similarity for m in matches]
    should_match = [m["should_match"] for m in meta]
    best = matcher.best_threshold(scores, should_match)

    at_best = [
        matcher.Match(
            label=m.nearest_label if m.similarity >= best["threshold"] else None,
            similarity=m.similarity,
            nearest_label=m.nearest_label,
        )
        for m in matches
    ]
    identity_hits = identity_total = 0
    cm = collections.Counter()
    for meta_row, m in zip(meta, at_best):
        predicted_match = m.label is not None
        cm[(meta_row["should_match"], predicted_match)] += 1
        if meta_row["should_match"] and predicted_match:
            identity_total += 1
            if m.nearest_label == f"{meta_row['brand']}_{meta_row['pack']}":
                identity_hits += 1

    print(
        f"\nbest threshold: {best['threshold']:.4f}  (accuracy {best['accuracy']:.3f} on "
        f"{len(scores)} crops)"
    )
    print(f"  should-match, matched (correct accept): {cm[(True, True)]}")
    print(f"  should-match, not matched (missed):      {cm[(True, False)]}")
    print(f"  should-not, not matched (correct reject): {cm[(False, False)]}")
    print(f"  should-not, matched (false accept):      {cm[(False, True)]}")
    if identity_total:
        print(
            f"\nof the correct accepts, {identity_hits}/{identity_total} "
            f"({identity_hits / identity_total:.1%}) named the right brand+pack"
        )

    out = Path(
        args.out_dir or DEFAULT_RUNS_DIR / "match" / f"{datetime.now():%Y%m%d-%H%M%S}"
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(
            {
                "labels": str(labels),
                "labels_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
                "gallery_images": len(gallery_images),
                "gallery_labels": sorted(set(gallery_labels)),
                "n_crops": len(crops),
                "skipped_photos": skipped,
                "best_threshold": best,
                "confusion": {str(k): v for k, v in cm.items()},
                "identity_accuracy": identity_hits / identity_total
                if identity_total
                else None,
                "note": "threshold tuned on this export only; never on the frozen test set",
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    with (out / "crops.jsonl").open("w", encoding="utf-8") as f:
        for meta_row, m in zip(meta, matches):
            f.write(
                json.dumps(
                    {
                        **meta_row,
                        "similarity": round(m.similarity, 5),
                        "nearest_label": m.nearest_label,
                    }
                )
                + "\n"
            )
    print(f"\nwrote {out}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--classes", default=str(DEFAULT_CLASSES))
    ap.add_argument("--reporting", default=str(DEFAULT_REPORTING))
    ap.add_argument("--scope", default=str(DEFAULT_SCOPE))
    ap.add_argument("--invoice-dir", default=str(gallery.DEFAULT_INVOICE_DIR))
    ap.add_argument("--competitors-dir", default=str(gallery.DEFAULT_COMPETITORS_DIR))
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("gallery", help="report what's in the reference gallery")

    tune = sub.add_parser("tune", help="embed labeled crops and pick a threshold")
    tune.add_argument(
        "--labels", required=True, help="Label Studio JSON export (gold set only)"
    )
    tune.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR))
    tune.add_argument(
        "--device", default=None, help="default: cuda if available, else cpu"
    )
    tune.add_argument("--out-dir", default=None, help="default: runs/match/<timestamp>")
    tune.add_argument(
        "--include-product-boxes", action="store_true",
        help="add grey `product` boxes from the export to the should_not_match pool "
             "when tuning the threshold; recommended for production use so the threshold "
             "is calibrated against the full detector output, not only named crops",
    )

    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "gallery":
        cmd_gallery(args)
    else:
        cmd_tune(args)


if __name__ == "__main__":
    main()
