---
type: devops
---

# Environments and dependency groups

Training uses the GPU; serving runs optimised inference on CPU only; every
other concern stays in its own environment. The groups in `pyproject.toml`
(`[dependency-groups]`) encode this, and nothing may cross-contaminate them.

| Group | Owner | Contains | Must never contain |
|---|---|---|---|
| base (`[project].dependencies`) | everyone | pandas, pillow(+heif), pymongo, pyyaml, openpyxl, python-dotenv | ML frameworks |
| `dev` | every machine | httpx, mongomock, pytest, ruff | torch, ultralytics |
| `serve` | the API process, CPU | fastapi, uvicorn, python-multipart, CPU `onnxruntime` | torch, transformers, ultralytics |
| `analytics` | hemin (GPU) | torch, torchvision, transformers, ultralytics, onnx, onnxslim, notebook | a CPU-index pin |

## Rules

1. **Put a package in the group of the process that imports it.** Export-only
   tools (`onnx`, `onnxslim` for `scripts/export_onnx.py`) belong in
   `analytics`, never in `serve`.
2. **Never pin torch to a CPU wheel index in the committed files.**
   `pyproject.toml` and `uv.lock` are shared with hemin through git; a CPU pin
   would replace hemin's working CUDA torch on its next sync. This happened
   once (commit b9b9fa7) and was reverted (5d1ecff) before hemin synced.
3. **CPU-only machines that need bare torch** for the two numeric tests in
   `test_identification.py` install it out of band, into their own `.venv`
   only (the command is in the comment above `analytics` in
   `pyproject.toml`). After that, sync with `--inexact` so the torch install
   is not stripped.
4. **Sync only the groups the task needs.** On hemin, use
   `--group dev --group serve --inexact` for serving work. A re-locked
   `analytics` re-resolves newer CUDA sub-dependencies. Check
   `torch.cuda.is_available()` on hemin before and after any
   `pyproject.toml` or `uv.lock` change.
5. **Images install `--no-dev --group serve`** (`deploy/serve.Dockerfile`);
   the result is checked to contain no torch.
6. **Serving code defers heavy imports** into functions, and a
   fresh-interpreter test asserts a request imports no torch, transformers or
   ultralytics (`tests/test_serving.py:240`).

## Known gaps

- hemin's `.venv` holds the `serve` wheels and `onnx`/`onnxslim`, copied in
  by hand while PyPI's file CDN was unreachable. They work, but uv does not
  track them. Issue #5 (wheelhouse + model artifact store).
- In non-interactive `ssh hemin <cmd>` sessions, `uv` is not on PATH; use
  `~/.local/bin/uv`.
