#!/usr/bin/env bash
# =============================================================================
# 小云雀 AI 漫剧 · 国内一键安装脚本
#
# 使用方法（在全新的腾讯云/阿里云轻量服务器 SSH 内执行）：
#   bash <(curl -fsSL https://gitee.com/<your-org>/ai-manju-xiaoyunque/raw/main/deploy/cn/install.sh)
# 或 GitHub：
#   bash <(curl -fsSL https://raw.githubusercontent.com/bistuwangqiyuan/ai-manju-xiaoyunque/main/deploy/cn/install.sh)
#
# 这个脚本会：
#   1. 检测系统（Ubuntu 22.04 / 24.04 / Debian 12 / CentOS Stream 9）
#   2. 安装 Docker + docker compose（用阿里云镜像）
#   3. 配置 Docker daemon 国内镜像加速
#   4. clone 仓库到 /opt/xyq
#   5. 生成强随机的 POSTGRES_PASSWORD 和 JWT_SECRET 写入 .env
#   6. docker compose pull + build + up -d
#   7. 等待 backend health 通过，输出访问地址
# =============================================================================
set -euo pipefail

XYQ_DIR=${XYQ_DIR:-/opt/xyq}
GIT_URL=${GIT_URL:-https://gitee.com/bistuwangqiyuan/ai-manju-xiaoyunque.git}
GIT_URL_FALLBACK=${GIT_URL_FALLBACK:-https://github.com/bistuwangqiyuan/ai-manju-xiaoyunque.git}
DOMAIN=${DOMAIN:-:80}
ACME_EMAIL=${ACME_EMAIL:-admin@example.com}

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
green() { color "1;32" "$*"; }
blue() { color "1;36" "$*"; }
yellow() { color "1;33" "$*"; }
red() { color "1;31" "$*"; }
hr() { printf '%s\n' "------------------------------------------------------------"; }

if [ "$EUID" -ne 0 ]; then
  red "请以 root 运行：sudo bash install.sh"
  exit 1
fi

# ---------- 1) 系统检测 ----------
hr
blue "[1/7] 检测系统..."
. /etc/os-release
green "检测到：$PRETTY_NAME"

case "$ID" in
  ubuntu | debian)
    PKG_INSTALL="apt-get install -y"
    PKG_UPDATE="apt-get update -y"
    ;;
  centos | rocky | almalinux)
    PKG_INSTALL="yum install -y"
    PKG_UPDATE="yum makecache -q"
    ;;
  *)
    red "未支持的发行版：$ID。请使用 Ubuntu 22.04+ / Debian 12 / CentOS Stream 9"
    exit 1
    ;;
esac

# ---------- 2) 安装 Docker（国内镜像）----------
hr
blue "[2/7] 安装 Docker..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
  systemctl enable --now docker
fi

# 检查 compose v2 可用
if ! docker compose version >/dev/null 2>&1; then
  red "docker compose v2 未安装。请升级 Docker 至 20.10+"
  exit 1
fi
green "Docker $(docker --version | awk '{print $3}' | tr -d ,) + Compose 已就绪"

# ---------- 3) Docker daemon 国内镜像加速 ----------
hr
blue "[3/7] 配置 Docker 镜像加速..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://hub.rat.dev",
    "https://docker.ketches.cn"
  ],
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "5" }
}
JSON
systemctl restart docker
green "Docker daemon 已重启（已注入 4 个国内镜像）"

# ---------- 4) clone 仓库 ----------
hr
blue "[4/7] 拉取代码到 $XYQ_DIR..."
$PKG_UPDATE >/dev/null
$PKG_INSTALL git curl ca-certificates openssl >/dev/null

if [ -d "$XYQ_DIR/.git" ]; then
  cd "$XYQ_DIR"
  git pull --rebase --autostash || yellow "(无法拉取最新代码，使用本地版本)"
else
  if git clone "$GIT_URL" "$XYQ_DIR" 2>/dev/null; then
    green "从 Gitee 拉取成功"
  else
    yellow "Gitee 拉取失败，回退到 GitHub..."
    git clone "$GIT_URL_FALLBACK" "$XYQ_DIR"
  fi
fi

cd "$XYQ_DIR/deploy/cn"

# ---------- 5) 生成 .env ----------
hr
blue "[5/7] 生成 .env..."
if [ -f .env ]; then
  yellow ".env 已存在，保留现有值（如需重置请删除后重跑）"
else
  PGPASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
  JWTSEC=$(openssl rand -base64 48 | tr -d '/+=' | head -c 64)
  cp .env.example .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|" .env
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWTSEC}|" .env
  sed -i "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" .env
  sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=${ACME_EMAIL}|" .env

  IP=$(curl -fsS https://ipinfo.io/ip || curl -fsS https://ifconfig.me || echo "your-server-ip")
  PROTO="http"; HOST="$IP"
  if [ "$DOMAIN" != ":80" ]; then
    PROTO="https"; HOST="$DOMAIN"
  fi
  sed -i "s|^SITE_URL=.*|SITE_URL=${PROTO}://${HOST}|" .env
  sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=${PROTO}://${HOST}|" .env

  green ".env 已生成（POSTGRES_PASSWORD 与 JWT_SECRET 为强随机）"
fi

# ---------- 6) 构建 + 启动 ----------
hr
blue "[6/7] 构建镜像 + 启动服务（首次约 5-10 分钟）..."
docker compose -f docker-compose.yml --env-file .env pull caddy postgres || true
docker compose -f docker-compose.yml --env-file .env build
docker compose -f docker-compose.yml --env-file .env up -d

# ---------- 7) 等 backend 就绪 ----------
hr
blue "[7/7] 等待后端 health..."
for i in $(seq 1 60); do
  if docker exec xyq-backend curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    green "Backend 已就绪"
    break
  fi
  printf '.'
  sleep 5
done
echo

# ---------- DONE ----------
IP=$(curl -fsS https://ipinfo.io/ip || curl -fsS https://ifconfig.me || echo "your-server-ip")
hr
green "============================================================"
green "  部署完成！"
green "============================================================"
if [ "$DOMAIN" = ":80" ]; then
  green "  前台访问：http://${IP}/"
  green "  后端 API：http://${IP}/api/health"
  yellow "  提示：当前为 HTTP（IP 直连）。要启用 HTTPS："
  yellow "        1) 把域名 A 记录指向 ${IP}"
  yellow "        2) 编辑 ${XYQ_DIR}/deploy/cn/.env 设置 DOMAIN + ACME_EMAIL"
  yellow "        3) docker compose -f docker-compose.yml --env-file .env up -d caddy"
else
  green "  前台访问：https://${DOMAIN}/"
  green "  后端 API：https://${DOMAIN}/api/health"
fi
hr
green "  常用命令："
green "    cd ${XYQ_DIR}/deploy/cn"
green "    docker compose --env-file .env logs -f backend"
green "    docker compose --env-file .env restart backend"
green "    docker compose --env-file .env pull && docker compose --env-file .env up -d --build  # 升级"
hr
