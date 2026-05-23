# ============================================================
# 小云雀 AI 漫剧 · Backend (FastAPI + worker + full pipeline)
# Build context = repository root (railway.toml / deploy/cn/docker-compose.yml)
#
# Build for 国内服务器 with Chinese mirrors:
#   docker build \
#     --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn \
#     --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
#     -f backend/Dockerfile -t xyq-backend .
# ============================================================
FROM python:3.11-slim

ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PORT=8000

# Optional: switch to a Chinese apt mirror for fast builds on CN servers.
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|$APT_MIRROR|g; s|security.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
      sed -i "s|deb.debian.org|$APT_MIRROR|g; s|security.debian.org|$APT_MIRROR|g" /etc/apt/sources.list 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libpq5 \
      fonts-noto-cjk \
      fonts-noto-cjk-extra \
      fonts-noto-color-emoji \
      curl \
      ca-certificates \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Optional: switch pip to a Chinese mirror (Tsinghua / Aliyun) for fast installs.
RUN if [ -n "$PIP_INDEX_URL" ]; then \
      pip config set global.index-url "$PIP_INDEX_URL"; \
    fi

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
