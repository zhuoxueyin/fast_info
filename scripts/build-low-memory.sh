#!/usr/bin/env bash
#
# 低内存服务器（如 1.8 GB 内存、无 swap）上构建 Docker 镜像时使用。
# 通过限制 docker compose 并行度和单个构建容器内存，降低前端构建 OOM 概率。
#
# 用法：
#   scripts/build-low-memory.sh [service...]
#   例：scripts/build-low-memory.sh web
#   例：scripts/build-low-memory.sh api web ingest_daemon subs_scheduler
#
# 不传参数时默认只构建 web。
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 未传参数时默认构建 web
if [ "$#" -eq 0 ]; then
  SERVICES=("web")
else
  SERVICES=("$@")
fi

cd "${PROJECT_ROOT}"

# 提示当前内存 / swap 情况
TOTAL_MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
TOTAL_SWAP_KB=$(awk '/SwapTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))
TOTAL_SWAP_MB=$((TOTAL_SWAP_KB / 1024))

echo "Detected memory: ${TOTAL_MEM_MB} MB, swap: ${TOTAL_SWAP_MB} MB"

if [ "${TOTAL_SWAP_MB}" -eq 0 ]; then
  echo "WARNING: No swap detected. If build still OOMs, run:" >&2
  echo "  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile" >&2
fi

# 构建参数说明：
#   DOCKER_BUILDKIT=0          禁用 BuildKit，因为 BuildKit 不支持 --memory 限制构建容器内存
#   COMPOSE_PARALLEL_LIMIT=1   串行构建 service，避免多个服务同时构建抢占内存
#   --memory 1800m             限制单个构建容器最多使用 1.8 GB 物理内存
for SERVICE in "${SERVICES[@]}"; do
  echo ""
  echo "Building service: ${SERVICE}"
  DOCKER_BUILDKIT=0 \
  COMPOSE_PARALLEL_LIMIT=1 \
    docker compose build \
      --memory 1800m \
      "${SERVICE}"
  echo "Build finished: ${SERVICE}"
done

echo ""
echo "All requested services built: ${SERVICES[*]}"
