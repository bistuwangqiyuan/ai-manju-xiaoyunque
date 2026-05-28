# =============================================================================
# 小云雀 · CloudBase 单容器 Bundle（预构建静态前端 + FastAPI）
# 本地先: CLOUDBASE_STATIC=1 npm run build --prefix web
# 再: python scripts/deploy_cloudbase_bundle.py
# =============================================================================
FROM python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    STATIC_WEB_DIR=/app/static_web \
    DATABASE_URL=sqlite:////data/xyq.db \
    STORAGE_DIR=/data/storage \
    EMBEDDED_WORKER=1 \
    PORT=8080 \
    MOCK_MODE=1

RUN pip config set global.index-url "$PIP_INDEX_URL"

WORKDIR /app

COPY backend/requirements.txt ./backend-requirements.txt
COPY requirements.txt ./pipeline-requirements.txt
RUN pip install -r backend-requirements.txt \
    && pip install -r pipeline-requirements.txt \
    && pip install python-multipart==0.0.20

COPY backend/app ./app
COPY src ./src
COPY prompts ./prompts
COPY config ./config
COPY tools ./tools
COPY compliance ./compliance

# Pre-built Next.js static export + sample mp4/jpg
COPY web/out ./static_web
COPY web/public/samples ./web/public/samples

RUN mkdir -p /data/storage

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
