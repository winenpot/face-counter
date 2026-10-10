---
type: findings
date: 2026-10-10
---

# 2026-10-10 Serving investigation

Everything measured while building and deploying the T6 demo API, in one
place. Method is noted per row; "est." marks a number that was not measured.
Related notes: [[Serving pipeline]], [[Demo API on the apps server]],
[[Environments and dependency groups]], [[Open issues (serving)]].

## Machines

| Box | CPU | Notes |
|---|---|---|
| Laptop | MX330 GPU unusable for torch convs | CPU-only work, tests |
| hemin | i5-13600K, RTX 4060 Ti, AVX2 + AVX-VNNI | torch `2.14.0+cu130`, CUDA working; often off |
| Apps server (ssh alias `atpg`) | Xeon E5-2680 v4, 8 vCPU, AVX2 + FMA, **no AVX-512, no VNNI** | 15 GB RAM, ~32 containers including the production MongoDB primary |

## Latency and memory

| What | Where | Result | How measured |
|---|---|---|---|
| ONNX detector, 44-unit photo | hemin CPU | 716-753 ms | `onnx_detector.build`, warm, 3 runs |
| ONNX detector, same photo | apps server, container, 2 threads | **4.8-5.8 s** | `/count` x3 (an earlier est. of 2-3 s was wrong) |
| CLIP ViT-L/14 forward pass, 44 crops | hemin CPU | 15.2 s | warm model, `get_image_features` |
| CLIP model load | hemin | 4.4 s, **on every call** | `pack_type.score_crops` calls `_load_model` each time |
| Full pipeline with CLIP | hemin CPU | 24.6 s per photo | `/count` timings |
| CLIP-only process RSS | hemin | 720 MB after imports → 779 MB after load → **2019 MB after first inference**, never released | `/proc/self/status` at checkpoints |
| Detector-only process RSS, ORT arena on | hemin | 65 MB imports → 307 MB session → **1439 MB after 2 requests** | same |
| Detector-only process RSS, ORT arena off | hemin | 307 → **~330 MB idle, 823 MB peak**, about +3% latency | same, now the default (`onnx_detector.py:76`) |
| Demo container | apps server | 277 MiB idle, **978 MiB cgroup peak** (1200 MiB cap) | `docker stats`, `memory.peak` |
| Idle CPU of a loaded model | hemin | ~0% | `ps` %CPU is a lifetime average and misleads; idle confirmed over a 15 s window |

## Accuracy

| What | Boxes | n | Result | Majority-class floor |
|---|---|---|---|---|
| CLIP ViT-L/14 can vs glass (T4) | human-labelled | 145 rivals | AUC 0.985, 93.8% | 81.9-82.1% (only 26 rival cans) |
| Box shape h/w ≥ 3.37 | human-labelled | 245 / 145 | AUC 0.960 / 0.952, 94.3% / 93.8%, threshold fitted on the same set | 65.7% / 82.1% |
| Box shape h/w ≥ 3.37 | **detector**, IoU ≥ 0.5 to gold | 236 / 138 | AUC 0.936 / 0.929, **87.3% / 86.2%** | 65.7% / 81.9% |
| CLIP on detector boxes | — | — | **never measured** (issue #2) | — |
| ONNX vs `.pt` detector scores | detector | 3 normal photos | top-3 scores within a few points, same boxes | — |

The gold export is `gold-val-2026-10-05.json`, sha256 `44e316ae…`, used
read-only. The frozen test set was not touched.

## Things that turned out different from what was assumed

- The ONNX export outputs a raw `(1, 4+nc, A)` grid, `(1, 5, 33600)` here,
  with **no NMS** applied; the plan had assumed `(1, N, 6)`. Fixed in
  `onnx_detector.py:54` (NMS) and `:120` (decode).
- Detector memory is dominated by ONNX Runtime's CPU arena, not the model;
  turning the arena off cut ~1.1 GB.
- On the apps server, `free` looked tight (1.7 GB) but `available` was about
  10 GB; the gap is page cache. That headroom is real, but MongoDB benefits
  from the cache, so treat it as soft.
- A plain PyPI `torch` wheel on Linux pulls the full CUDA stack. Pinning a CPU
  index in the shared `pyproject.toml` would have replaced hemin's CUDA torch;
  reverted. See [[Environments and dependency groups]].
- `files.pythonhosted.org` was unreachable from hemin while the PyPI index
  answered. The apps server reached PyPI, Docker Hub and GitHub fine (issue #5).

## Corrections to statements made during the session

- Test counts of 222/224 were wrong. The suite had 200 tests before the work,
  211 after the classifier switch, and 213 after the session-options tests.
- Issue #4 ("ultralytics in the dev group") was filed in error and closed: a
  misread of two `sed` ranges printed back to back. `dev` holds only httpx,
  mongomock, pytest and ruff.
- The "~0.3 GB detector" figure was a guess; measured, it was 1.44 GB until
  the arena fix.
