"""T4 spike: can vs glass on labeled crops with zero-shot CLIP. Read-only on the labels.

Why: the pilot reports share per category (canned vs glass). Our own SKUs carry their
pack type in their class, but a rival crop is only a box until something names its pack.
This measures how well a text-only match ("a metal can" vs "a glass bottle") can do it,
per model size and prompt wording, before anything is built around it.

    uv run python scripts/can_vs_glass_spike.py                       # 3 CLIP sizes, GPU if any
    uv run python scripts/can_vs_glass_spike.py --models openai/clip-vit-base-patch32 --device cpu

Reads the frozen v1 export (never writes it) and the RAW photos (default
data/raw/images; boxes are re-oriented with EXIF exactly as Label Studio showed them, and a
photo whose size disagrees with the export is skipped and counted, never rescaled).
Writes runs/t4_can_vs_glass/<timestamp>/{results.json,crops.jsonl}; runs/ is gitignored and
travels with scripts/sync_from_hemin.sh.

READ THE NUMBERS AS EXPLORATORY: they are measured on the frozen test photos, so picking a
prompt or threshold here is selection on the test set. The choice is confirmed on the gold
validation set (T2) before it goes anywhere near the demo number.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from face_counter.evaluation import ls_export
from face_counter.utils.config import DEFAULT_IMAGES_DIR, DEFAULT_SCOPE

register_heif_opener()
log = logging.getLogger("t4")

DEFAULT_LABELS = "data/label_studio/exports/pilot-test-v1-2026-09-30.json"
DEFAULT_MODELS = ("openai/clip-vit-base-patch32", "openai/clip-vit-base-patch16",
                  "openai/clip-vit-large-patch14")
PACKS = {"canned": "can", "glass": "glass"}
MIN_SIDE = 12  # px; smaller boxes are noise for a classifier

# (can wording, glass wording). "ens" averages all of them.
PROMPTS = {
    "A": ("a photo of an aluminum drink can", "a photo of a glass bottle"),
    "B": ("a cropped photo of a canned drink on a shelf",
          "a cropped photo of a glass bottled drink on a shelf"),
    "C": ("a metal can of soda", "a glass bottle of soda with a cap"),
}


def auc(scores: list[float], is_glass: list[int]) -> float:
    """P(a random glass crop scores above a random can crop); ties count half."""
    pos = [s for s, g in zip(scores, is_glass) if g]
    neg = [s for s, g in zip(scores, is_glass) if not g]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def summarize(scores: list[float], is_glass: list[int]) -> dict:
    """score > 0 means 'glass'. acc0 is the untuned zero-shot decision."""
    pred = [int(s > 0) for s in scores]
    cm = collections.Counter(zip(is_glass, pred))
    n = len(is_glass)
    return {"n": n, "acc0": (cm[(0, 0)] + cm[(1, 1)]) / n if n else float("nan"),
            "auc": auc(scores, is_glass), "can_as_can": cm[(0, 0)], "can_as_glass": cm[(0, 1)],
            "glass_as_glass": cm[(1, 1)], "glass_as_can": cm[(1, 0)]}


def _open(images_dir: Path, name: str) -> Image.Image | None:
    p = images_dir / Path(name).name
    if not p.exists():
        hits = sorted(images_dir.glob(Path(name).stem + ".*"))
        if not hits:
            return None
        p = hits[0]
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def collect_crops(labels: Path, images_dir: Path, ours: set[str]):
    """Return (crops, meta, skipped): one crop per can/glass-named box of every photo."""
    crops, meta, skipped = [], [], collections.Counter()
    for ph in ls_export.load(labels):
        im = _open(images_dir, ph.file_name)
        if im is None:
            skipped["missing"] += 1
            continue
        if abs(im.width - ph.width) > 1 or abs(im.height - ph.height) > 1:
            log.warning("%s: image is %dx%d, export says %dx%d; skipped", ph.file_name,
                        im.width, im.height, ph.width, ph.height)
            skipped["size_mismatch"] += 1
            continue
        for b in ph.boxes:
            brand, _, pack = b.label.rpartition("_")
            if pack not in PACKS:
                continue
            x1, y1, x2, y2 = b.xyxy
            if x2 - x1 < MIN_SIDE or y2 - y1 < MIN_SIDE:
                continue
            crops.append(im.crop((max(x1, 0), max(y1, 0), min(x2, im.width), min(y2, im.height))))
            meta.append({"photo": ph.file_name, "label": b.label, "truth": PACKS[pack],
                         "ours": brand in ours})
    return crops, meta, dict(skipped)


def score_model(name: str, crops: list[Image.Image], device: str) -> dict[str, list[float]]:
    """Per prompt set: glass-minus-can cosine score for every crop (> 0 = glass)."""
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained(name).to(device).eval()
    proc = CLIPProcessor.from_pretrained(name)

    def feats(out):
        return out if torch.is_tensor(out) else out.pooler_output

    @torch.no_grad()
    def image_emb():
        out = []
        for i in range(0, len(crops), 32):
            x = proc(images=crops[i:i + 32], return_tensors="pt").to(device)
            out.append(torch.nn.functional.normalize(feats(model.get_image_features(**x)), dim=-1).cpu())
        return torch.cat(out)

    @torch.no_grad()
    def text_emb(texts):
        x = proc(text=list(texts), return_tensors="pt", padding=True).to(device)
        return torch.nn.functional.normalize(feats(model.get_text_features(**x)), dim=-1).cpu()

    img = image_emb()
    scores = {}
    for key, (can_t, glass_t) in PROMPTS.items():
        t = text_emb([can_t, glass_t])
        scores[key] = (img @ t[1] - img @ t[0]).tolist()
    can_e = torch.nn.functional.normalize(text_emb([c for c, _ in PROMPTS.values()]).mean(0), dim=0)
    glass_e = torch.nn.functional.normalize(text_emb([g for _, g in PROMPTS.values()]).mean(0), dim=0)
    scores["ens"] = (img @ glass_e - img @ can_e).tolist()
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    return scores


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--labels", default=DEFAULT_LABELS)
    ap.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR))
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--device", default=None, help="default: cuda if available, else cpu")
    ap.add_argument("--out-dir", default=None, help="default: runs/t4_can_vs_glass/<timestamp>")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # one line per HF file otherwise

    import torch
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    labels = Path(args.labels)
    ours = set(yaml.safe_load(Path(DEFAULT_SCOPE).read_text(encoding="utf-8"))["brands"])
    crops, meta, skipped = collect_crops(labels, Path(args.images_dir), ours)
    truth = [m["truth"] for m in meta]
    log.info("device=%s crops=%d (%s) skipped photos=%s", device, len(crops),
             dict(collections.Counter(truth)), skipped or "none")
    if not crops:
        raise SystemExit("no crops: check --labels and --images-dir")

    y = [int(t == "glass") for t in truth]
    rival = [i for i, m in enumerate(meta) if not m["ours"]]
    results, all_scores = [], {}
    for name in args.models.split(","):
        scores = score_model(name, crops, device)
        for key, s in scores.items():
            all_scores[f"{name}|{key}"] = s
            for subset, idx in (("all", range(len(y))), ("rivals", rival)):
                idx = list(idx)
                r = summarize([s[i] for i in idx], [y[i] for i in idx])
                results.append({"model": name, "prompts": key, "subset": subset, **r})
                if subset == "rivals":
                    by = collections.defaultdict(lambda: [0, 0])
                    for i in idx:
                        by[meta[i]["label"]][0] += 1
                        by[meta[i]["label"]][1] += int((s[i] > 0) == bool(y[i]))
                    results[-1]["per_label_acc"] = {k: round(v[1] / v[0], 3) for k, v in sorted(by.items())}
        log.info("%s done", name)

    print(f"\n{'model':32s} {'prompts':7s} {'subset':6s} {'n':>4s} {'acc@0':>6s} {'AUC':>6s}  "
          "can->glass  glass->can")
    for r in results:
        print(f"{r['model'].split('/')[-1]:32s} {r['prompts']:7s} {r['subset']:6s} {r['n']:4d} "
              f"{r['acc0']:6.3f} {r['auc']:6.3f}  {r['can_as_glass']:10d}  {r['glass_as_can']:10d}")
    best = max((r for r in results if r["subset"] == "rivals"), key=lambda r: r["auc"])
    print(f"\nbest rival AUC: {best['model']} / {best['prompts']}  AUC={best['auc']:.3f}  "
          f"acc@0={best['acc0']:.3f}\nper label (rival boxes, accuracy at 0):")
    for k, v in best["per_label_acc"].items():
        print(f"  {k:24s} {v:.2f}")

    out = Path(args.out_dir or f"runs/t4_can_vs_glass/{datetime.now():%Y%m%d-%H%M%S}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({
        "labels": str(labels), "labels_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
        "device": device, "skipped_photos": skipped, "n_crops": len(crops), "results": results,
        "note": "measured on the frozen test photos: exploratory, confirm on the gold set (T2)",
    }, indent=1), encoding="utf-8")
    with (out / "crops.jsonl").open("w", encoding="utf-8") as f:
        for i, m in enumerate(meta):
            f.write(json.dumps({**m, "scores": {k: round(v[i], 5) for k, v in all_scores.items()}}) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
