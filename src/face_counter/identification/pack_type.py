"""Can vs. glass for crops the matcher doesn't put a pack type on: a rival's
crop carries no pack type until something names its container (PILOT.md step
5; the per-category share needs one for every face, ours or not).

T4's CLIP spike (``scripts/can_vs_glass_spike.py``) confirmed on the gold
validation set (2026-10-05, ``runs/t4_can_vs_glass/20261005-175743/``):
CLIP ViT-L/14, prompts averaged across all three wordings ("ens"), threshold
0 on the glass-minus-can score. Gold rival-box AUC 0.985 / acc@0 93.8%,
matching the test-set exploratory run (AUC 0.932) rather than falling short
of it. Promoted in ``.hermes/plans/2026-10-04_demo-path.md`` T4.

A crop the matcher *did* name (ours or a tracked competitor) already has a
pack type from ``classes.csv`` and never goes through this -- it only applies
to crops below the matcher's threshold that still need a category.
"""
from __future__ import annotations

from PIL import Image

MODEL = "openai/clip-vit-large-patch14"
THRESHOLD = 0.0
PACKS = ("canned", "glass")

# Averaged at inference exactly as scripts/can_vs_glass_spike.py's "ens" key
# does: text-embed every prompt, mean, re-normalise.
PROMPTS = (
    ("a photo of an aluminum drink can", "a photo of a glass bottle"),
    ("a cropped photo of a canned drink on a shelf",
     "a cropped photo of a glass bottled drink on a shelf"),
    ("a metal can of soda", "a glass bottle of soda with a cap"),
)


def _load_model(name: str, device: str):
    from transformers import CLIPModel, CLIPProcessor

    return CLIPProcessor.from_pretrained(name), CLIPModel.from_pretrained(name).to(device).eval()


def score_crops(crops: list[Image.Image], model_name: str = MODEL,
                device: str | None = None) -> list[float]:
    """Glass-minus-can cosine score per crop; > threshold means glass."""
    import torch

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    proc, model = _load_model(model_name, device)

    def feats(out):
        return out if torch.is_tensor(out) else out.pooler_output

    @torch.no_grad()
    def image_emb():
        out = []
        for i in range(0, len(crops), 32):
            x = proc(images=crops[i:i + 32], return_tensors="pt").to(device)
            out.append(torch.nn.functional.normalize(feats(model.get_image_features(**x)), dim=-1).cpu())
        return torch.cat(out) if out else torch.empty(0)

    @torch.no_grad()
    def text_emb(texts):
        x = proc(text=list(texts), return_tensors="pt", padding=True).to(device)
        return torch.nn.functional.normalize(feats(model.get_text_features(**x)), dim=-1).cpu()

    img = image_emb()
    can_e = torch.nn.functional.normalize(
        text_emb([c for c, _ in PROMPTS]).mean(0), dim=0)
    glass_e = torch.nn.functional.normalize(
        text_emb([g for _, g in PROMPTS]).mean(0), dim=0)
    scores = (img @ glass_e - img @ can_e).tolist()
    if device == "cuda":
        torch.cuda.empty_cache()
    return scores


def pack_types(crops: list[Image.Image], model_name: str = MODEL, device: str | None = None,
               threshold: float = THRESHOLD) -> list[str]:
    """"canned" or "glass" per crop, from the promoted zero-shot classifier."""
    return ["glass" if s > threshold else "canned" for s in score_crops(crops, model_name, device)]
