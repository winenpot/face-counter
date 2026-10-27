# 2026-10-26 Audit sources

Reading list for the best-practice audit. Checked 2026-10-26: each URL returned HTTP 200 and the title shown on the page matched the listing (arXiv titles come from the abs page; arXiv year is the v1 submission year).

## Detection
- RF-DETR: Neural Architecture Search for Real-Time Detection Transformers — 2025 — preprint — https://arxiv.org/abs/2511.09554 — Real-time DETR-family detector as a modern alternative to YOLO.
- DEIM: DETR with Improved Matching for Fast Convergence — 2024 — preprint — https://arxiv.org/abs/2412.04234 — Faster-converging real-time DETR training.
- Slicing Aided Hyper Inference and Fine-tuning for Small Object Detection (SAHI) — 2022 — preprint (ICIP 2022) — https://arxiv.org/abs/2202.06934 — Tiled inference for small, dense objects.
- Precise Detection in Densely Packed Scenes (SKU-110K) — 2019 — CVPR 2019 — https://arxiv.org/abs/1904.00853 — Benchmark and method for dense shelf detection.
- Rethinking Object Detection in Retail Stores (Locount) — 2020 — AAAI 2021 — https://arxiv.org/abs/2003.08230 — Detection combined with per-box instance counting on shelves.
- AAAI2021 Locount Dataset (GitLab) — 2021 — dataset repo — https://isrc.iscas.ac.cn/gitlab/research/locount-dataset — Locount data. The page sits behind a GitLab sign-in, but it resolves.
- Unitail: Detecting, Reading, and Matching in Retail Scene — 2022 — preprint (ECCV 2022) — https://arxiv.org/abs/2204.00298 — Retail benchmark with quadrilateral detection and product matching.
- chistopat/sku110k-yolo11-object-detector — n/a — Hugging Face model card — https://huggingface.co/chistopat/sku110k-yolo11-object-detector — Public YOLO11 checkpoint trained on SKU-110K.
- GitHub - huy-06/YOLOv8s_SKU110K — n/a — student repo — https://github.com/huy-06/YOLOv8s_SKU110K — Baseline YOLOv8s on SKU-110K (low evidentiary weight).

## Identification
- Bridging the Catalog-to-Real Gap: Scalable Product Recognition via Multi-Stage Contrastive Learning (Cat2Real) — 2026 — preprint — https://arxiv.org/abs/2607.09888 — Contrastive training that bridges catalog images and real shelf crops.
- Trendyol/trendyol-dino-v2.1-ecommerce-256d — n/a — Hugging Face model card — https://huggingface.co/Trendyol/trendyol-dino-v2.1-ecommerce-256d — DINOv2 embedder fine-tuned on e-commerce products.
- Retail-786k: a Large-Scale Dataset for Visual Entity Matching — 2023 — preprint — https://arxiv.org/abs/2309.17164 — Large-scale retail product matching dataset.
- RP2K: A Large-Scale Retail Product Dataset for Fine-Grained Image Classification — 2020 — preprint — https://arxiv.org/abs/2006.12634 — Fine-grained shelf product classification data.
- Exploring Fine-grained Retail Product Discrimination with Zero-shot Object Classification Using Vision-Language Models — 2024 — preprint — https://arxiv.org/abs/2409.14963 — Limits of zero-shot VLMs on similar-looking SKUs.
- What Matters for Grocery Product Retrieval with Open Source Vision Language Models — 2026 — preprint — https://arxiv.org/abs/2605.18029 — Design choices for VLM-based grocery retrieval.
- A deep learning pipeline for product recognition on store shelves — 2018 — preprint — https://arxiv.org/abs/1810.01733 — Detect-then-retrieve pipeline against reference images.
- DINOv2: Learning Robust Visual Features without Supervision — 2023 — preprint (TMLR) — https://arxiv.org/abs/2304.07193 — General-purpose embedding backbone.
- ArcFace: Additive Angular Margin Loss for Deep Face Recognition — 2018 — preprint (CVPR 2019) — https://arxiv.org/abs/1801.07698 — Margin-based metric-learning loss for embeddings.
- Technology (ParallelDots) — n/a — vendor marketing — https://paralleldots.com/technology — Commercial shelf-recognition stack claims.
- InfiView – Unified Shelf Intelligence & Retail Analytics — n/a — vendor marketing — https://infilect.com/solutions/infiview-unified-shelf-intelligence — Commercial shelf-analytics product claims.
- Synthetic Data from a One-Faced Asset | ZIA documentation (Neurolabs) — n/a — vendor docs — https://docs.neurolabs.ai/docs/catalogue-management/synthetic-data — Synthetic training data generated from catalogue images.

