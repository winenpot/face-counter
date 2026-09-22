"""Export shelf photos from MongoDB GridFS to disk and write a manifest.

Read-only and resumable: files already on disk are skipped, so the script can be
stopped and re-run safely. Every later dataset is built from data/raw/manifest.csv.

Usage:
    uv run shelf-export --limit 50   # dry run
    uv run shelf-export              # everything
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from face_counter.config import (
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    get_path,
    load_config,
    mongo_client,
)

log = logging.getLogger("export")

MANIFEST_COLUMNS = [
    "photo_id", "file_name", "store_id", "visit_id", "taken_at", "rep_id", "city",
    "width", "height", "bytes", "sha256", "exported_at",
]


def _ext_for(img_format: str | None, filename: str | None) -> str:
    """Extension from the decoded image format (trustworthy), else the uploaded file name."""
    if img_format:
        return "." + img_format.lower().replace("jpeg", "jpg")
    suffix = Path(filename or "").suffix.lower()
    return suffix or ".jpg"


def _parse_date(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def iter_photo_records(db, cfg: dict):
    """Yield (file_id, metadata_doc) pairs according to the metadata source in the config."""
    meta = cfg["metadata"]
    bucket = cfg["mongo"].get("gridfs_bucket", "fs")
    fields = meta.get("fields", {})
    exp = cfg.get("export", {})
    query = dict(meta.get("query") or {})

    date_field = fields.get("taken_at")
    date_from, date_to = _parse_date(exp.get("date_from")), _parse_date(exp.get("date_to"))
    if date_field and (date_from or date_to):
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lt"] = date_to
        query[date_field] = rng

    batch = exp.get("batch_size", 200)
    if meta.get("source", "collection") == "gridfs":
        cursor = db[f"{bucket}.files"].find(query, batch_size=batch)
        for doc in cursor:
            yield doc["_id"], doc
    else:
        id_field = meta["file_id_field"]
        query.setdefault(id_field, {"$exists": True})
        cursor = db[meta["collection"]].find(query, batch_size=batch)
        for doc in cursor:
            yield get_path(doc, id_field), doc


def load_existing(manifest_path: Path) -> dict[str, dict]:
    if not manifest_path.exists():
        return {}
    with open(manifest_path, newline="", encoding="utf-8") as f:
        return {row["photo_id"]: row for row in csv.DictReader(f)}


def export(cfg: dict, limit: int | None = None, db=None) -> Path:
    import gridfs

    configured = Path(cfg["export"]["out_dir"])
    out_dir = configured if configured.is_absolute() else PROJECT_ROOT / configured
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.csv"

    if db is None:
        db = mongo_client(cfg)[cfg["mongo"]["database"]]
    fs = gridfs.GridFS(db, collection=cfg["mongo"].get("gridfs_bucket", "fs"))
    fields = cfg["metadata"].get("fields", {})
    throttle = float(cfg["export"].get("throttle_seconds", 0) or 0)

    rows = load_existing(manifest_path)
    stats = {"new": 0, "skipped": 0, "missing": 0, "bad_image": 0}

    for file_id, meta_doc in iter_photo_records(db, cfg):
        if limit is not None and stats["new"] >= limit:
            break
        if file_id is None:
            stats["missing"] += 1
            continue
        pid = str(file_id)
        if pid in rows and (img_dir / rows[pid]["file_name"]).exists():
            stats["skipped"] += 1
            continue
        try:
            grid_out = fs.get(file_id)
        except gridfs.errors.NoFile:
            log.warning("GridFS file %s not found", pid)
            stats["missing"] += 1
            continue

        data = grid_out.read()
        try:
            with Image.open(io.BytesIO(data)) as im:
                fmt = im.format
                # Phone photos carry an EXIF rotation; store the size as it will be displayed.
                width, height = ImageOps.exif_transpose(im).size
        except Exception as e:  # corrupt or non-image upload
            log.warning("Skipping %s: not a readable image (%s)", pid, e)
            stats["bad_image"] += 1
            continue

        file_name = pid + _ext_for(fmt, getattr(grid_out, "filename", None))
        tmp = img_dir / (file_name + ".part")
        tmp.write_bytes(data)          # original bytes, untouched (EXIF kept)
        tmp.replace(img_dir / file_name)  # atomic: no half-written files after a crash

        taken_at = get_path(meta_doc, fields.get("taken_at"))
        rows[pid] = {
            "photo_id": pid,
            "file_name": file_name,
            "store_id": get_path(meta_doc, fields.get("store_id"), ""),
            "visit_id": get_path(meta_doc, fields.get("visit_id"), ""),
            "taken_at": taken_at.isoformat() if isinstance(taken_at, datetime) else (taken_at or ""),
            "rep_id": get_path(meta_doc, fields.get("rep_id"), ""),
            "city": get_path(meta_doc, fields.get("city"), ""),
            "width": width,
            "height": height,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        }
        stats["new"] += 1
        if stats["new"] % 100 == 0:
            log.info("exported %d ...", stats["new"])
            _write_manifest(manifest_path, rows)  # checkpoint
        if throttle:
            time.sleep(throttle)

    _write_manifest(manifest_path, rows)
    log.info("done: %s | manifest rows: %d -> %s", stats, len(rows), manifest_path)
    return manifest_path


def _write_manifest(path: Path, rows: dict[str, dict]) -> None:
    tmp = path.with_suffix(".csv.part")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        for row in rows.values():
            w.writerow({k: row.get(k, "") for k in MANIFEST_COLUMNS})
    tmp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--limit", type=int, default=None, help="export at most N new photos (for a test run)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    export(load_config(args.config), limit=args.limit)


if __name__ == "__main__":
    main()
