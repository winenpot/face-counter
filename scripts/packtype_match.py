"""T11 step 1: pack-type-constrained nearest-neighbour identity on gold crops."""
import collections
import json
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np

os.environ["CUDA_VISIBLE_DEVICES"] = ""
from face_counter.evaluation import share
from face_counter.identification import embedder, gallery, pack_type
from face_counter.identification.cli import collect_crops
from face_counter.utils.config import (
    DEFAULT_CLASSES,
    DEFAULT_IMAGES_DIR,
    DEFAULT_REPORTING,
    DEFAULT_SCOPE,
)

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data/label_studio/exports/gold-val-2026-10-05.json"
out = ROOT / "runs/match" / f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-packtype"
out.mkdir(parents=True)
T = {}
t0 = time.time()
tax = share.Taxonomy.load(str(DEFAULT_CLASSES), str(DEFAULT_REPORTING), str(DEFAULT_SCOPE))
crops, meta, skipped = collect_crops(LABELS, Path(DEFAULT_IMAGES_DIR), tax)
gal = gallery.build()
glabels = np.array([g.label for g in gal])
gpack = np.array([l.rsplit("_", 1)[1] for l in glabels])
print(len(crops), "crops", len(gal), "gallery", skipped, flush=True)
gE = embedder.embed_paths([g.path for g in gal], device="cpu")
cE = embedder.embed_images(crops, device="cpu")
T["dinov2_s"] = round(time.time() - t0, 1)
sims = cE @ gE.T
np.save(out / "sims.npy", sims)

t1 = time.time()
try:
    clip_scores = pack_type.score_crops(crops, device="cpu")
    pred_pack = ["glass" if s > pack_type.THRESHOLD else "canned" for s in clip_scores]
    T["clip_s"] = round(time.time() - t1, 1)
except Exception as e:  # noqa: BLE001  report, don't fake
    print("CLIP failed:", repr(e)); clip_scores = pred_pack = None

def run(packs):
    rows = []
    for i, m in enumerate(meta):
        s = sims[i].copy()
        if packs is not None:
            s[gpack != packs[i]] = -np.inf
        j = int(np.argmax(s))
        rows.append(glabels[j])
    return rows

variants = {"baseline": run(None), "oracle": run([m["pack"] for m in meta])}
if pred_pack: variants["predicted"] = run(pred_pack)
idx = [i for i, m in enumerate(meta) if m["should_match"]]
truth = {i: f"{meta[i]['brand']}_{meta[i]['pack']}" for i in idx}
res = {"n_crops": len(meta), "n_named": len(idx), "runtime_s": T, "variants": {}}
if pred_pack:
    res["pack_classifier_acc_named"] = sum(pred_pack[i] == meta[i]["pack"] for i in idx) / len(idx)
for k, pred in variants.items():
    hits = sum(pred[i] == truth[i] for i in idx)
    conf = collections.Counter((truth[i], pred[i]) for i in idx if pred[i] != truth[i])
    per = collections.defaultdict(lambda: [0, 0])
    for i in idx:
        per[truth[i]][1] += 1; per[truth[i]][0] += pred[i] == truth[i]
    res["variants"][k] = {"acc": hits / len(idx), "hits": hits,
        "top_confusions": [[a, b, n] for (a, b), n in conf.most_common(10)],
        "per_label": {l: f"{h}/{n}" for l, (h, n) in sorted(per.items())}}
(out / "results.json").write_text(json.dumps(res, indent=1))
with (out / "crops.jsonl").open("w") as f:
    for i, m in enumerate(meta):
        f.write(json.dumps({**m, **{f"pred_{k}": v[i] for k, v in variants.items()},
                            "clip_score": clip_scores[i] if clip_scores else None,
                            "pred_pack": pred_pack[i] if pred_pack else None}) + "\n")
print(json.dumps(res, indent=1)); print("wrote", out)