## Labeling & evaluation
- Bias in the Loop: How Humans Evaluate AI-Generated Suggestions — 2025 — preprint — https://arxiv.org/abs/2509.08514 — Pre-annotation and AI suggestions bias human reviewers.
- OpenReview forum JxiOoHqbXl — NOT VERIFIED (OpenReview bot challenge, HTTP 403 on the API; title unknown) — https://openreview.net/forum?id=JxiOoHqbXl — not confirmed.
- Evaluating the impact of pre-annotation on annotation speed and potential bias: natural language processing gold standard development for clinical named entity recognition in clinical trial announcements — 2014 — JAMIA — https://pmc.ncbi.nlm.nih.gov/articles/PMC3994857 — Pre-annotation speeds labeling and its bias is measurable. The title was confirmed through web search because the page itself showed a CAPTCHA.
- Soft Sampling for Robust Object Detection — 2018 — preprint (BMVC 2019) — https://arxiv.org/abs/1806.06986 — Training detectors with missing or partial annotations.
- Object Detection Benchmarks are Incomplete: The Role of Label Errors and Annotation Uncertainty — 2026 — preprint — https://arxiv.org/abs/2609.21822 — Label errors distort detection benchmark rankings.
- Noise-Aware Evaluation of Object Detectors — 2025 — WACV 2025 — https://openaccess.thecvf.com/content/WACV2025/html/Llerena_Noise-Aware_Evaluation_of_Object_Detectors_WACV_2025_paper.html — Detector evaluation that accounts for annotation noise.
- Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks — 2021 — preprint (NeurIPS 2021 D&B) — https://arxiv.org/abs/2103.14749 — Test-set label errors can flip model rankings.
- Confidence Intervals for Performance Estimates in Brain MRI Segmentation — 2023 — preprint — https://arxiv.org/abs/2307.10926 — Report confidence intervals on small evaluation sets.
- KαLOS finds Consensus: A Meta-Algorithm for Evaluating Inter-Annotator Agreement in Complex Vision Tasks — 2026 — CVPR 2026 — https://openaccess.thecvf.com/content/CVPR2026/html/Tschirschwitz_KaLOS_finds_Consensus_A_Meta-Algorithm_for_Evaluating_Inter-Annotator_Agreement_in_CVPR_2026_paper.html (arXiv: https://arxiv.org/abs/2603.27197) — Inter-annotator agreement for detection labels.
- Iterative Bounding Box Annotation for Object Detection — 2020 — preprint (ICPR 2020) — https://arxiv.org/abs/2007.00961 — Model-assisted iterative box labeling cuts annotation cost.
- Active Learning for Object Detection with Non-Redundant Informative Sampling (NORIS) — 2023 — preprint — https://arxiv.org/abs/2307.08414 — Picks images that are informative without repeating each other.
- Box-Level Active Detection — 2023 — CVPR 2023 — https://openaccess.thecvf.com/content/CVPR2023/html/Lyu_Box-Level_Active_Detection_CVPR_2023_paper.html (arXiv: https://arxiv.org/abs/2303.13089) — Active learning per box, with labeling budgets counted in boxes.
- Active Learning for Deep Object Detection — 2018 — preprint (WACV 2019) — https://arxiv.org/abs/1809.09875 — Baseline active-learning study for detection.

## Serving & MLOps
- Thread management | onnxruntime — n/a — vendor docs — https://onnxruntime.ai/docs/performance/tune-performance/threading.html — Tuning intra-op and inter-op threads for CPU inference.
- Tutorial: Data and Model Versioning | Data Version Control · DVC — n/a — vendor docs — https://doc.dvc.org/example-scenarios/versioning-data-and-models/tutorial — Versioning datasets and models alongside git.
