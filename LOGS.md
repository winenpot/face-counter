# LOGS

Note (2026-09-24): entries from here forward are written in English.
Earlier entries below remain in Persian/Farsi as originally written —
left as-is rather than machine-translated, to avoid corrupting the
original record.

---

خط زمانی خوانا و انسانی از آن‌چه واقعاً روی این پروژه اتفاق افتاده —
تصمیم‌ها، باگ‌های پیدا شده، بن‌بست‌ها. این جایگزین `git log` نیست (آن‌جا
خودش هست)؛ این برای روزی است که شش ماه دیگر بپرسیم «چرا این‌طور
انجامش دادیم؟». هر بخش یک جلسه‌ی کاری، جدیدترین بالا، خلاصه و کوتاه.

---

## 1405/07/04 (2026-09-26) — test set frozen, labeling strategy written, and the first three detectors actually ran

**Labeling strategy — how 9,500 photos get labeled by a small team.** New doc
`LABELING_STRATEGY.md`. Three decisions carry it: only the **test set** is
labeled exhaustively (two passes); identity is named per *cluster* of
near-identical crops rather than per crop; and competitors are labeled at
category level (`COMPETITOR_<category>`), because share of shelf only ever needs
"ours vs. not ours" within a category. Also settled a tooling question with a
licence answer: **Roboflow's free plan publishes your data**, so it is out for
company photos — Label Studio stays the primary tool.

**Label Studio operational guardrails.** The stack holds every annotation in
named volumes, so `down -v` / `docker volume rm` / `prune --volumes` are
unrecoverable there. Written into `deploy/label-studio/README.md` with the
export + `pg_dump` procedure to run before any upgrade. Noted that the unrelated
`ATPG-tagsystem` Label Studio on port 7071 is a different instance — don't
import into it, don't touch its volumes.

**The 30-photo test set is frozen (12:57).** Reviewed by eye, hand-corrected,
and committed: `data/splits/test_labeling.txt` is now the one tracked file under
`data/splits/`, via an explicit `.gitignore` exception. The **git copy is the
authority** and no seed regenerates it — `shelf-splits --force` must never run
again, or every accuracy number ever reported is measured against a different
test set.

**EXIF correction, worse than first recorded.** The 2026-09-24 entry said two of
the 30 test photos disagreed with the manifest on orientation. The real number
is **14 of 30 stored sideways**. The manifest's width/height are post-rotation;
pixels must always be loaded through `ImageOps.exif_transpose`. Anything that
skips it places boxes rotated 90° and it will look like a model bug.

**`shelf-bakeoff` — step zero of Phase 1 (13:30).** New CLI
(`src/face_counter/training/detector_bakeoff.py`): runs candidate detectors over
the frozen test set and writes what a human needs to judge them —
`detections.jsonl`, `counts.csv`, `overlays/<model>/*.jpg`, and
`ls_predictions_<model>.json` to pre-fill the Label Studio geometry pass.
Deliberately scores nothing: the test set has no boxes yet.

**A transformers 5 break, fixed (14:13).** The DETR-SKU110K checkpoint's
`config.json` was written by transformers 4.38 with `"dilation": null` (and three
other nulls). transformers 5 type-checks config fields strictly and rejects
`None` for a `bool`; dropping the null keys falls back to the class defaults,
which is what 4.x did with `None` anyway.

**First real run, on the GPU box (14:15–14:23), and what it showed.** 30 photos
x 3 models, ~15 s total; steady state 0.04–0.07 s/photo with a slower first
image per model (CUDA warm-up) — GPU, unambiguously. Box counts over the test
set:

| model | total | median | min | max |
|---|---|---|---|---|
| sku110k-yolo11s | 2,319 | 69.5 | 15 | 218 |
| detr-r50-sku110k | 5,545 | 183.5 | 51 | 396 |
| yoloe-26s | 1,466 | 40.5 | 1 | 134 |

Three readings, none of them accuracy:
- **DETR is structurally capped at 400 boxes** (400 queries) and one photo came
  back with 396 — saturation, on shelves documented as reaching ~500 faces. Its
  uniformly high counts are also what DETR does at conf 0.25 with no NMS, so
  part of the gap is recall and part is duplicate queries. Only the overlays
  separate the two.
