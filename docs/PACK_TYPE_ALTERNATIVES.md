# Pack-type (canned vs glass) classifier: alternatives to CLIP ViT-L/14

Status: survey plus two measurements, 2026-10-10. The serving default runs
**without** this stage (`FACE_COUNTER_CLASSIFY=0`, see
`src/face_counter/serving/pipeline.py`), so nothing here blocks the demo.
This document exists so the stage can return as a decision backed by numbers.

## What the stage has to do, and what it costs today

The detector finds products; it does not know a can from a bottle. The
pilot reports share per category (canned drinks vs glass drinks), so every
box that is not already named by the matcher needs a pack type. T4 promoted
zero-shot CLIP ViT-L/14. It compares each crop's image embedding with two
text embeddings, "a can" and "a glass bottle", averaged over three wordings.

On CPU that choice is expensive. A 44-crop photo takes about 15 s of forward
pass on hemin's i5-13600K. The process holds about 2 GB once warm, and
`pack_type.score_crops` reloads the model from disk on every call (another
4.4 s). The task itself is coarse: a binary decision about the material of
an object that already fills its crop. A 428M-parameter vision-language model
is the general-purpose tool applied to a narrow problem.

## How much the 93.8% actually tells us

Read the existing number before comparing anything against it.

- **Small, imbalanced set.** The gold validation set has 245 can/glass crops.
  Of these, 145 are rivals, and only 26 rival crops are cans. Guessing "glass"
  for every rival crop already scores 81.9%. The 93.8% headline is about 12
  points above that floor. With 26 minority-class examples, the uncertainty
  on can recall is large. Report can recall and a bootstrap interval, not one
  accuracy number.
- **Human boxes, not detector boxes.** `scripts/can_vs_glass_spike.py` crops
  the *labelled* boxes. The serving path feeds the classifier *detector*
  boxes, which are looser, clipped by occlusion, and sometimes cover two
  units. CLIP has never been measured on the input it gets in production. The
  box-shape baseline below lost about 7 points making exactly that move.

Any replacement is judged on detector boxes, on gold photos, against both
the majority-class floor and CLIP's own detector-box number. That number has
to be measured first.

## Measured: box shape alone (zero ML)

