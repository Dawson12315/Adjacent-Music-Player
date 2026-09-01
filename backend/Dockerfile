FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    ca-certificates \
    openssl \
    curl \
    ffmpeg \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Runtime state (SQLite DB, transcode caches, uploads) lives in a volume mounted at
# /app/data. Never COPY it into the image: published images are public, and the local
# data directory holds the operator's real database.
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]