- **YOLOE collapses on two photos** (1 box each) while returning 134 elsewhere:
  a failure, not a weak score. Generic text prompts are the suspect.
- The three models disagree by 3–10x on the same photo, which is exactly why
  step zero exists — the geometry pass can't be pre-filled from a model chosen
  on vibes.

**The pull had to be done by hand, and that is a real finding.**
`sync_from_hemin.sh` gates on the remote tree being clean, but
`~/code/face-counter` on the GPU box **is not a git repo** (it was rsynced, never
cloned), so the gate fails closed and every results pull aborts. Pulled the 43 MB
run directly with `rsync` instead. Two facts worth keeping: the box has **no
revert safety net** for anything edited there, and the fix is to `git clone` it
rather than to weaken the gate.

**Also established: this workstation cannot be pushed to.** It runs no sshd —
from the GPU box, `ssh winenpot@192.168.1.206` is refused. So "results are sent
back" is not implementable as a push; results come back only because this side
pulls them. Any future automation of that must be initiated here.

**Reverted an over-engineered sync refactor.** Started building `.env`-driven
sync config (`GPU_HOST` alias, `GPU_REMOTE_DIR`, `GPU_REMOTE_HAS_GIT`), a
`report.json` per run, and a `--run <stamp>` pull mode — five files. The user
called it too much machinery for the problem and reverted it all; the existing
scripts work, and where things go is easier to remember than to configure.
Recorded because the *underlying facts* (no sshd here, no git there) outlive the
code that was deleted.

**Still open, end of day:**
- Eyeball the overlays in `runs/bakeoff/20260926-141557/overlays/` and decide
  whether DETR's extra boxes are recall or duplicates — that single judgement
  picks the model that pre-fills the geometry pass.
- The 3 annotated examples for `labeling_guide.md` (last Phase 0 item, owner
  working on it).
- `git clone` the GPU box so sync stops needing manual rsync.
- Carried over: the 2,230-vs-3,292 store gap, studio packshots, `root` rotation.

**Lesson of the day:** a guard that fails closed on a condition nobody
anticipated (no `.git` on the far side) is indistinguishable from a broken
script, and gets worked around by hand instead of fixed. Same shape as
2026-09-24's `--with-data` bug: the failure is silent-ish, the workaround is
cheap, so the cause survives. Note the cause where it will be read again.

---

## ۱۴۰۵/۰۷/۰۲ (۲۰۲۶-۰۹-۲۴) — the export finally ran; the model landscape moved; a user tip corrected a wrong call

**Morning – Phase 0 audit.** Walked the roadmap checkbox by checkbox. The
picture was worse than the checkboxes implied: the export had never run against
production, so the "manifest" and "fixed test set" were both artifacts of a
295-photo sample, and the test set held 15 photos instead of the required 30.

