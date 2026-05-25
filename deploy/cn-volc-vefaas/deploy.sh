#!/usr/bin/env bash
# =============================================================================
# 小云雀 AI 漫剧 -> 火山引擎 veFaaS 一键部署 (macOS / Linux / Git-Bash)
# =============================================================================
set -euo pipefail

IMAGE_TAG=""
APP_NAME="xyq-manju"
IMAGE_REPO=""
SKIP_BUILD=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image-tag) IMAGE_TAG="$2"; shift 2 ;;
    --app-name) APP_NAME="$2"; shift 2 ;;
    --image-repo) IMAGE_REPO="$2"; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      grep '^#' "$0" | head -20
      exit 0 ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# 加载已同步的全局 keys (Unix 用户)
if [[ -f "$HOME/.config/api-keys/xyq.env" ]]; then
  set -a; source "$HOME/.config/api-keys/xyq.env"; set +a
fi

: "${VOLC_ACCESS_KEY:?need VOLC_ACCESS_KEY (run scripts/sync_keys_to_windows.sh first)}"
: "${VOLC_SECRET_KEY:?need VOLC_SECRET_KEY}"
: "${VOLC_REGION:=cn-beijing}"

[[ -z "$IMAGE_TAG" ]] && IMAGE_TAG="v9.$(date +%Y%m%d%H%M)"
[[ -z "$IMAGE_REPO" ]] && IMAGE_REPO="cr-${VOLC_REGION}.volces.com/xyq/manju"
FULL_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

echo
echo "=========================================================="
echo "  小云雀 AI 漫剧 -> veFaaS (v9)"
echo "=========================================================="
echo "Image:    $FULL_IMAGE"
echo "AppName:  $APP_NAME"
echo "Region:   $VOLC_REGION"
echo "DryRun:   $DRY_RUN"
echo

if [[ "$SKIP_BUILD" == "0" ]]; then
  echo "[1/3] docker build"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [DRY] docker build -f deploy/cn-volc-vefaas/Dockerfile.vefaas -t $FULL_IMAGE --platform linux/amd64 ."
  else
    docker build -f deploy/cn-volc-vefaas/Dockerfile.vefaas -t "$FULL_IMAGE" --platform linux/amd64 .
  fi

  echo "[2/3] docker push"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [DRY] docker push $FULL_IMAGE"
  else
    docker push "$FULL_IMAGE"
  fi
else
  echo "[1-2/3] 跳过 build/push (--skip-build)"
fi

echo "[3/3] python deploy.py"
PY_ARGS=(deploy/cn-volc-vefaas/deploy.py --app-name "$APP_NAME"
         --image-repo "$IMAGE_REPO" --image-tag "$IMAGE_TAG")
[[ "$DRY_RUN" == "1" ]] && PY_ARGS+=(--dry-run)

python "${PY_ARGS[@]}"

echo
echo "完成! 验证: python scripts/verify_volc_chain.py --live"
