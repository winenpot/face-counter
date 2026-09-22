"""Build Label Studio inputs: the labeling config (XML) and a task file for a photo list.

Images are served by Label Studio's local-files storage, so nothing is uploaded twice.
The container must mount the export folder and set (see deploy/label-studio/docker-compose.yml):
    LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
    LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files

Usage:
    uv run shelf-label-prep --list data/splits/test_labeling.txt --level sku
    uv run shelf-label-prep --list data/splits/label_batch_01.txt --level brand

Then in Label Studio: create a project, paste labeling_config_<level>.xml under
Settings > Labeling Interface > Code, and import the tasks JSON.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from face_counter.config import (
    DEFAULT_CLASSES,
    DEFAULT_LABEL_STUDIO_DIR,
    DEFAULT_MANIFEST,
)

# Distinct, readable box colours; cycles for long class lists.
PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
           "#bfef45", "#469990", "#9a6324", "#800000", "#808000", "#000075", "#a9a9a9"]


def read_classes(path: Path, level: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("class_name", "").strip()]
    if level == "sku":
        names = [r["class_name"].strip() for r in rows]
    else:  # brand level; competitors keep their category so share-of-shelf stays computable
        names = [r["class_name"].strip() if r["brand"] == "COMPETITOR" else r["brand"].strip() for r in rows]
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append({"name": n})
    if len(out) < 2:
        raise SystemExit(f"{path} has fewer than 2 classes")
    return out


def labeling_config(classes: list[dict]) -> str:
    labels = "\n".join(
        f'    <Label value={quoteattr(c["name"])} background="{PALETTE[i % len(PALETTE)]}"/>'
        for i, c in enumerate(classes)
    )
    # Filter = search box over the labels (essential with ~400 classes).
    # Zoom is on because whole-aisle photos have small products.
    return f"""<View>
  <Header value="Box every visible product face (front row). Use the search box to find a class."/>
  <Filter name="filter" toName="label" hotkey="shift+f" minlength="1" placeholder="Search class..."/>
  <RectangleLabels name="label" toName="image" strokeWidth="2" canRotate="false">
{labels}
  </RectangleLabels>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <TextArea name="notes" toName="image" placeholder="Optional: glare, blur, unknown product..." maxSubmissions="1"/>
</View>
"""


def build_tasks(list_file: Path, manifest: Path, url_prefix: str) -> list[dict]:
    meta = {}
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            meta = {r["file_name"]: r for r in csv.DictReader(f)}
    tasks = []
    for name in list_file.read_text(encoding="utf-8").split():
        m = meta.get(name, {})
        tasks.append({"data": {
            "image": f"/data/local-files/?d={quote(url_prefix.rstrip('/') + '/' + name)}",
            "photo_id": m.get("photo_id", Path(name).stem),
            "store_id": m.get("store_id", ""),
            "taken_at": m.get("taken_at", ""),
        }})
    return tasks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", required=True, help="text file with one image file name per line")
    ap.add_argument("--classes", default=str(DEFAULT_CLASSES))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--level", choices=["brand", "sku"], default="sku")
    ap.add_argument("--url-prefix", default="raw/images",
                    help="image folder path relative to LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT")
    ap.add_argument("--out-dir", default=str(DEFAULT_LABEL_STUDIO_DIR))
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    classes = read_classes(Path(args.classes), args.level)
    cfg_path = out / f"labeling_config_{args.level}.xml"
    cfg_path.write_text(labeling_config(classes), encoding="utf-8")

    tasks = build_tasks(Path(args.list), Path(args.manifest), args.url_prefix)
    tasks_path = out / f"tasks_{Path(args.list).stem}.json"
    tasks_path.write_text(json.dumps(tasks, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(classes)} classes -> {cfg_path}\n{len(tasks)} tasks   -> {tasks_path}")


if __name__ == "__main__":
    main()
