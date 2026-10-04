"""Render a numbered contact sheet of the photos in a list file, for eyeballing a set.

    uv run python scripts/contact_sheet.py data/splits/gold_val.txt
    uv run python scripts/contact_sheet.py data/splits/gold_val.txt --cols 5 --out sheet.jpg

Numbers follow the list's line order (1 = first line), so "drop 7, 12" maps straight
back to the list file. Photos missing from --images-dir are drawn as a red
"MISSING" tile, not skipped, so the numbering never shifts. Output goes to
data/label_studio/ by default (gitignored, like the photos themselves).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

TILE = 360
LABEL_H = 22


def render(names: list[str], images_dir: Path, cols: int) -> Image.Image:
    rows = -(-len(names) // cols)
    sheet = Image.new("RGB", (cols * TILE, rows * (TILE + LABEL_H)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        x, y = (i % cols) * TILE, (i // cols) * (TILE + LABEL_H)
        path = images_dir / name
        try:
            with Image.open(path) as im:
                w, h = im.size
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((TILE - 4, TILE - 4))
                sheet.paste(im, (x + 2, y + LABEL_H))
            caption, colour = f"{i + 1}  {name[:14]}  {w}x{h}", "black"
        except (FileNotFoundError, OSError):
            draw.rectangle([x + 2, y + LABEL_H, x + TILE - 3, y + LABEL_H + TILE - 3], outline="red")
            caption, colour = f"{i + 1}  MISSING {name[:14]}", "red"
        draw.text((x + 4, y + 4), caption, fill=colour)
    return sheet


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("list", help="text file, one photo file name per line")
    ap.add_argument("--images-dir", default="data/raw/images")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--out", default=None, help="default: data/label_studio/<list stem>_sheet.jpg")
    args = ap.parse_args()
    list_path = Path(args.list)
    names = list_path.read_text(encoding="utf-8").split()
    out = Path(args.out or f"data/label_studio/{list_path.stem}_sheet.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    render(names, Path(args.images_dir), args.cols).save(out, quality=88)
    print(out)


if __name__ == "__main__":
    main()
