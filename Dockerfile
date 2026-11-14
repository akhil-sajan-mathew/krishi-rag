# syntax=docker/dockerfile:1
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/hf \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN useradd --create-home --uid 1000 app && mkdir -p /opt/hf && chown app /opt/hf

# Dependencies first so code changes don't reinstall them. Linux gets CPU-only torch (pyproject).
# The cache mount keeps uv's ~1.6 GB download cache out of the image.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

# Bake both models into the image as the runtime user: no download at startup.
USER app
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"

COPY app ./app
COPY scripts ./scripts
COPY data/sources.csv ./data/sources.csv
ENV HF_HUB_OFFLINE=1

EXPOSE 8000
# --proxy-headers: take the client IP from Caddy's X-Forwarded-For so per-IP rate limits work.
# Trusting all forwarders is safe only because the API port is never published; Caddy is the
# only thing that can reach it, and Caddy discards X-Forwarded-For sent by clients.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
