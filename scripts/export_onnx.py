"""Export an ultralytics `.pt` detector to ONNX for serving.

Ultralytics (AGPL) runs here once, offline, against the weights file; the
served process (`face_counter.serving.onnx_detector`) never imports
ultralytics at all -- this is the only place in the service path that does
(T6 plan, decision 2026-10-10).

Usage (needs the `analytics` dependency group installed):
    uv run python scripts/export_onnx.py \\
        models/yolo26l-sku110k.pt models/yolo26l-sku110k.onnx --imgsz 1280

Then point `configs/bakeoff.yaml`'s `yolo26l-sku110k.onnx` key at the output
(gitignored like the `.pt`, same as every other model weight in this repo).
"""

from __future__ import annotations

import argparse
from pathlib import Path


def export(weights: Path, out: Path, imgsz: int) -> Path:
    from ultralytics import YOLO

    model = YOLO(str(weights))
    exported = Path(model.export(format="onnx", imgsz=imgsz, simplify=True))
    if exported != out:
        out.parent.mkdir(parents=True, exist_ok=True)
        exported.replace(out)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("weights", type=Path, help="ultralytics .pt weights to export")
    parser.add_argument("out", type=Path, help="output .onnx path")
    parser.add_argument("--imgsz", type=int, default=1280)
    args = parser.parse_args(argv)

    out = export(args.weights, args.out, args.imgsz)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
