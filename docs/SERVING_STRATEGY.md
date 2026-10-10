# Serving strategy: from a synchronous demo API to a queue-backed counting pipeline

Status: proposal, 2026-10-10. Nothing here is implemented yet beyond the
synchronous FastAPI service from T6 (`src/face_counter/serving/`). Decisions
still open are listed in the last section.

## 1. What the measurements say

The T6 smoke run on hemin, plus a follow-up memory probe, gave these numbers
for one shelf photo with 44 detected units. Unmeasured figures are marked as
estimates.

| Stage | hemin CPU (i5-13600K) | atpg CPU (Xeon E5-2680 v4) | hemin GPU (RTX 4060 Ti) |
|---|---|---|---|
| ONNX detector | 737 ms | unmeasured, est. 2-3 s | not used (ONNX on CPU) |
| CLIP ViT-L/14 model load | 4.4 s (repeated on every request today) | unmeasured | unmeasured |
| CLIP forward pass, 44 crops | 15.2 s | unmeasured, est. 40-60 s | unmeasured, expected well under 1 s |
| Resident memory once warm | ~2.3 GB total (CLIP ~0.8-2.0 GB, detector 1.44 GB); detector alone ~0.33 GB with the ONNX memory arena off | same model, same footprint | GPU memory instead of RAM for weights |

Two of these numbers matter more than the rest.

The first is the memory floor. `transformers` loads weights lazily, so a
CLIP-only process sits at ~780 MB after `from_pretrained` and jumps to
~2.0 GB on the first forward pass. It never gives that memory back while the
process lives. CPU use between requests is genuinely zero; the cost of keeping
the model "always on" is RAM, not CPU.

The detector has a floor of its own, and it is mostly not the model. A
detection-only process measured on hemin uses 65 MB after imports and 307 MB
once the ONNX session exists. It then grows to 1.44 GB within two requests,
because ONNX Runtime's CPU memory arena keeps every activation buffer for
reuse. With `enable_cpu_mem_arena` and `enable_mem_pattern` off, it idles at
~330 MB and peaks at 823 MB during a request. The cost is ~20 ms more per
photo (~3%). This is the cheapest memory fix in the system and is not applied
yet.

The second is that atpg is the wrong place to hold that floor permanently. It
runs 32 containers, including the production MongoDB primary, with about
1.7 GB of truly free memory. Its CPU has AVX2 and FMA but no AVX-512 and no
VNNI. That last point removes an optimisation that looks attractive on paper:
int8 quantization gets its CPU speed-up from VNNI integer kernels, and
without them the quantize/dequantize overhead can make inference *slower*.
hemin has AVX-VNNI, so a quantization benchmark run there would not transfer
to atpg.

## 2. Reframing the requirement

The consumer of these counts is the BI team, and a day-old count is
acceptable to them. That makes this a batch or asynchronous workload, not an
online one. A synchronous endpoint makes the uploader wait for the model and
sizes the server for peak load. Its failure mode is also wrong here: if the
process dies mid-request, the count is lost.

The longer-term goal still matters: near-real-time counts feeding an OLAP
store, where no submitted photo is ever lost. Both goals point the same way.
Separate **accepting a photo** (cheap, always on, must never lose data) from
**counting it** (heavy, can run late, can run elsewhere, can be retried).
Batch, near-real-time and real-time then differ only in how often workers run
and how many there are. The architecture does not change.

## 3. Target shape

```
 uploader ──► intake API (atpg, no ML deps, ~100 MB)
                │ 1. store photo bytes, id = sha256(bytes)
                │ 2. insert job {photo_sha, status: pending, metadata}
                │ 3. reply 202 Accepted + job id
                ▼
          durable job store  ◄──── workers PULL jobs (outbound connection only)
                │                  ├─ hemin: GPU, batch, when it is on
                │                  └─ atpg: CPU, night window, memory-capped, exits after
                ▼
          results (append-only, keyed by photo_sha + model_version)
                ▼
          BI read model (daily export now; OLAP + dashboards later)
```

The properties that make this professional rather than a demo:

- **Never lost.** An upload is acknowledged only after the photo bytes and
  the job record are both durably written. Everything downstream can crash
  and be retried.
