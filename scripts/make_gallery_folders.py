"""Create the reference-gallery folder per tracked competitor, from config only.

    uv run python scripts/make_gallery_folders.py            # create + report
    uv run python scripts/make_gallery_folders.py --check    # report only

One folder per `<Brand>_<pack_type>` the scope tracks, under
configs/Product/competitors/, each with a README saying what belongs in it.
The folders are what the embedding matcher (PILOT.md step 4b) embeds to name a
crop as a tracked rival; without images in them nothing can tell Icy-Monkey
from Hoffenberg.

Brands and pack types are read from configs/scope.yaml + classes.csv +
reporting.yaml, so adding a tracked competitor stays a config edit: add it to
scope.yaml, re-run this, fill the new folder (PILOT.md step 8, the
extensibility test). Never hand-create a folder -- a name that this script
would not produce is a name the matcher will not look for.

configs/Product/ is gitignored (real product photography), so this script, not
the folders, is the tracked artifact.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from face_counter.utils.config import (
    DEFAULT_CLASSES,
    DEFAULT_REPORTING,
    DEFAULT_SCOPE,
    PROJECT_ROOT,
)
from face_counter.utils.taxonomy import load_reporting, load_scope, targeted_label_names

DEFAULT_GALLERY_DIR = PROJECT_ROOT / "configs" / "Product" / "competitors"

# Enough per face to let the matcher see the label under shelf lighting and
# angle; more is better, these are the floor.
MIN_IMAGES = 2
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".heic"}

README = """# {label}

Reference images for **{brand}**, pack type **{pack}** ({category}).

Drop packshots here, at least {min_images}, named freely. The folder name is
what the matcher reports, so leave it exactly as generated.

What belongs here:

- A straight-on front-of-pack shot (the face a shelf photo shows).
- A slight angle, and a second flavour or variant if the brand has several --
  the matcher names the *brand and pack type*, not the flavour, so variants
  that differ only in colour are all useful here.
- Web product photos or a photo of the real item are both fine. Crops from our
  own shelf photos are fine too, with one exception below.

What does not:

- Crops taken from the **frozen test set** (data/splits/test_labeling.txt).
  Using them here would tune the matcher on the set that scores it, and every
  accuracy number in the pilot would become meaningless.
- Multi-pack, shrink-wrap or carton shots, unless that is how the item sits on
  the shelf.
- The other pack type. A can goes in {brand}_canned, a glass bottle in
  {brand}_glass; mixing them breaks the per-category share, which is reported
  for cans and glass separately.
"""


def gallery_labels(
    scope_path: Path = DEFAULT_SCOPE,
    classes_path: Path = DEFAULT_CLASSES,
    reporting_path: Path = DEFAULT_REPORTING,
) -> list[tuple[str, str, str, str]]:
    """(label, brand, pack_type, category) per tracked competitor pack type."""
    reporting = load_reporting(reporting_path)
    scope = load_scope(scope_path, reporting)
    with open(classes_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_pack = {p: cat for cat, packs in reporting.items() for p in packs}
    out = []
    for label in targeted_label_names(rows, scope):
        brand, _, pack = label.rpartition("_")
        out.append((label, brand, pack, by_pack.get(pack, "?")))
    return out


def count_images(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(
        1
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--gallery-dir", type=Path, default=DEFAULT_GALLERY_DIR)
    ap.add_argument("--scope", type=Path, default=DEFAULT_SCOPE)
    ap.add_argument("--classes", type=Path, default=DEFAULT_CLASSES)
    ap.add_argument("--reporting", type=Path, default=DEFAULT_REPORTING)
    ap.add_argument(
        "--check", action="store_true", help="report what is missing; create nothing"
    )
    args = ap.parse_args()

    labels = gallery_labels(args.scope, args.classes, args.reporting)
    print(f"{len(labels)} tracked-competitor galleries under {args.gallery_dir}\n")

    short = []
    for label, brand, pack, category in labels:
        folder = args.gallery_dir / label
        made = False
        if not args.check:
            folder.mkdir(parents=True, exist_ok=True)
            readme = folder / "README.md"
            if not readme.exists():
                readme.write_text(
                    README.format(
                        label=label,
                        brand=brand,
                        pack=pack,
                        category=category,
                        min_images=MIN_IMAGES,
                    ),
                    encoding="utf-8",
                )
                made = True
        n = count_images(folder)
        mark = "ok  " if n >= MIN_IMAGES else "NEED"
        print(
            f"  {mark} {label:<24} {category:<14} {n} image(s)"
            + ("   (folder created)" if made else "")
        )
        if n < MIN_IMAGES:
            short.append((label, n))

    if short:
        print(
            f"\n{len(short)} folder(s) still need images (at least {MIN_IMAGES} each):"
        )
        for label, n in short:
            print(f"  - {label}: {MIN_IMAGES - n} more")
        print("\nThe embedding matcher cannot name a rival with an empty folder.")
    else:
        print(
            "\nEvery tracked competitor has a gallery. "
            "Next: the embedding matcher (docs/PILOT.md step 4b)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
