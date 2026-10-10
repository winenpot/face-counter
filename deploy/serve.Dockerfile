# Detection-only serving image (docs/SERVING_STRATEGY.md, T6).
#
# No torch, no CLIP. `--no-dev` matters: the dev group pulls ultralytics,
# and with it torch. Only the base dependencies plus the `serve` group are
# installed.
#
# Model weights are not baked in. Mount the exported ONNX directory at
# /app/models read-only (configs/bakeoff.yaml points at
# models/yolo26l-sku110k.onnx, relative to the project root /app).
#
#   docker build -f deploy/serve.Dockerfile --build-arg VERSION=$(git rev-parse --short HEAD) \
#       -t face-counter-serve:$(git rev-parse --short HEAD) .
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
# Dependencies first, so code-only changes reuse this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --group serve --no-install-project
COPY src ./src
COPY configs ./configs
RUN uv sync --frozen --no-dev --group serve && rm -rf /root/.cache/uv

ARG VERSION=unknown
ENV PATH=/app/.venv/bin:$PATH \
    FACE_COUNTER_VERSION=$VERSION \
    FACE_COUNTER_HOST=0.0.0.0 \
    FACE_COUNTER_PORT=8000 \
    FACE_COUNTER_CLASSIFY=0

USER 65534:65534
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["shelf-serve"]
