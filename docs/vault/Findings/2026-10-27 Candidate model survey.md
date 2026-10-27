# Candidate model survey (2026-10-27)

Two research passes (detectors; identity embedders), each told to mark every
claim's basis. Nothing here has been run on our data; every gain is a guess
until scored on gold. Basis marks: *read* = README/model card/paper section
fetched and searched; *summary* = abstract or snippet; *vendor* = vendor page.
The two headline findings were re-checked by hand (HF API, licence file).

## Headline findings

- **Cat2Real weights are public.** `zhanganyi88/Cat2Real-DINOv3-384` on
  Hugging Face (Apache-2.0, uploaded 2026-06-22, safetensors). The Cat2Real
  approach can be tested as a drop-in embedder before training anything
  (*read*, re-checked).
- **DEIMv2 is no longer a candidate for the service.** Its licence is now a
  custom non-commercial licence (*read*, re-checked), as is its successor
  EdgeCrafter. Original DEIM stays Apache-2.0.
- **No 2025-2026 detector paper reports SKU-110K** (RF-DETR, DEIMv2,
  YOLOv12, YOLOv13 searched). Dense-shelf suitability below is reasoning
  from each method, not a result.

## Detectors: shortlist after RF-DETR (T12)

1. YOLO26-L with the P2 small-object head (`yolo26-p2.yaml`): same toolchain
   and ONNX path; no published P2 weights, so fine-tune from L; memory test
   at 1280 on 8 GB needed.
2. D-FINE-L (or M): most mature DETR codebase, custom-dataset configs, ONNX
   + ONNX Runtime script; 300 queries, configurable.
3. RT-DETRv4-M/L: DINOv3 teacher only during training, so no extra CPU cost;
   COCO L 55.4 vs D-FINE-L 54.0 (README); young repo.
4. DEIM training recipe on D-FINE: changes training only; effect on photos
   that already hold ~150 objects unknown.
5. Free bake-off of extra SKU-110K checkpoints: `hatuankiet/YOLOv12S_SKU110K`
   (no metrics published), `sbfisher/yolov8l-sku110k` (no card).

Not verified: CPU ONNX latency of every DETR at 1280 on our Xeon (only
Ultralytics publishes CPU numbers), LW-DETR COCO AP, RT-DETRv4 query
default, DETR recall at 236 boxes vs a 300-query cap.

## Identity: shortlist, ordered by expected gain per hour

Each scored on the same 225 gold crops vs 65.3% (`runs/match/20261005-184748`).
The embedder is one setting (`DEFAULT_MODEL` in
`src/face_counter/identification/embedder.py`).

1. Cat2Real-DINOv3-384 drop-in (~2 h). Trained for exactly our task shape;
   in-house 80.73% vs 35.53% plain DINOv2-L (paper Table, *read*). ViT-L at
   384 px: likely several times slower on our CPU (*estimate*). Run offline
   first; it also bounds what our own triplet head could gain.
2. Plain DINOv3 ViT-B/16 (~1-2 h). Same size class as today; general
   benchmarks favour DINOv3, no product-retrieval evidence at base size.
3. OCR re-rank of top-k (~4-6 h). The only lever aimed at look-alike
   bottles with different brand text. PP-OCRv5 Arabic-script model lists
   Persian; EasyOCR lists fa. Unitail: text added +1.76-2.75 pts on hard
   cases, +0.56-0.94 overall (English, *read*). Check read rate on our
   small crops first.
4. PE-Core-B16 / SigLIP 2 image-to-image (~2-3 h). Strong in a zero-shot
   grocery benchmark (image-to-text, not our setup; no DINO compared).
5. Trendyol DINOv2.1 e-commerce (~1 h). Product-tuned head, catalog data
   not shelves; low expected gain.

Dropped: VLM re-ranking (too heavy for CPU serving), Marqo e-commerce
(vendor evidence only), EVA-CLIP (only the 18B model is benchmarked).

## Sources

Full source lists with basis marks are in the subagent transcripts
(`~/.hermes/cache/delegation/live/deleg_62722d92/task-0.log`, `task-1.log`;
scratch, pruned after 24 h). Key ones:
- https://huggingface.co/zhanganyi88/Cat2Real-DINOv3-384 (read)
- https://arxiv.org/html/2607.09888 (read in full)
- https://github.com/roboflow/rf-detr (read)
- https://github.com/Intellindust-AI-Lab/DEIMv2 and its LICENSE.md (read)
- https://github.com/Peterande/D-FINE (read)
- https://github.com/RT-DETRs/RT-DETRv4 (read; paper 2510.25257 not read)
- https://docs.ultralytics.com/models/yolo26/ (vendor)
- https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m (read)
- https://arxiv.org/html/2204.00298 Unitail (read, §5.1, Table 4)
- https://arxiv.org/html/2605.18029 grocery VLM retrieval (read)
- https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html (read)
- https://huggingface.co/facebook/PE-Core-B16-224 (read)
- https://huggingface.co/Trendyol/trendyol-dino-v2.1-ecommerce-256d (read)
