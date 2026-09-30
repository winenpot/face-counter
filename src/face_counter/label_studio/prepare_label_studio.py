"""Build Label Studio inputs: the labeling config (XML) and a task file for a photo list.

Images are served by Label Studio's local-files storage, so nothing is uploaded twice.
The container must mount the export folder and set (see deploy/label-studio/docker-compose.yml):
    LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
    LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files

Usage:
    uv run shelf-label-prep --list data/splits/test_labeling.txt --level scope \\
        --predictions runs/bakeoff/20260927-114232/ls_predictions_yolo26l-sku110k.json \\
        --stage-images data/label_studio/images
    uv run shelf-label-prep --list data/splits/test_labeling.txt --level geometry
    uv run shelf-label-prep --list data/splits/label_batch_01.txt --level brand

--predictions attaches a detector's boxes (label `product`) so every photo opens
pre-drawn. --stage-images writes the photos into a folder in a form every browser
displays upright: JPEGs are copied as-is, HEIF/MPO are converted to upright JPEGs.
Upload that folder's contents to the server's raw/images.

Then in Label Studio: create a project, paste labeling_config_<level>.xml under
Settings > Labeling Interface > Code, and import the tasks JSON.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from PIL import Image, ImageOps

from face_counter.utils import taxonomy
from face_counter.utils.config import (
    DEFAULT_CLASSES,
    DEFAULT_IMAGES_DIR,
    DEFAULT_LABEL_STUDIO_DIR,
    DEFAULT_MANIFEST,
    DEFAULT_REPORTING,
    DEFAULT_SCOPE,
)

# Distinct, readable box colours; cycles for long class lists. No grey: grey is
# `product` only, so a named box must never look unnamed.
PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
           "#bfef45", "#469990", "#9a6324", "#800000", "#808000", "#000075", "#ffe119",
           "#fabed4", "#dcbeff", "#aaffc3", "#ffd8b1"]
# `product` = "boxed, not named yet". Grey, so every box still to be named stands out.
UNNAMED_COLOUR = "#9e9e9e"
# Short label lists get number-key shortcuts (1-9) instead of a search box.
MAX_HOTKEYS = 9


def read_classes(path: Path, level: str, scope: Path = DEFAULT_SCOPE,
                 reporting: Path = DEFAULT_REPORTING) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("class_name", "").strip()]
    if level == "geometry":  # pass one: box every product, one label
        return [{"name": taxonomy.PRODUCT}]
    if level == "scope":  # the active pilot's identity pass; see configs/scope.yaml
        s = taxonomy.load_scope(scope, taxonomy.load_reporting(reporting))
        targeted = set(taxonomy.targeted_label_names(rows, s))
        # Targeted competitors are click-only: keys 1-7 stay where labelers learned them.
        return [{"name": n, "hotkey": n not in targeted} for n in taxonomy.scoped_label_names(rows, s)]
    if level == "sku":
        names = [r["class_name"].strip() for r in rows]
    else:  # brand level; competitors keep their pack type so share-of-shelf stays computable
        names = [r["class_name"].strip() if str(r.get("is_ours", "")).strip() == "0" else r["brand"].strip()
                 for r in rows]
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append({"name": n})
    if len(out) < 2:
        raise SystemExit(f"{path} has fewer than 2 classes")
    return out


def labeling_config(classes: list[dict]) -> str:
    """Classes with `"hotkey": False` are click-only: they get no number key and
    don't count toward the short-list limit, so appending them never moves the
    keys labelers already use."""
    keyed = [c for c in classes if c.get("hotkey", True)]
    short = len(keyed) <= MAX_HOTKEYS
    colours = iter(PALETTE * (len(classes) // len(PALETTE) + 1))
    labels = []
    key = 0
    for c in classes:
        colour = UNNAMED_COLOUR if c["name"] == taxonomy.PRODUCT else next(colours)
        hotkey = ""
        if short and c.get("hotkey", True):
            key += 1
            hotkey = f' hotkey="{key}"'
        labels.append(f'    <Label value={quoteattr(c["name"])} background="{colour}"{hotkey}/>')
    labels = "\n".join(labels)
    # Long lists (~400 classes) need a search box; short ones use number keys.
    # Zoom is on because whole-aisle photos have small products.
    search = ("" if short else
              '  <Filter name="filter" toName="label" hotkey="shift+f" minlength="1" '
              'placeholder="Search class..."/>\n')
    header = ("Fix the boxes, then name every can and glass bottle: select a box, press its number."
              if short else
              "Box every visible product face (front row). Use the search box to find a class.")
    return f"""<View>
  <Header value={quoteattr(header)}/>
{search}  <RectangleLabels name="label" toName="image" strokeWidth="2" canRotate="false">
{labels}
  </RectangleLabels>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <TextArea name="notes" toName="image" placeholder="Optional: glare, blur, unknown product..." maxSubmissions="1"/>
