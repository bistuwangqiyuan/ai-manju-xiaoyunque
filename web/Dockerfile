# ============================================================
# 小云雀 AI 漫剧 · Web (Next.js 15 standalone)
# Build context = ./web   (see deploy/cn/docker-compose.yml)
#
# Build for 国内服务器 with Chinese npm mirror:
#   docker build \
#     --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
#     -t xyq-web ./web
# ============================================================
ARG NODE_IMAGE=node:22-alpine

# -------- 1) deps --------
FROM ${NODE_IMAGE} AS deps
ARG NPM_REGISTRY=""
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm install --no-audit --no-fund

# -------- 2) build --------
FROM ${NODE_IMAGE} AS builder
ARG NPM_REGISTRY=""
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT_STANDALONE=1
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npx next build

# -------- 3) runtime (only the standalone server + static + public) --------
FROM ${NODE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=builder --chown=nextjs:nextjs /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