**~11:37–12:17 – the production export ran** (on Hemin's box, by the user).
9,409 new + 295 already on disk = **9,704 manifest rows**, `missing: 0`,
`bad_image: 1`. About 30 GB. Two things worth recording: the single `bad_image`
is the already-known truncated 7 KB photo, not a new failure mode; and the
earlier live sample's alarming 8-of-13 decode failures collapsed to **1 in
9,704** once `pillow-heif` landed — good retrospective evidence that diagnosis
was right.

**Detector research — the landscape moved, and our stated plan is out of date.**
The roadmap says "train a small YOLO on SKU-110K", which hides two things.
SKU-110K is a *dataset*, not a model, and it is *single-class* — every box is
labelled `object`, so it can never name a product. That is not a limitation but
the reason it fits: it solves stage 1 completely and demands zero labelling
from us. Second, YOLO is no longer the accuracy leader. The DETR branch took
over: RT-DETR made DETR real-time, D-FINE replaced point-estimate box
coordinates with a distribution it iteratively sharpens, and **DEIM** (CVPR
2025, Apache-2.0) attacked training cost — ~50% less training time, SOTA
real-time AP, and *largest gains on small objects*, which is exactly our
weakness. DEIM reaches 53.2 AP in one day on a single 4090; our 4060 Ti is in
the same conversation. The training-cost objection that justified picking YOLO
is the specific thing DEIM removes. Also found published SKU-110K checkpoints
(one DETR-ResNet-50 at 58.9 mAP, *trained on a 4060 Ti*), so Phase 1 now starts
with an afternoon evaluating existing weights before spending a night training.
Written up in `DETECTOR_ALTERNATIVES.md`; Phase 1 gained a `Detector` protocol
so the backend stays a config choice.

**RLHF question → the process gap it exposed.** The user asked whether RLHF
applied here. It does not, and the reason is structural: RLHF exists to optimise
models whose output has *no ground truth* — every part of its machinery
(preference pairs, reward model, policy gradient) is a workaround for a missing
label. A corrected bounding box *is* ground truth, so supervised learning on
corrections is strictly better. What the user actually wanted is **active
learning**, and that led somewhere more useful: the roadmap had no home for
error analysis, hyperparameter tuning, or any mechanism behind "prioritize
low-confidence photos". Phase 3 was rewritten around diagnosis-before-retraining
(a nine-row failure taxonomy separating wrong-brand from wrong-flavor, sliced
metrics, confusion matrix, a worst-50 bank reviewed by eye) plus a real active
learning loop (uncertainty → ensemble disagreement → NORIS diversity over
*object-region* features → ALMUS class-balanced allocation). New doc:
`ERROR_ANALYSIS.md`.

**A pre-existing bug in `sync_from_hemin.sh --with-data`: it never worked.**
Found while adding `--with-manifest` (splits need a 2 MB CSV, not 32 GB of
photos, and there was no way to ask for that). With the trailing
`--exclude '*'` default-deny, rsync never descended into `data/` because
`data/` itself was never included — the mode would report success and transfer
nothing. Nobody had exercised it. Both modes now include the parent dir
explicitly, verified against the live remote with `--ignore-times` dry runs.

**Splits re-cut over the full corpus, test set frozen at 30.** Cleared the old
sample-derived files and re-ran from scratch. 9,573 photos after dropping 131
exact duplicates; train 7,640 / val 1,076 / test 857, and **zero store overlap
between any pair of splits** — the leakage guard holds at full scale. The test
set is 30 photos from 30 *distinct* stores, one photo each. All 30 decode
(including 3 `.mpo` and 1 `.heif`).

**The user's tip that corrected a wrong call.** During the decode check, three
test photos shared an identical byte size and two more looked like screenshots;
I was heading toward calling them contamination and re-rolling the test set.
The user mentioned the field app's developer had modified images server-side
after upload because of upload problems. The data confirms it exactly: **1,225
of 9,704 photos (12.6%) sit within 2 KB of exactly 4 MiB, 950 at the identical
byte count 4,194,868**, plus downscaled populations at 810x1080 (221), 960x1280
(214), 1200x1600 (200). So the low-resolution photos are a *systematic,
representative slice of real production traffic* — filtering them out would
have made the test set less representative than reality and inflated every
number the project ever reports. Resolution tier became a reporting slice in
`ERROR_ANALYSIS.md`; `requests.md` gained a question to the app developer about
whether pre-compression originals still exist anywhere (if they do, training on
them is free accuracy).

**Still open / waiting on someone else, end of day:**
- Eyeball pass on the 30 test photos for mix (aisles, fridges, glare, store
  types) — images are on Hemin's box.
- The 3 annotated examples for `labeling_guide.md` — owner working on it.
- **Unexplained: 2,230 distinct stores against the surveyed 3,292.** The 1%
  join-failure rate does not account for a 32% gap. Not blocking, but nobody
  should quote store coverage until it is understood.
- **EXIF orientation trap:** the manifest records pre-rotation dimensions while
  Pillow applies the orientation flag; two of the 30 test photos disagree.
  Harmless today, but anything in Phase 1 trusting manifest width/height will
  place boxes rotated 90° — and it will look like a model bug, not an
  assumption bug.
- Studio packshots from marketing (all 8 brands, named by `class_name`), and
  the deferred `root` password rotation.

**Lesson of the day:** the two most valuable corrections came from outside the
code. The user's offhand remark about the app developer's upload fix overturned
a conclusion I had reached from the data alone and was about to act on — the
numbers were right, the interpretation was wrong, and only domain context could
tell the difference. Corollary: before treating unusual data as defective,
find out who touched it and why. The same day also showed the cost of *never*
exercising a code path — `--with-data` had been broken since it was written,
and only running it revealed that.

---



## ۱۴۰۵/۰۶/۳۱ (۲۰۲۶-۰۹-۲۲) — یک روز کامل: ادغام shelf-detector، یک باگ واقعی در اسکیما، راه‌اندازی سرور GPU



**۰۹:۴۶ – اولین نگاه واقعی به دیتابیس تولید.** یک بررسی فقط‌خواندنی از
`atpg` (دیتابیس واقعی و زنده) یک شگفتی بزرگ نشان داد: تنظیمات export
(`configs/export.yaml`) *قبل از این‌که کسی اسکیمای واقعی را دیده باشد*
نوشته شده بود — فیلدهایی (`visit_id`, `rep_id`, `city`, `created_at`)
نگاشت شده بودند که اصلاً در داده‌ی واقعی وجود نداشتند.

**۱۰:۰۷–۱۰:۴۵ – مستندات از کنترل خارج شد، بعد جمع‌وجور شد.** یک
`VERIFY.md` مفصل به‌همراه یک اسکریپت تأیید نوشته شد تا هر ادعای بررسی
به‌طور مستقل قابل بررسی باشد. کمی بعد این حجم مستندات جمع شد:
`VERIFY.md` حذف شد، سند باقی‌مانده (`PHASE0_REMAINING.md`) کوتاه‌تر
شد، و اسکریپت تأیید ساده‌تر شد. درس: پیش‌فرض باید ساده‌ترین راهی
باشد که کار می‌کند؛ پیچیدگی فقط وقتی اضافه شود که واقعاً یک استفاده‌ی
دوم داشته باشد.

**۱۰:۴۵–۱۰:۵۱ – تنظیمات export روی اسکیمای واقعی تنظیم شد.**
`configs/export.yaml` بازنویسی شد تا با شکل واقعی `atpg` هم‌خوان
باشد: مبتنی بر GridFS، فیلتر شده روی `photo_type: shelf` (عکس‌ها چند
نوع دارند؛ فقط یکی از آن‌ها عکاسی واقعی از قفسه است)، و جوین‌شده با
مجموعه‌ی `location` برای به‌دست‌آوردن منطقه، چون خود عکس منطقه را
مستقیماً حمل نمی‌کند. هر کدام از این‌ها روی داده‌ی زنده تأیید شد،
نه فقط روی تست‌ها.

**۱۴:۱۱ – عکس‌های HEIC بی‌سروصدا ناپدید می‌شدند.** عکس‌های آیفون
به‌صورت پیش‌فرض HEIC هستند، فرمتی که Pillow به‌تنهایی نمی‌تواند
بخواند — هر آپلود HEIC در حین export بی‌سروصدا حذف می‌شد، بدون خطا،
بدون هشدار، بدون هیچ اثری در manifest. کتابخانه‌ی `pillow-heif` اضافه
شد؛ روی داده‌ی زنده تأیید شد که از یک نمونه‌ی ۲۵ تایی، ۸ عکس HEIC
بودند و همه اکنون درست دیکد می‌شوند.

**۱۴:۳۱ – مورد بزرگ روز: store_code در واقع یک فروشگاه نیست.**
جرقه‌اش یک مشاهده‌ی دو خطی از رابط کاربری برنامه بود — دو عدد متفاوت
برای یک فروشگاه نمایش داده می‌شد، با برچسب «کد ثابت» و «کد ثبت». این
موضوع خیلی مهم بود: `store_code` روی یک عکس در واقع یک **کد ثبت
مخصوص بازدید** است، و هر بار که فروشگاه دوباره ثبت می‌شود، عوض
می‌شود — به‌صورت زنده تأیید شد که یک فروشگاه در طول زمان ۵ کد متفاوت
داشته. منطق تقسیم‌بندی train/test فرض می‌کرد که «تقسیم بر اساس
فروشگاه» از نشت عکس‌های تقریباً تکراری بین train و test جلوگیری
می‌کند، اما در واقع بر اساس *بازدید* تقسیم می‌شد — یک فروشگاه فیزیکی
واحد، در دو بازدید مختلف، می‌توانست هم در train و هم در test بیفتد.
با یک جوین دوم (`location.code -> permanent_id`) اصلاح شد تا هویت
واقعی و پایدار فروشگاه بازیابی شود؛ کد خام هر بازدید حالا درست در
ستون `visit_id` قرار می‌گیرد، جایی که قبلاً همیشه خالی بود.

**بعدازظهر — پاک‌سازی Docker روی apps server (بی‌ربط به کد، ولی
واقعی).** apps server (۳۰ کانتینر، شامل MongoDB تولید و Label Studio)
روی ٪۷۹ فضای دیسک بود، فقط ۲۰ گیگابایت آزاد. حجم زیادی از build
cache و ایمیج‌های بلااستفاده‌ی Docker پیدا شد که قابل پاک‌سازی بودند
— بخش‌های امن پاک شدند (فقط build cache و ایمیج‌های dangling، هیچ‌چیز
تگ‌خورده یا در حال استفاده)، حدود ۱۵ گیگابایت آزاد شد. دیسک از ٪۷۹
به ٪۶۳ رسید. همچنین تأیید شد که حذف یک ایمیج بلااستفاده‌ی `mongo:7`
توسط کاربر بی‌خطر بوده — MongoDB تولید روی `mongo:latest` اجرا
می‌شود و دست‌نخورده باقی ماند.

**۱۶:۲۶ – راه‌اندازی سرور GPU برای آموزش مدل.** دسترسی SSH بدون رمز
به کامپیوتر یکی از همکاران در شبکه‌ی داخلی (RTX 4060 Ti، ۸ گیگابایت
VRAM) برای آموزش مدل راه‌اندازی شد — عمداً فقط به‌عنوان *هدف اجرا*
نگه داشته شد، نه محیط توسعه، چون سخت‌افزار مشترک است. `uv` نصب شد،
ریپو سینک شد، `torch`/`ultralytics` نصب شدند (حدود ۲۵ دقیقه طول
کشید، بیشترش دانلود wheel‌های CUDA بود — چیزی گیر نکرده بود).
`torch.cuda.is_available() == True` تأیید شد و GPU درست شناسایی شد.
اسکریپت `scripts/sync_to_gpu.sh` اضافه شد تا آپدیت‌های بعدی کد/تنظیمات
فقط یک rsync باشند.

**۱۶:۳۶ – بستن ریسک «ارسال دوباره‌ی همان عکس به برچسب‌زن‌ها».**
دسته‌های برچسب‌گذاری (`label_batch_01.txt`, `_02.txt`, ...) قبلاً
در هر اجرای `shelf-splits` کاملاً بازنویسی می‌شدند — یک export جدید
که عکس تازه می‌آورد می‌توانست بی‌سروصدا عکس‌های *متفاوتی* را زیر همان
نام فایل جایگزین کند، بدون هیچ راهی برای فهمیدن این‌که برچسب‌زن‌ها
قبلاً چه چیزی دیده بودند. حالا دسته‌ها شماره‌دار و تجمعی هستند: عکسی
که یک‌بار در یک دسته ظاهر شده باشد، دیگر هرگز در دسته‌ی بعدی انتخاب
نمی‌شود. روی نمونه‌ی ۲۹۵ عکسی به‌صورت زنده تأیید شد: اجرای دوباره‌ی
split درست یک `label_batch_02.txt` تازه ساخت، فقط با عکس‌های باقی‌مانده
و هرگز ارسال‌نشده.

**هنوز گیر / منتظر یک نفر دیگر، پایان روز:**
- export واقعی تولید (حدود ۹٬۲۰۷ عکس، حدود ۲۸ گیگابایت) — منتظر
  کاربر که خودش اجرایش کند.
- لیست کلاس‌ها و پک‌شات‌ها از فروش/بازاریابی — کاربر چند پک‌شات و یک
  فایل اکسل از لیست کلاس‌ها را همین امروز در دست دارد.
- این‌که آیا عکس‌های نوع `sardar` جزو عکاسی قفسه حساب می‌شوند یا نه
  (اگر بله، حجم داده‌ی آموزشی تقریباً دو برابر می‌شود) — یک تصمیم
  کسب‌وکاری است.

**درس روز:** تقریباً هر باگ واقعی که امروز پیدا شد (حذف بی‌صدای
HEIC، اشتباه فروشگاه/بازدید، ریسک بازنویسی دسته‌ها) از طریق *اجرای
واقعی pipeline روی داده‌ی زنده* و خواندن دقیق خروجی پیدا شد، نه از
خواندن کد روی کاغذ. باید ادامه داد: اجراهای کوچک با `--limit` روی
داده‌ی تولید، زود و مکرر.
