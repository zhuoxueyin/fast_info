#!/usr/bin/env bash
# fastInfo · L 本地开发模式部署
# =====================================================
# 适用:本机直接开发(无 docker,或仅起 mongo+redis)
# 启动方式:venv + start.ps1 启 API / ingest / scheduler
# 用法:bash scripts/deploy-local.sh
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
log "0/4 前置检查"

# 1) Python venv
if [ ! -d ".venv" ]; then
  err ".venv 不存在,先建:"
  echo "    python -m venv .venv"
  echo "    .venv/Scripts/Activate.ps1   # Windows"
  echo "    pip install -r requirements.txt"
  exit 1
fi
log "   ✅ .venv OK"

# 2) .env
if [ ! -f ".env" ]; then
  warn ".env 不存在,从 .env.example 复制"
  cp .env.example .env
  err "请编辑 .env 填入 MMX_API_KEY,再重跑本脚本"
  exit 1
fi
log "   ✅ .env OK"

# 3) docker(只用来跑 mongo+redis,API 走 venv)
if ! command -v docker &> /dev/null; then
  err "docker 未装。本地模式可以不用 docker,直接装本机 MongoDB/Redis"
  err "或者装 Docker Desktop 后重跑"
  exit 1
fi
log "   ✅ docker OK"

# === 1. 起基础数据层(mongo + redis) ===
log "1/4 启动 mongo + redis(基础数据层)"
docker compose up -d mongo redis
sleep 5

if ! docker compose ps mongo --status running | grep -q running; then
  err "mongo 没起来,看 docker compose logs mongo"
  exit 1
fi
if ! docker compose ps redis --status running | grep -q running; then
  err "redis 没起来,看 docker compose logs redis"
  exit 1
fi
log "   ✅ mongo + redis Up"

# === 2. 验收数据层 ===
log "2/4 验收数据层"
sleep 3
if docker compose exec -T mongo mongosh --quiet --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q "1"; then
  log "   ✅ mongo ping OK"
else
  err "mongo ping 失败"
  exit 1
fi

# === 3. 提示启动 API ===
log "3/4 数据层就绪 ✅"
echo ""
echo "  ${GREEN}接下来请在另一个终端跑以下任一方式:${NC}"
echo ""
echo "  ${YELLOW}[方式 1]${NC} 一键全起(PowerShell,推荐 Windows 开发者):"
echo "    .\\start.ps1"
echo ""
echo "  ${YELLOW}[方式 2]${NC} 单独起(适合 IDE 调试):"
echo "    .venv\\Scripts\\Activate.ps1"
echo "    python scripts/api_server.py                       # API"
echo "    python scripts/ingest_daemon.py --interval 1800    # 抓取"
echo "    python scripts/subs_scheduler.py --interval 60     # 调度"
echo "    cd frontend && npm run dev                          # 前端"
echo "    cd docs-site && npm run dev                         # 文档"
echo ""
echo "  ${YELLOW}[方式 3]${NC} Linux/macOS:"
echo "    source .venv/bin/activate"
echo "    python scripts/api_server.py"
echo ""

# === 4. 收尾 ===
log "4/4 ✅ L 本地环境就绪"
echo ""
echo "  ${GREEN}访问入口(L 模式用经典端口):${NC}"
echo "    API        http://127.0.0.1:8000/healthz"
echo "    Swagger    http://127.0.0.1:8000/docs"
echo "    前端 dev   http://127.0.0.1:5173/"
echo "    文档 dev   http://127.0.0.1:5174/"
echo "    Mongo      127.0.0.1:27018   (docker 端口)"
echo "    Redis      127.0.0.1:6380    (docker 端口)"
echo ""