Cans are squat and bottles are tall, so a box's height-to-width ratio is a
free feature. Measured on the gold export (sha256 `44e316ae…`, the same file
as T4's gold run):

| Boxes | Subset | n | AUC | Accuracy (h/w ≥ 3.37) | Majority-class floor |
|---|---|---|---|---|---|
| Labelled (human) | all | 245 | 0.960 | 94.3%, threshold fitted on this set | 65.7% |
| Labelled (human) | rivals | 145 | 0.952 | 93.8%, threshold fitted on this set | 82.1% |
| Detector, IoU ≥ 0.5 to a gold box | all | 236 | 0.936 | 87.3%, threshold carried over | 65.7% |
| Detector, IoU ≥ 0.5 to a gold box | rivals | 138 | 0.929 | 86.2%, threshold carried over | 81.9% |

On human boxes, shape alone ties CLIP's headline. On detector boxes it falls
to about 4 points above "always glass" for rivals. **Verdict: not a
replacement on its own.** It is a free, strong feature to add to any learned
classifier, and it is the baseline every candidate must beat. Scripts used
are in the 2026-10-10 session record; they read only the gold export and
never write it.

## Candidates

They are ordered by how cheaply each can be tried, not by expected accuracy.
Published speed claims are the authors' own and are mostly measured on
phones or GPUs. None has been measured on this project's crops yet.

**1. Smaller zero-shot CLIP-family models, same harness.** These need no
labels and no training, just a gold-set run. One deployment point applies to
all of them: in zero-shot mode the two text embeddings never change, so they
can be computed once and stored. Serving then needs only the *image tower*,
exported to ONNX. That runs in the `serve` environment with no torch, the
same rule the detector already follows.

- *TinyCLIP* (Microsoft; arXiv 2309.12314). Distilled CLIP checkpoints, from
  ViT-8M/16 to ViT-61M/32. They load with `transformers.CLIPModel`
  (`wkcn/TinyCLIP-ViT-8M-16-Text-3M-YFCC15M` and siblings), so
  `can_vs_glass_spike.py --models …` should run them unchanged. That load is
  not yet verified. The 8M image tower is about 50x smaller than ViT-L/14's.
- *OpenAI CLIP ViT-B/32* (151M total). Already in the spike's defaults. On
  the exploratory test-set run (20261004) it scored rival AUC 0.914 against
  0.932 for ViT-L/14. It has not been run on gold.
- *MobileCLIP2* (Apple; arXiv 2508.20691). A family built for low latency;
  S0 is reported at OpenAI B/16 zero-shot quality with 4.8x lower latency
  and 2.8x fewer parameters. It ships in `open_clip` format, so it needs a
  loader branch in the spike and a new dependency in the `analytics` group.
- *SigLIP 2* (Google; arXiv 2502.14786). Its vision towers come in ViT-B
  (86M) up to g (1B), and the B/16 tower is reported to beat SigLIP 1 at the
  same size. It loads through `transformers.AutoModel` and needs a loader
  branch, because its sigmoid scoring differs from CLIP's softmax.

**2. Linear probe on embeddings the pipeline already computes.** The debug
path embeds every crop with DINOv2-base for the matcher. A logistic
regression on those vectors, plus box shape, would add near-zero cost in
that path. It needs pack-type labels for *training*, and those must come
from the labelling batches (`data/splits/label_batch_*`). The gold set
validates; the frozen test set is never used.

**3. Distil CLIP into a small supervised model.** Use ViT-L/14 once, on
hemin's GPU, as a teacher that labels thousands of unlabelled detector crops.
Then train a MobileNetV3-Small or EfficientNet-B0-class network on its soft
labels plus box shape. Models that size typically need milliseconds per crop
on CPU and tens of MB of memory, and they export to ONNX. Expect it to land
near the teacher's accuracy, not above it. This is a training task with its
own plan, not a config change.

**4. Fold pack type into the detector.** When the detector is fine-tuned on
the project's own labels, give it `canned` / `glass` / `product` classes, and
the separate stage disappears. This is the end state. It rides on detector
fine-tuning, which is already on the roadmap.

**Not recommended: int8 quantization of ViT-L/14 for atpg.** atpg's CPU has
no VNNI instructions (AVX2 and FMA only), so int8 kernels lose their speed-up
and can even run slower. See `SERVING_STRATEGY.md` §1.

## Proposed order

1. Add a `--boxes detector` mode to `can_vs_glass_spike.py` (crop matched
   detector boxes instead of label boxes). Re-measure ViT-L/14 there. That
   gives the real baseline, along with can recall and a bootstrap interval.
2. Same run for TinyCLIP 8M/39M and CLIP B/32 (harness-compatible), then
   MobileCLIP2-S0 and SigLIP 2 B/16 after adding loaders. Each image tower
   is timed on CPU as an ONNX export, not as a torch model.
3. Selection rule: beat the box-shape baseline and the majority floor on
   detector-box rival AUC, with can recall reported. Then pick the cheapest
   model within the interval of the best.
4. Serve the winner as an ONNX image tower plus two stored text vectors.
   Turn the stage back on only after that.
5. Distillation and detector folding stay on the longer roadmap.

## Sources

- TinyCLIP: Wu et al., *TinyCLIP: CLIP Distillation via Affinity Mimicking
  and Weight Inheritance*, ICCV 2023, arXiv 2309.12314; checkpoints on the
  Hugging Face Hub under `wkcn/`.
- MobileCLIP2: Faghri et al., *MobileCLIP2: Improving Multi-Modal Reinforced
  Training*, arXiv 2508.20691; checkpoints under `apple/MobileCLIP2-*`.
- SigLIP 2: Tschannen et al., *SigLIP 2: Multilingual Vision-Language
  Encoders…*, arXiv 2502.14786.
- CLIP: Radford et al., *Learning Transferable Visual Models From Natural
  Language Supervision*, ICML 2021, arXiv 2103.00020.
- Project measurements: `runs/t4_can_vs_glass/20261004-185614/` (exploratory,
  test set) and `runs/t4_can_vs_glass/20261005-175743/` (gold); the box-shape
  numbers above (gold, 2026-10-10).
