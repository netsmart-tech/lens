# =============================================================================
# Lens backend — multi-stage Dockerfile
# Stage 1 (builder): install deps into a venv
# Stage 2 (runtime): slim image, non-root, venv copied in
# =============================================================================

ARG PYTHON_VERSION=3.12

# ---- builder ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a venv so the runtime stage can copy a self-contained tree
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
# Resolve deps from pyproject. Use pip to install the project (no build backend
# needed for editable here — we'll COPY the source in the runtime stage).
RUN pip install --upgrade pip && \
    pip install .

# ---- runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 lens \
    && useradd --system --uid 1000 --gid lens --home /app lens

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=lens:lens . /app

USER lens

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "lens.main:app", "--host", "0.0.0.0", "--port", "8000"]
