# ============================================================
# 小云雀 AI 漫剧 · Backend (FastAPI + worker)
# 适用平台: Railway / Render / Fly.io / 任意 Docker 主机
# ------------------------------------------------------------
# 构建上下文 = 仓库根目录（由根目录 railway.toml 指定 dockerfilePath）
# 本地手动构建：   docker build -f backend/Dockerfile -t xyq-backend .
# ============================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# 系统依赖：仅 ffmpeg（后期合成用）+ ca-certificates
# 不装 build-essential：bcrypt / psycopg2-binary 等都有预编译 wheel，250MB+ 浪费
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      curl \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制 requirements.txt 利用 docker layer cache
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# 复制后端代码
COPY backend/app ./app

# storage 目录用于本地落盘视频
# 不用 Dockerfile VOLUME（Railway 显式不支持 dockerfile VOLUME 指令）
# 持久化方式：在 Railway service → Settings → Volumes 挂载到 /app/storage
# 或者把 result_url 改成 S3/R2/Vercel Blob 的 URL
RUN mkdir -p /app/storage

EXPOSE 8000

# Railway / Render 会自动注入 $PORT，本地默认 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
