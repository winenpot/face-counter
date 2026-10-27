# face-counter: status report for the technical director

Date: 2026-10-27. Project start: 2026-09-21 (5 weeks). Author: project owner.
DRAFT. Numbers are measured unless marked *estimate*. Sources for every
number are in `docs/PILOT.md` (Current checkpoint) and `docs/vault/Findings/`.

## 1. Bottom line

- **Feasible, not yet delivered.** Finding and counting products on shelf
  photos works. Naming them (our brand vs a tracked rival) does not yet work
  well enough to report share of shelf.
- **The blocker is identification accuracy (65.3%), not infrastructure or
  serving.** The fix is known in the literature (train the embedder on our
  own labeled shelf crops) and the labeling now under way produces that data.
- **Main risks:** label quality from the new labelers, a test set that does
  not yet match the metric we report, and dependence on one GPU PC.
- **Decisions needed:** see section 9.

## 2. What the system is

Shelf photo -> **detector** (finds every front-facing product) ->
**identifier** (names brand + pack: can or glass) -> share per category:
`ours / (ours + 7 tracked rivals)`, cans and glass bottles reported
separately. Pilot brands: Kix-Max and TorshX.

## 3. Where each part stands

| Part | Status | Measured result | Verdict |
| --- | --- | --- | --- |
| Detector (published SKU-110K weights, not yet fine-tuned) | Working | Recall ~0.87 on 30 frozen test photos (all-object labels) | Good enough to start; fine-tuning pending |
| Can vs glass | Working | AUC 0.985, 93.8% accuracy on gold (human-drawn boxes) | Good; not yet measured on detector boxes |
| Brand + pack identification (on human-drawn boxes) | Weak | 65.3% (147/225 named gold crops, 27 photos; ~59-72% naive 95% interval) | **Blocker** |
| Predicted share vs truth (test set v1) | Not usable | Cans -37.6 pp, glass -26.9 pp | Follows from identification |
| Ground-truth share (labels, not model) | Available | Cans 58.2%, glass 24.0% (wide confidence intervals, 30 photos) | Usable as a manual baseline |
| API service | Deployed (demo) | ~5 s/photo on CPU, 978 MiB peak under a 1,200 MiB cap | Works; counts only, brand share hidden |

Estimated completeness *(estimate)*: pilot/demo ~65%, full roadmap ~25%.

## 4. Annotation progress (to 2026-10-27 06:00)

- 5 training batches of 250 photos (1,250). **337 annotations on 332 photos
  (27%)** in 4 working days by 3 labelers. Batch-04 not started.
- Pace ~110 photos/day; remaining ~920 photos is **8-9 working days**
  *(estimate)*. Labeler time so far ~27 hours; remaining ~75 hours
  *(estimate, median 4.8 min/photo; one labeler takes ~15 min)*.
- Quality:
  - 15 photos submitted with no edits to the machine's pre-drawn boxes
    (14 from one labeler); being sent back.
  - Labelers delete 24-31% of pre-drawn boxes vs 23% in the owner's own
    reference labeling. Whether those deletions are correct is
    **not measurable yet**; that needs hidden reference photos in each batch
    (decision in section 9).
  - 4 photos carry duplicate submissions; cleaned before training.
- Do we need all 10,000 photos? **No.** The model starts from a detector
  already trained on shelves; the plan expects 300-600 photos to reach
  diminishing returns *(estimate, unmeasured)*. The first training round
  measures it.

## 5. Costs

| Item | Spent so far | Next 4-6 weeks *(estimate)* |
| --- | --- | --- |
| Engineering | 1 person, 5 weeks | Same |
| Labeling | ~27 labeler-hours | ~75 more for the current 1,250 photos |
| GPU compute | Colleague's 4060 Ti PC (handover pending) | Same PC; no cloud spend planned |
| Servers | Shared apps server (container capped at 1.2 GB RAM) | Same, or a dedicated box (section 6) |
| Licences | None (all open source: Label Studio Community, ONNX Runtime, DINOv2) | None; Ultralytics is AGPL, kept out of the served process by design |
| Purchases | None | None (GPU PC has ~5 TB storage) |

