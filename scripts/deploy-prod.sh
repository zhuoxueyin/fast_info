#!/usr/bin/env bash
# fastInfo · P 正式环境服务器拉起/更新
# =====================================================
# 适用:腾讯云/阿里云轻量服务器,云端完整部署
# 流程:git pull → build → up → 健康检查
# 用法:
#   bash scripts/deploy-prod.sh                 # 拉 origin/master
#   bash scripts/deploy-prod.sh <commit-sha>    # 部署指定 commit
# =====================================================
# 唯一权威源:docs/deploy-runbook.md §3.7(改脚本改文档)

set -euo pipefail

TARGET_COMMIT="${1:-}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { printf "${GREEN}==>${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}!!>${NC} %s\n" "$1"; }
err()  { printf "${RED}xx>${NC} %s\n" "$1"; }

# === 0. 前置检查 ===
log "0/5 前置检查"

command -v docker &> /dev/null || { err "docker 未装,先跑 apt-get install -y docker.io docker-compose-v2"; exit 1; }
docker compose version &> /dev/null || { err "docker compose v2 未装"; exit 1; }
[ -f docker-compose.yml ] || { err "找不到 docker-compose.yml(当前目录:$PROJECT_ROOT)"; exit 1; }
[ -f .env ] || { err ".env 不存在,先 cp .env.example .env 并填密钥"; exit 1; }
[ -f docker/env.docker.local ] || { err "docker/env.docker.local 不存在,先 cp docker/env.docker.local.example docker/env.docker.local"; exit 1; }
grep -q "^MMX_API_KEY=.\+" .env || { err ".env 里 MMX_API_KEY 没填,服务起来 LLM 调用也会失败"; exit 1; }

log "   ✅ 全部通过"

# === 1. 同步代码 ===
log "1/5 同步代码"

if [ -n "$TARGET_COMMIT" ]; then
  log "   部署到指定 commit:$TARGET_COMMIT"
  git fetch origin
  git reset --hard "$TARGET_COMMIT"
else
  log "   拉 origin/master"
  git fetch origin
  git reset --hard origin/master
fi

git clean -fdx   # 清掉未跟踪文件

DEPLOYED_COMMIT=$(git rev-parse --short HEAD)
log "   当前 commit:$DEPLOYED_COMMIT"

# === 2. build ===
log "2/5 build 新镜像(5-15 分钟)"
docker compose build
log "   ✅ build 完成"

# === 3. restart ===
log "3/5 restart containers"
docker compose up -d --remove-orphans

# === 4. 健康检查 ===
log "4/5 健康检查"
sleep 20

HEALTH_OK=true

# 4.1 /healthz 走 Nginx
if curl -sf http://127.0.0.1:18080/healthz > /dev/null; then
  log "   ✅ API /healthz (Nginx 18080) 200"
else
  err "   ❌ /healthz 失败"
  HEALTH_OK=false
fi

# 4.2 /api/stats
if curl -sf http://127.0.0.1:18080/api/stats > /dev/null; then
  log "   ✅ /api/stats 200"
else
  warn "   !! /api/stats 异常,可能是 mongo 没起"
  HEALTH_OK=false
fi

# 4.3 容器状态
RUNNING_COUNT=$(docker compose ps --status running 2>/dev/null | tail -n +2 | wc -l)
TOTAL_COUNT=$(docker compose ps 2>/dev/null | tail -n +2 | wc -l)
if [ "$RUNNING_COUNT" -eq "$TOTAL_COUNT" ] && [ "$RUNNING_COUNT" -gt 0 ]; then
  log "   ✅ 全部 $RUNNING_COUNT 个容器 Up"
else
  err "   ❌ 容器状态异常:$RUNNING_COUNT/$TOTAL_COUNT"
  HEALTH_OK=false
fi

# === 5. 收尾 ===
echo ""
if [ "$HEALTH_OK" = true ]; then
  log "5/5 ✅ 部署完成 · $DEPLOYED_COMMIT · $(date -Iseconds)"
  log "   浏览器访问:http://<SERVER_IP>:18080/"
  exit 0
else
  err "5/5 ❌ 健康检查失败"
  log "   查日志:cd $PROJECT_ROOT && docker compose logs --tail=80 api"
  exit 1
fi
