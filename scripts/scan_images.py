#!/usr/bin/env python3
import sys
from pathlib import Path

from PIL import Image


def scan_images(directory="."):
    """Scan directory for images and report their properties."""
    path = Path(directory)
    images = sorted(path.glob("**/*"))
    images = [
        p
        for p in images
        if p.is_file()
        and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
    ]

    if not images:
        print("No images found")
        return

    # Header
    print(f"{'Filename':<40} {'Dimensions':<15} {'Size (MB)':<12} {'Format':<8}")
    print("-" * 75)

    for img_path in images:
        try:
            img = Image.open(img_path)
            width, height = img.size
            size_mb = img_path.stat().st_size / (1024 * 1024)
            fmt = img.format or "Unknown"

            filename = img_path.name
            print(f"{filename:<40} {width}×{height:<13} {size_mb:>10.2f}  {fmt:<8}")
        except Exception as e:
            print(f"{img_path.name:<40} Error: {e}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    scan_images(directory)
