# syntax=docker/dockerfile:1.7

# ── Stage 1: build the frontend ────────────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Stage 2: backend runtime ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tini ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for cache friendliness.
COPY backend/pyproject.toml ./
RUN python -m pip install --upgrade pip \
 && pip install \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.27" \
    "sqlalchemy>=2.0" \
    "pydantic>=2.6" \
    "pydantic-settings>=2.2" \
    "aiofiles>=23.2" \
    "exifread>=3.0" \
    "python-multipart>=0.0.9" \
    "httpx>=0.27" \
    "Pillow>=10.4" \
    "pillow-heif>=0.18" \
    "rawpy>=0.21" \
    "numpy>=1.26"

COPY backend/ ./
COPY --from=frontend-build /build/dist ./static

RUN mkdir -p /app/data /data/media /mnt/sdoffload

ENV SDOFFLOAD_DB_PATH=/app/data/sdoffload.db \
    SDOFFLOAD_DESTINATION_ROOT=/data/media

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
