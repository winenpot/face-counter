# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This is an early-stage project (no commits yet). The `face_counter` package is currently a stub (`src/face_counter/__init__.py` only prints a greeting from `main()`). The real substance right now is the planning docs (`docs/PROPOSAL.md`, `docs/DATASET_PREPARATION.md`) and the dataset-collection scaffolding (DVC, `data/raw/`).

**Goal:** a computer-vision service that counts visible product faces in retail shelf photographs (see `docs/PROPOSAL.md` for the full design). Planned architecture: `Caddy (reverse proxy) → FastAPI → CV inference service → object-detection model (YOLO-based) → structured face-count JSON`. None of the API/inference layers exist yet — only the data pipeline is underway.

## Commands

Dependency management is via `uv` (Python 3.14, pinned in `.python-version`; `uv_build` backend).

- Install dependencies: `uv sync`
- Install the optional analytics group (notebook, pytorch): `uv sync --group analytics`
- Run the package entry point: `uv run face-counter` (maps to `face_counter:main`)
- Run the image-audit script: `uv run python scripts/scan_images.py [directory]` (defaults to `.`)

No test suite, linter, or formatter is configured yet — don't assume `pytest`/`ruff`/etc. exist until they're added to `pyproject.toml`.

## Data pipeline

Raw images live in `data/raw/` and are **git-ignored**; DVC (`.dvc/`, `.dvcignore`) owns dataset versioning instead. `.dvc/config` currently has no remote configured — data is local-only for now.

`docs/DATASET_PREPARATION.md` defines the intended pipeline: **Collect → Organize & Preprocess → Annotate → Validate → Split → Version**.
- Preprocessing/QA tooling: Pillow / OpenCV.
- Annotation format: COCO JSON, via CVAT (or Label Studio / X-AnyLabeling / Roboflow).
- Splits should keep images from the same store/session together (no leaking near-duplicate shelf photos across train/test).
- Dataset versions get their own manifest (image/annotation counts, split seed, class count) once versioning is formalized.

When adding data-processing scripts, follow this doc's tool choices rather than introducing new ones (e.g. Pillow over adding a new imaging dependency).