- **Idempotent.** The photo id is the sha256 of its bytes, and a result's key
  is `(photo_sha, model_version)`. A re-upload, a redelivered job or a worker
  crash after writing cannot produce a duplicate count. Queues deliver *at
  least once*; idempotent writes are what turn that into effectively
  *exactly once* results.
- **Pull-based workers.** Workers open the connection, so hemin, which is
  often off and sits behind someone else's network, can drain the backlog
  whenever it is up without being reachable from atpg. When no worker is
  running, jobs wait instead of failing.
- **Leases, not hope.** A worker claims a job with an expiring lease (the
  same idea as a broker's visibility timeout). A crashed worker's job becomes
  claimable again after the lease ends. The lease must exceed the slowest job;
  after N failed attempts a job moves to a dead-letter state that someone
  actually looks at.
- **Model versions are first-class.** The matcher is at 65.3% and the
  detector will be fine-tuned, so counts *will* be recomputed. Results are
  never overwritten. A new model version adds new rows, and the BI view picks
  a version explicitly. This is also what the future Kafka move is for (§5).
- **The model lives with the worker, not the API.** The 2 GB floor exists
  only while a worker runs. A night-window worker on atpg loads the model,
  drains the queue, and exits, so it holds 0 GB for the rest of the day.
  That answers the "2 GB around the clock" concern without making the model
  smaller.

## 4. Phased path

**Phase A, now: no new infrastructure.** Use a MongoDB collection in a
*separate database* on the existing instance as the job store. Workers claim
jobs with an atomic `find_one_and_update` (`pending` → `processing`, with
`lease_until`). This is the transactional-outbox pattern: queue state and
results live in one durable store that is already backed up, with no broker
to operate. It handles hundreds to low thousands of photos per day
comfortably. The existing synchronous `/count` stays as the demo and debug
path.

**Phase B, when volume or fan-out needs it: Celery.** Celery's worker model
(retries, concurrency, lifecycle) suits Python ML code. It needs a broker
container on atpg. RabbitMQ is preferred over Redis here. Redis emulates acks
with a visibility timeout that defaults to one hour: a job running longer
than that is silently started a second time, and a job held in prefetch ages
against the same clock. Required settings either way: `task_acks_late=True`,
`task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`, a
visibility timeout above the slowest job, and a dead-letter route. Celery's
result backend should stay off; results go to the results store.

**Phase C, with the OLAP and dashboard work: Kafka (or Redpanda) as the
log.** The deciding difference is semantics, not throughput. A queue deletes
a message once it is acknowledged. A log keeps it, so a new consumer group
can replay last month's `photo_received` events against a new model version,
and several systems (dashboard, audit, retraining set) can read the same
events independently. Re-counting history with a better model is a
certainty for this project, so the log is worth its operational cost once
dashboards exist. The hybrid that tends to survive is Kafka as the source of
truth, with a thin consumer handing work to Celery workers.

To make Phase C a transport swap rather than a rewrite, shape Phase A's
records as events from day one: `photo_received {photo_sha, store_id,
captured_at, uploaded_by, storage_ref}` and `count_completed {photo_sha,
model_version, units_detected, categories, boxes_ref, timings}`. Messages
carry references to photos, never the bytes.

## 5. Making each count cheaper, ranked by return on atpg

1. **Load models once per worker process.** Today `pack_type.score_crops`
   calls `from_pretrained` on every request, which costs 4.4 s each time on
   hemin. Loading once is free and changes no accuracy.
2. **Cap threads to the worker's CPU allowance.** On a shared host,
   `torch.set_num_threads` and `OMP_NUM_THREADS` must match the container
   limit (e.g. 4 of 8 vCPUs). Otherwise the worker competes with MongoDB, and
   over-subscribed threads also slow the worker itself. Run it under
   `nice`/`ionice` and a hard memory limit (`--memory 3g`) so the OOM killer
   takes the worker, not the database.
3. **Batch crops across photos.** A worker draining a backlog can embed
   crops from many photos per forward pass. The gain on CPU is modest. On
   GPU it is large.
4. **Replace the zero-shot classifier with a small trained one.** Telling
   cans from glass is a coarse binary decision; a 428M-parameter ViT-L/14 is
   the expensive way to do it. Distil it: run ViT-L/14 once on hemin's GPU
   as a teacher over thousands of non-test crops, then train a small student
   (a linear probe on a small backbone, or MobileNet/EfficientNet-B0 size).
   Validate on the gold set against the 93.8% baseline. A student like this
   typically needs milliseconds per crop and tens of MB of RAM. The accuracy
   it keeps is a measurement to make, not a given.
5. **End state: fold pack type into the detector.** Once the detector is
   fine-tuned on the project's own labels, a two-class detector
   (`canned`/`glass`) removes the classifier stage entirely.
6. **Int8 quantization: not on atpg.** It has no VNNI (see §1). It may be
   worth testing only for a future worker host that has it.

Throughput sketch, using unmeasured estimates: at ~50 s per photo on atpg
with concurrency 1, an 8-hour night window processes about 575 photos. With
step 4 done, the same window holds orders of magnitude more. The real
capacity question is the daily photo volume, which is still unknown (§7).

## 6. Gradio and hosted platforms

Gradio is a UI library with a good request queue, not a compute provider. It
does not change the 2 GB footprint or the 15 s forward pass. A self-hosted
Gradio page is reasonable as a *demo front-end*: upload a photo, see the
overlay. It would sit beside or on top of this pipeline, not replace it.
FastAPI's built-in `/docs` page already gives a usable upload form for
internal demos.

Hugging Face Spaces is not a good fit, for three independent reasons:

- **Plan limits.** A free account can no longer create CPU Gradio Spaces.
  It can host two ZeroGPU Spaces, and each visitor gets about 5 minutes of
  GPU time per day. CPU Basic (2 vCPU, 16 GB) needs PRO, and free hardware
  sleeps after 48 h idle with a 30-90 s cold start.
- **Reachability and account risk.** Hugging Face is reported blocked from
  Iran, and sanctions apply at the account level. The project already hit a
  network block on PyPI's file CDN from hemin.
- **Data governance.** Store shelf photos would be processed by a third
  party.

Other serverless GPU hosts (Replicate, Modal, RunPod) were not assessed one
by one. The same payment and reachability questions apply to each, so they
should be treated as unavailable unless shown otherwise.

## 7. Open decisions

- **Daily photo volume and arrival pattern** (steady, or bursts after
  store visits). This sizes everything in §5.
- **Metadata at intake.** A count is useless to BI without at least store
  id and capture time. The current `/count` accepts only a file. Where do
  photos come from today (an app, a shared folder, a messenger export)?
- **May hemin be a worker on a schedule?** It is a colleague's machine and
  is often off. A pull-based worker tolerates that, but someone should agree
  to it.
- **Approval on atpg** for: a separate MongoDB database plus a dedicated
  user for the job store; a memory-capped worker container in a night
  window; one measured benchmark run there. This is a shared production
  host, so each step needs a go-ahead.
- **Classifier distillation (§5.4) as its own task.** It needs hemin's GPU
  and a gold-set re-validation.

## Sources

- Measurements: T6 plan, Task 6 (`.hermes/plans/2026-10-10_111130-t6-fastapi-service.md`),
  and the 2026-10-10 memory probe on hemin (RSS at import / load / first
  inference / idle).
- CPU flags: `/proc/cpuinfo` on atpg (avx2, fma) and on hemin (avx2, avx_vnni, fma).
- Hugging Face Spaces plans and hardware: huggingface.co/docs/hub/spaces-overview,
  huggingface.co/docs/hub/spaces-gpus, huggingface.co/docs/hub/spaces-zerogpu.
- Hugging Face reachability from Iran: voidly.ai/ai-blocked/is-huggingface-blocked-in-iran
  (network measurement, not a vendor statement).
- Int8 without VNNI being slower on ONNX Runtime CPU:
  github.com/VENKATESH1608/onnx-cpu-inference-accelerator (single-machine report).
- Celery late acks, worker-lost requeue, prefetch and the Redis visibility
  timeout: docs.celeryq.dev (Redis broker, visibility timeout); Kombu Redis
  transport reference.
- Queue versus log semantics, and the Kafka-to-Celery hybrid:
  codenicely.in/blog/businesses/saas/celery-vs-kafka-ai-pipelines.
- Batch vs online vs streaming serving patterns:
  machinelearningatscale.com/blog/ml-model-serving-patterns.
