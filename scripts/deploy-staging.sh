#!/usr/bin/env bash
# fastInfo · S 预发布环境部署(本机 docker)
# =====================================================
# 适用:本机完整模拟生产环境(全部 6 服务起在 docker)
# 端口:18000/18080/27018/6380(语义化 5 位数)
# 用法:bash scripts/deploy-staging.sh
# =====================================================

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { printf "${GREEN}==>${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}!!>${NC} %s\n" "$1"; }
err()  { printf "${RED}xx>${NC} %s\n" "$1"; }

# === 0. 前置检查 ===
log "0/5 前置检查"

command -v docker &> /dev/null || { err "docker 未装"; exit 1; }
docker compose version &> /dev/null || { err "docker compose v2 未装"; exit 1; }
[ -f docker-compose.yml ] || { err "找不到 docker-compose.yml"; exit 1; }
[ -f .env ] || { err ".env 不存在,先 cp .env.example .env 并填密钥"; exit 1; }
[ -f docker/env.docker.local ] || {
  err "docker/env.docker.local 不存在,先 cp docker/env.docker.local.example docker/env.docker.local"
  exit 1
}
grep -q "^MMX_API_KEY=.\+" .env || {
  err ".env 里 MMX_API_KEY 没填,服务起来 LLM 调用也会失败"
  exit 1
}

# 检查 env 模板与实例是否同步
log "   检查 env 模板与实例同步..."
if ! bash scripts/check-env-sync.sh > /tmp/fastinfo-env-sync.log 2>&1; then
  err "env 文件与模板不同步"
  cat /tmp/fastinfo-env-sync.log
  exit 1
fi
log "   ✅ env 同步检查通过"

log "   ✅ 全部通过"

# === 1. 清理旧容器(保留数据卷) ===
log "1/5 清理旧容器(mongo/redis 数据卷保留)"
docker compose down --remove-orphans 2>/dev/null || true

# === 2. build ===
log "2/5 build 镜像(5-15 分钟,慢是预期)"
docker compose build
log "   ✅ build 完成"

# === 3. up ===
log "3/5 启动 6 服务"
docker compose up -d

# === 4. 健康检查 ===
log "4/5 健康检查"
sleep 20

# 4.1 容器状态
RUNNING=$(docker compose ps --status running 2>/dev/null | tail -n +2 | wc -l)
TOTAL=$(docker compose ps 2>/dev/null | tail -n +2 | wc -l)
if [ "$TOTAL" -lt 6 ]; then
  err "只起 $TOTAL 个 service,期望 6 个,看 docker compose ps"
  docker compose ps
  exit 1
fi
if [ "$RUNNING" -ne "$TOTAL" ]; then
  err "容器状态异常:$RUNNING/$TOTAL 在跑"
  docker compose ps
  docker compose logs --tail=80 api
  exit 1
fi
log "   ✅ $RUNNING 个容器 Up"

# 4.2 API 走 Nginx
if curl -sf http://127.0.0.1:18080/healthz > /dev/null; then
  log "   ✅ /healthz (走 Nginx 18080) 200"
else
  err "   ❌ /healthz 失败"
  docker compose logs --tail=80 api
  exit 1
fi

# 4.3 API 直连
if curl -sf http://127.0.0.1:18000/healthz > /dev/null; then
  log "   ✅ /healthz (直连 18000) 200"
else
  warn "   !! /healthz 直连失败,但 Nginx 通了,可能是端口没映射"
fi

# 4.4 /api/stats
if curl -sf http://127.0.0.1:18080/api/stats > /dev/null; then
  log "   ✅ /api/stats 200"
else
  err "   ❌ /api/stats 失败,可能是 mongo 没连上"
  exit 1
fi

# === 5. 收尾 ===
log "5/5 ✅ 预发部署完成 · $(date -Iseconds)"
echo ""
echo "  ${GREEN}访问入口(S 模式用 5 位数端口):${NC}"
echo "    Web(Nginx)  http://127.0.0.1:18080/"
echo "    API 直连    http://127.0.0.1:18000/healthz"
echo "    Swagger     http://127.0.0.1:18080/swagger"
echo "    Docs        http://127.0.0.1:18080/docs/"
echo "    Mongo       127.0.0.1:27018"
echo "    Redis       127.0.0.1:6380"
echo ""
echo "  ${YELLOW}查看日志:${NC}  docker compose logs -f"
echo "  ${YELLOW}停止:${NC}      docker compose down    (保留数据卷)"
echo "  ${YELLOW}完全清理:${NC}  docker compose down -v (⚠️ 删数据卷)"
echo ""