</View>
"""


def stage_images(names: list[str], src: Path, out: Path) -> dict[str, str]:
    """Write the photos Label Studio will serve; returns {original name: served name}.

    JPEGs are copied byte for byte (the browser applies their EXIF orientation, the
    same rotation the detector used). HEIF and MPO are converted to plain JPEGs,
    rotated upright with no orientation tag left, because browsers can't be trusted
    to display those containers.
    """
    import pillow_heif

    pillow_heif.register_heif_opener()
    served: dict[str, str] = {}
    for name in names:
        p = Path(name)
        target = name if p.suffix.lower() in {".jpg", ".jpeg"} else f"{p.stem}.jpg"
        if target in served.values():
            raise SystemExit(f"two photos would both be served as {target}")
        served[name] = target
    out.mkdir(parents=True, exist_ok=True)
    for name, target in served.items():
        if target == name:
            shutil.copy2(src / name, out / target)
            continue
        with Image.open(src / name) as im:
            upright = ImageOps.exif_transpose(im).convert("RGB")
        upright.save(out / target, format="JPEG", quality=92)
    return served


def build_tasks(list_file: Path, manifest: Path, url_prefix: str,
                served: dict[str, str] | None = None) -> list[dict]:
    meta = {}
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            meta = {r["file_name"]: r for r in csv.DictReader(f)}
    tasks = []
    for no, name in enumerate(list_file.read_text(encoding="utf-8").split(), 1):
        m = meta.get(name, {})
        shown = (served or {}).get(name, name)
        tasks.append({"data": {
            # The photo's number in its list: a visible, sortable column in the
            # Data Manager, and what review notes refer to. Label Studio's own
            # task ids differ per project and are shown nowhere as "No.".
            "no": no,
            "image": f"/data/local-files/?d={quote(url_prefix.rstrip('/') + '/' + shown)}",
            "photo_id": m.get("photo_id", Path(name).stem),
            "file_name": name,
            "store_id": m.get("store_id", ""),
            "taken_at": m.get("taken_at", ""),
        }})
    return tasks


def attach_predictions(tasks: list[dict], predictions: Path, labels: set[str]) -> list[dict]:
    """Add a detector's boxes (shelf-bakeoff's ls_predictions_<model>.json) to the
    tasks, matched by photo_id. Every photo must have its predictions, and every
    predicted label must exist in the config: Label Studio drops unknown ones
    without a word."""
    by_photo = {t["data"]["photo_id"]: t["predictions"]
                for t in json.loads(predictions.read_text(encoding="utf-8"))}
    missing = [t["data"]["photo_id"] for t in tasks if t["data"]["photo_id"] not in by_photo]
    if missing:
        raise SystemExit(f"{predictions} has no predictions for: {missing}")
    unknown = {lab for t in tasks for p in by_photo[t["data"]["photo_id"]]
               for r in p["result"] for lab in r["value"].get("rectanglelabels", [])} - labels
    if unknown:
        raise SystemExit(f"predicted labels not in the labeling config: {sorted(unknown)}")
    return [{**t, "predictions": by_photo[t["data"]["photo_id"]]} for t in tasks]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", required=True, help="text file with one image file name per line")
    ap.add_argument("--classes", default=str(DEFAULT_CLASSES))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--level", choices=["brand", "sku", "scope", "geometry"], default="sku",
                    help="geometry = pass one, the single label 'product'; "
                         "scope = only the active pilot's labels (configs/scope.yaml)")
    ap.add_argument("--url-prefix", default="raw/images",
                    help="image folder path relative to LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT")
    ap.add_argument("--predictions", default=None,
                    help="shelf-bakeoff ls_predictions_<model>.json to pre-draw boxes from")
    ap.add_argument("--stage-images", default=None, metavar="DIR",
                    help="write the photos, browser-safe, into DIR for upload")
    ap.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR),
                    help="where the exported photos are (source for --stage-images)")
    ap.add_argument("--out-dir", default=str(DEFAULT_LABEL_STUDIO_DIR))
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    classes = read_classes(Path(args.classes), args.level)
    cfg_path = out / f"labeling_config_{args.level}.xml"
    cfg_path.write_text(labeling_config(classes), encoding="utf-8")

    names = Path(args.list).read_text(encoding="utf-8").split()
    served = None
    if args.stage_images:
        served = stage_images(names, Path(args.images_dir), Path(args.stage_images))
    tasks = build_tasks(Path(args.list), Path(args.manifest), args.url_prefix, served)
    if args.predictions:
        tasks = attach_predictions(tasks, Path(args.predictions), {c["name"] for c in classes})
    tasks_path = out / f"tasks_{Path(args.list).stem}.json"
    tasks_path.write_text(json.dumps(tasks, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(classes)} classes -> {cfg_path}\n{len(tasks)} tasks   -> {tasks_path}")
    if served is not None:
        converted = sum(1 for k, v in served.items() if k != v)
        print(f"{len(served)} photos  -> {args.stage_images} ({converted} converted to JPEG)")


if __name__ == "__main__":
    main()
