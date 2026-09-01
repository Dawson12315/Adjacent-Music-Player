# Build stage: compilers live here and never reach the runtime image.
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ffmpeg: mobile/HLS transcoding. curl: container healthcheck.
# sqlite3 + openssl: operator conveniences for inspecting the DB and
# generating AUTH_SECRET_KEY from inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    openssl \
    sqlite3 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY app ./app

# Runtime state (SQLite DB, transcode caches, uploads) lives in a volume mounted
# at /app/data. Never COPY it into the image: published images are public, and
# the local data directory holds the operator's real database.
RUN useradd --create-home --uid 1000 adjacent \
    && mkdir -p data \
    && chown -R adjacent:adjacent /app

USER adjacent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