No vendor quote yet; outsourcing labeling was scoped (RFP) but not priced.

## 6. Infrastructure limits

- **GPU:** one consumer GPU PC (RTX 4060 Ti), the only machine with all
  photos (~30 GB) and the model weights. It is being handed over; single
  point of failure until backed up. The owner's laptop cannot run training.
- **Serving host:** shared production apps server (8 vCPU Xeon E5-2680 v4,
  15 GB RAM, ~30 containers incl. the production MongoDB). No VNNI, so
  quantization gives no speed-up; ~5 s/photo. Fine for a demo and for
  batch processing; not for many concurrent users.
- **No SSH to the db server** (the originally planned host).
- **Exposure:** the demo API is public on plain HTTP with a shared key
  (deliberate, for demos). Needs a key rotation and a TLS front door
  before wider use.
- **Labeling tool:** Label Studio Community has no review workflow,
  assignment, or agreement statistics; quality control is scripted by us.
- **Network:** some package and model downloads are blocked from company
  machines (issue #5); the GPU PC's environment was hand-patched.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Identification stays below a usable level | Medium | Share of shelf cannot be reported | Train embedder on our labeled crops (one-day experiment first) |
| Label quality from new labelers | High (already seen) | Model learns to miss products | Hidden reference photos per batch, bounce unedited work |
| Test labels count every object, metric counts front faces only | Certain until fixed | Reported recall not comparable | Face audit (v2 labels); needs BI's definition answers |
| Served model differs from the scored one (export path) | Unknown | Headline number may not hold in production | Parity test on the GPU PC (about a day) |
| GPU PC handover / data loss | Medium | Weeks lost | Back up photos, weights, runs on handover day |
| 30-photo test set | Certain | Wide confidence intervals; small changes not meaningful | Report intervals; grow gold set later |
| Inference load on the shared prod server | Low (capped) | Slower apps / MongoDB | Memory cap, low CPU share; move to own box if volume grows |
| Counts not stored with store/time | Certain today | BI cannot use outputs | Persistence + metadata (issue #7) before production |

## 8. Comparisons (for orientation, not like-for-like)

| Reference | Number | Caveat |
| --- | --- | --- |
| Commercial vendors (Infilect, ParallelDots) | 95-97% SKU accuracy | Marketing figures, protocol unstated, after per-category onboarding with in-domain data |
| Cat2Real (Walmart, 2026 preprint) | 80.7% top-1 across 2,155 products; off-the-shelf DINOv2 only 35.5% | Trained on ~197k labeled shelf crops on an A100; different, much larger task |
| Us | 65.3% across ~16 brand+pack classes, untrained embedder | Small gold set (225 crops); no fine-tuning yet |
| SKU-110K public detectors | Recall ~0.84-0.87 on their own benchmark | Ours ~0.87 on our photos, before fine-tuning |

Reading: our detector is at the public state of the art for this kind of
model; our identifier is where an untrained one is expected to be. Every
serious system gets past it by training on its own labeled shelf crops.

## 9. Decisions requested

1. Approve hidden reference photos in the labeling batches (per-labeler
   accuracy).
2. Order of work: fix measurement and identification **before** the
   management demo (recommended), or demo product counts now with brand
   share marked as not ready.
3. GPU PC: handover date, and approval to back it up before anything else.
4. Where production serving lives (shared apps server vs db server vs a
   dedicated box) and a TLS front door.
5. BI's answers on the face definition (blocks the v2 test labels).

## 10. Next 4 weeks *(estimate)*

| Week | Work | Exit criterion |
| --- | --- | --- |
| 1 | GPU PC takeover and backup; labeling hygiene; key rotation | Tests pass on the PC; each labeler has an accuracy score |
| 2 | Export parity test; tuning; face audit if BI has answered | One defensible detector number |
| 2-3 | First detector fine-tune on cleaned batches | First learning-curve point |
| 3-4 | Identification: pack filter (ceiling 74%), shelf crops in galleries, trained embedder | Identity accuracy on gold vs 65.3% |
| 4+ | Demo with share and error bars; production hosting decision | Director sign-off |
