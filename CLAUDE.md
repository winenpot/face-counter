# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Early-stage. **Phase 0 (foundations) is implemented**; the API and inference layers are not.

**Goal:** a computer-vision service that counts visible product faces in retail shelf photographs and computes share of shelf. `docs/ROADMAP.md` is the operative plan (phases, architecture, MongoDB `predictions` schema, risks); `docs/PROPOSAL.md` is the earlier, broader proposal — where the two disagree, the roadmap wins.

The approach is **two-stage**: a detector finds every product, then an identifier names each crop. A single 400-class detector would need ~90k hand-drawn boxes, which doesn't fit the timeline. Adding a SKU means adding reference images to the gallery, not retraining. Two companion docs expand the model and method choices: `docs/DETECTOR_ALTERNATIVES.md` (SKU-110K is a single-class *dataset*, not a model; YOLO is a starting point and the detector is meant to stay swappable — RT-DETR/D-FINE/DEIM are the live alternatives) and `docs/ERROR_ANALYSIS.md` (failure taxonomy, sliced metrics, hyperparameter-tuning order, and active learning — which is what "human-in-the-loop" means here; RLHF is the wrong tool because detection has ground truth). `docs/LABELING_STRATEGY.md` covers how labeling scales without labeling every photo: an exhaustive two-pass test set only, identity named per *cluster* of near-identical crops, and competitors labeled at category level (`COMPETITOR_<category>`), because share of shelf only needs "ours vs. not ours" per category. It also covers which free tools fit; Roboflow's free plan publishes data, so it is not used for company photos.

What exists today is the data pipeline in `src/face_counter/`: export photos from MongoDB, build a manifest, split by store, prepare Label Studio. The package is organized by deployment role — `training/` (export, run on the GPU box), `label_studio/` (splits + labeling prep, run here), `serving/` (placeholder for the future inference API), `utils/` (shared config/path helpers used by all of them) — so `scripts/sync_to_hemin.sh` / `scripts/sync_from_hemin.sh` can sync code one-way per direction without shipping the other side's concerns (code changes still belong in git, not rsync — see the comments in those scripts). **Phase 0 is nearly complete** — the full export ran against production on 2026-09-24 (9,704 photos, ~30 GB, living on the GPU box only; this machine needs just the 2 MB manifest via `sync_from_hemin.sh --with-manifest`), and splits were cut over it the same day (30-photo test set, leak-checked). What's left is eyeballing the test set's mix and freezing it with a versioned copy (`data/splits/` is gitignored). `docs/PHASE0_REMAINING.md` has the detail and the open questions; read it before touching the export. Phases 1–4 (detector, FastAPI `/count` + `/overlay`, pre-labeling loop, production) are not started.

## Commands

Dependency management is via `uv` (Python 3.14, pinned in `.python-version`; `uv_build` backend).

- Install: `uv sync --group dev` (runtime + pytest/mongomock)
- Optional analytics group (notebook, ultralytics): `uv sync --group analytics`
- Run tests: `uv run pytest` — end-to-end against a fake MongoDB (mongomock + GridFS); no database or network needed
- Phase 0 CLIs: `uv run shelf-export` → `uv run shelf-splits` → `uv run shelf-label-prep`
- Image-audit helper: `uv run python scripts/scan_images.py [directory]`

No linter or formatter is configured yet — don't assume `ruff`/etc. exists until it's in `pyproject.toml`.

## Architecture notes

- `src/face_counter/utils/config.py` owns `PROJECT_ROOT` (resolved via `parents[3]` from inside `src/face_counter/utils/`) and the `DEFAULT_*` path constants. Use those constants for defaults rather than rebuilding paths, so the repo can be run from any cwd.
- The export is **read-only and resumable** by design: it writes `.part` files and renames atomically, checkpoints the manifest every 100 photos, and skips anything already on disk. Preserve those properties — it runs against the live production MongoDB.
- Use a read-only Mongo user. Never add a write path to the export.
- `make_splits.py` assigns splits by a **stable hash of `store_id`** with a fixed `SALT`. Changing the salt reshuffles which stores are in test and invalidates every accuracy number ever reported; don't. Splitting by store (not by photo) is what stops near-duplicate shelf photos leaking across train/test.
- `data/splits/test_labeling.txt` is the fixed test set and is never regenerated without `--force`.

## Data pipeline

Raw images live in `data/raw/` and are **git-ignored**; DVC (`.dvc/`, `.dvcignore`) owns dataset versioning. `.dvc/config` has no remote configured — data is local-only for now.

`docs/DATASET_PREPARATION.md` defines the pipeline: **Collect → Organize & Preprocess → Annotate → Validate → Split → Version**.
- Preprocessing/QA tooling: Pillow / OpenCV; dataset inspection via supervision.
- Annotation: **Label Studio** is the primary tool (Roboflow/supervision are complementary). Annotation format: COCO JSON.
- Labelers follow `docs/labeling_guide.md` — it defines what counts as a "face" (front row, label visible, ≥50% of the front face).

When adding data-processing scripts, follow this doc's tool choices rather than introducing new ones (e.g. Pillow over adding a new imaging dependency).

## Label Studio is a separate app

`deploy/label-studio/` deploys the third-party **labeling web app** that labelers use in the browser. It is **not** this service's deployment — the shelf-detector inference API (Phase 2) will get its own. Don't conflate the two compose files.

It holds company photos and is network-reachable, so: signup disabled, invite links only, port bound to one interface via `LS_BIND_IP`. Note that Docker publishes ports ahead of `ufw`, so a firewall does not restrict it. See `deploy/label-studio/README.md`.

**Never run `docker compose down -v`, `docker volume rm`, or any `prune --volumes` against a Label Studio stack.** Its named volumes hold every annotation, and deleting them is unrecoverable. `stop` or plain `down` keeps them. Before an upgrade or cleanup, export JSON and `pg_dump` first (README, "Stopping without losing labels"). This machine also runs an unrelated Label Studio from `~/code/ATPG-tagsystem` on port 7071; don't import into it or touch its volumes.
