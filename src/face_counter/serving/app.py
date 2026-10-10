"""FastAPI service: `POST /count`, `POST /overlay`, `GET /health` (T6 plan,
Task 5). The pipeline (serving/pipeline.py) decides what's reliable; this
module is presentation only — decoding uploads, drawing an overlay, and
shaping the HTTP surface.

`/count` and `/overlay` require a static `X-API-Key` header (Task 5b) —
a placeholder, not real auth; see `require_api_key`'s docstring. `/health`
stays open for monitoring.
"""

from __future__ import annotations

import hmac
import io
import logging
import os
import subprocess
import threading
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from PIL import Image, ImageDraw, ImageOps
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from face_counter.identification import pack_type as pt
from face_counter.serving import schemas
from face_counter.serving.pipeline import BoxResult, Pipeline, ServeConfig
from face_counter.utils.config import PROJECT_ROOT

log = logging.getLogger("serve.app")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# Overlay colours by pack type (the reliable signal) -- never by brand/role.
_PACK_COLORS = {"canned": "#2ecc71", "glass": "#3498db"}
_FALLBACK_COLOR = "#999999"


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=2, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except OSError:
        pass
    return os.environ.get("FACE_COUNTER_VERSION", "unknown")


def _pack_classifier_name(pipeline: Pipeline | None) -> str | None:
    """The classifier actually in use, or None when the stage is off."""
    return pt.MODEL if pipeline is not None and pipeline.cfg.classify else None


def _decode_image(data: bytes) -> Image.Image:
    try:
        return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"could not decode image: {e}") from e


def require_api_key(request: Request, x_api_key: str = Header(default="")) -> None:
    """Static shared-secret check — a placeholder, not real auth (no
    accounts, no rotation, no scopes). Decided 2026-10-10: good enough to
    keep the service off the open internet for now; replace before this
    goes anywhere less trusted than an internal demo."""
    expected = request.app.state.pipeline.cfg.api_key
    if not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "invalid API key")


def _run_locked(pipeline: Pipeline, lock: threading.Lock, img: Image.Image, debug: bool):
    """Runs in a worker thread (via run_in_threadpool): the lock's blocking
    acquire must never happen on the event-loop thread."""
    with lock:
        return pipeline.run(img, debug=debug)


def _draw_overlay(img: Image.Image, boxes: list[BoxResult], max_side: int = 1600) -> Image.Image:
    im = img.copy()
    scale = min(1.0, max_side / max(im.size))
    if scale < 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)))
    d = ImageDraw.Draw(im)
    for b in boxes:
        x1, y1, x2, y2 = b.xyxy
        color = _PACK_COLORS.get(b.pack_type, _FALLBACK_COLOR)
        d.rectangle([x1 * scale, y1 * scale, x2 * scale, y2 * scale], outline=color, width=3)
    d.rectangle([0, 0, 220, 24], fill="black")
    d.text((6, 5), f"{len(boxes)} units detected", fill="white")
    return im


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    """Build the app. Pass `pipeline` to inject a fake for tests; omit it to
    load the real one from env vars at startup (lifespan)."""

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        if app.state.pipeline is None:
            app.state.pipeline = Pipeline.load(ServeConfig.from_env())
        if app.state.pipeline.cfg.api_key == ServeConfig.api_key:  # the dataclass default
            log.warning(
                "FACE_COUNTER_API_KEY is still the placeholder default — "
                "rotate it before this service is reachable from anywhere "
                "but a local, trusted demo."
            )
        yield

    app = FastAPI(title="face-counter", lifespan=_lifespan)
    app.state.pipeline = pipeline
    app.state.lock = threading.Lock()

    @app.get("/health")
    def health() -> dict:
        pipeline_ = app.state.pipeline
        return {
            "status": "ok" if pipeline_ is not None else "loading",
            "detector": pipeline_.cfg.detector_model if pipeline_ else None,
            "pack_classifier": _pack_classifier_name(pipeline_),
            "version": _git_sha(),
        }

    @app.post(
        "/count",
        response_model=schemas.CountResponse,
        response_model_exclude_none=True,
        dependencies=[Depends(require_api_key)],
    )
    async def count(file: UploadFile = File(...), debug: bool = Query(False)):  # noqa: B008
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file too large (max 20 MB)")
        img = _decode_image(data)
        pipeline_ = app.state.pipeline
        result = await run_in_threadpool(_run_locked, pipeline_, app.state.lock, img, debug)
        model_info = schemas.ModelInfo(
            detector=pipeline_.cfg.detector_model, pack_classifier=_pack_classifier_name(pipeline_)
        )
        return schemas.from_result(result, model_info)

    @app.post("/overlay", dependencies=[Depends(require_api_key)])
    async def overlay(file: UploadFile = File(...)):  # noqa: B008
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file too large (max 20 MB)")
        img = _decode_image(data)
        pipeline_ = app.state.pipeline
        result = await run_in_threadpool(_run_locked, pipeline_, app.state.lock, img, False)
        out_img = _draw_overlay(img, result.boxes)
        buf = io.BytesIO()
        out_img.save(buf, format="JPEG", quality=85)
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    return app


def main() -> None:
    import uvicorn

    host = os.environ.get("FACE_COUNTER_HOST", "127.0.0.1")
    port = int(os.environ.get("FACE_COUNTER_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
