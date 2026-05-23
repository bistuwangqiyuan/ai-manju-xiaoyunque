# ============================================================
# 小云雀 AI 漫剧 · Backend (FastAPI + worker + full pipeline)
# Build context = repository root (railway.toml)
# ============================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libpq5 \
      fonts-noto-cjk \
      fonts-noto-cjk-extra \
      fonts-noto-color-emoji \
      curl \
      ca-certificates \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend-requirements.txt
COPY requirements.txt ./pipeline-requirements.txt
RUN pip install -r backend-requirements.txt \
    && pip install -r pipeline-requirements.txt

COPY backend/app ./app
COPY src ./src
COPY prompts ./prompts
COPY config ./config
COPY tools ./tools
COPY compliance ./compliance

RUN mkdir -p /app/storage /app/storage/jobs

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
