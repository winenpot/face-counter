"""DINOv2 image embeddings: one vector per image, L2-normalised so cosine
similarity is a plain dot product.

The same embedding space for every embed_* call (gallery packshots, labeled
crops, inference crops) is the whole point: a gallery's vectors and a crop's
vector are only comparable when the same model produced both (DINOv2 over
CLIP here, matching the identity-pass design in LABELING_STRATEGY.md §3, "the
same embedding the stage-2 matcher uses").

Heavy imports (torch, transformers) are deferred into functions so this
module imports instantly for tests, which monkeypatch ``_load_model``.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

DEFAULT_MODEL = "facebook/dinov2-base"


def load_image(path: Path) -> Image.Image:
    """Pixels as a shelf photo would display them: EXIF-oriented, RGB."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def _load_model(name: str, device: str):
    from transformers import AutoImageProcessor, AutoModel

    proc = AutoImageProcessor.from_pretrained(name)
    model = AutoModel.from_pretrained(name).to(device).eval()
    return proc, model


def embed_images(images: list[Image.Image], model_name: str = DEFAULT_MODEL,
                 device: str | None = None, batch_size: int = 32):
    """L2-normalised embeddings, one row per image, as an (N, D) array."""
    import torch

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    proc, model = _load_model(model_name, device)

    @torch.no_grad()
    def run():
        out = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            x = proc(images=batch, return_tensors="pt").to(device)
            feats = model(**x).pooler_output
            out.append(torch.nn.functional.normalize(feats, dim=-1).cpu())
        return torch.cat(out) if out else torch.empty(0)

    embs = run()
    if device == "cuda":
        torch.cuda.empty_cache()
    return embs.numpy()


def embed_paths(paths: list[Path], model_name: str = DEFAULT_MODEL, device: str | None = None,
                batch_size: int = 32):
    """Convenience: load then embed. One bad file stops the run with its path,
    not a stack trace pointing at PIL internals."""
    images = []
    for p in paths:
        try:
            images.append(load_image(p))
        except Exception as e:
            raise ValueError(f"could not open {p}: {e}") from e
    return embed_images(images, model_name=model_name, device=device, batch_size=batch_size)
