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
log "0/6 前置检查"

command -v docker &> /dev/null || { err "docker 未装,先跑 apt-get install -y docker.io docker-compose-v2"; exit 1; }
docker compose version &> /dev/null || { err "docker compose v2 未装"; exit 1; }
[ -f docker-compose.yml ] || { err "找不到 docker-compose.yml(当前目录:$PROJECT_ROOT)"; exit 1; }
[ -f .env ] || { err ".env 不存在,先 cp .env.example .env 并填密钥"; exit 1; }
# 生产环境优先用 docker/env.prod.local(APP_ENV=prod, MONGO_DB=fastinfo_prod)
# 如果没有,fallback 到 docker/env.docker.local(预发配置)并 WARN
if [ -f docker/env.prod.local ]; then
  log "   ✅ 使用生产专用配置 docker/env.prod.local"
elif [ -f docker/env.docker.local ]; then
  warn "!! 找不到 docker/env.prod.local,fallback 到 docker/env.docker.local"
  warn "!! 强烈建议:cp docker/env.prod.local.example docker/env.prod.local 并填入生产专用值"
  warn "!! 否则生产进程会拿到 APP_ENV=docker,和数据隔离设计冲突"
else
  err "docker/env.prod.local 和 docker/env.docker.local 都不存在,先 cp 其中一个对应模板"; exit 1
fi
grep -q "^MMX_API_KEY=.\+" .env || { err ".env 里 MMX_API_KEY 没填,服务起来 LLM 调用也会失败"; exit 1; }

# 将 .env(共享配置)和最终选用的 env_file(环境差异)导入当前 shell,
# 方便部署脚本读取 FASTINFO_ADMIN_PASSWORD 等变量
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi
ENV_FILE="${FASTINFO_ENV_FILE:-docker/env.prod.local}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

log "   ✅ 全部通过"

# === 1. 分支检查 (P 环境必须跑 master) ===
log "1/6 分支检查"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
if [ -z "$TARGET_COMMIT" ] && [ "$CURRENT_BRANCH" != "master" ]; then
  err "P 正式环境必须部署 master 分支，当前分支是 '$CURRENT_BRANCH'"
  err "请执行: git checkout master && git pull origin master"
  err "或指定 commit 回滚: bash scripts/deploy-prod.sh <commit-sha>"
  exit 1
fi
log "   ✅ 当前分支:$CURRENT_BRANCH"

# === 2. 同步代码 ===
log "2/6 同步代码"

if [ -n "$TARGET_COMMIT" ]; then
  log "   部署到指定 commit:$TARGET_COMMIT"
  git fetch origin
  git reset --hard "$TARGET_COMMIT"
else
  log "   拉 origin/master"
  git fetch origin
  git reset --hard origin/master
fi

# 清掉未跟踪文件，但保留 env 配置文件(里面有机密)
git clean -fdx -e .env -e docker/env.docker.local -e docker/env.prod.local

DEPLOYED_COMMIT=$(git rev-parse --short HEAD)
log "   当前 commit:$DEPLOYED_COMMIT"

# === 3. build ===
log "3/6 build 新镜像(5-15 分钟)"
# 让 docker-compose 优先用 prod 专用 env_file
# (在 fallback 到 env.docker.local 时已 WARN,这里只是补一刀防止误用)
export FASTINFO_ENV_FILE="${FASTINFO_ENV_FILE:-docker/env.prod.local}"
log "   FASTINFO_ENV_FILE=$FASTINFO_ENV_FILE"
docker compose build
log "   ✅ build 完成"

# === 4. restart ===
log "4/6 restart containers"
docker compose up -d --remove-orphans

# 健康检查总开关,admin 初始化失败也视为部署异常
HEALTH_OK=true

# === 4.5 确保 admin 账号存在 ===
log "4.5/6 确保 admin 账号存在"
ADMIN_USERNAME="${FASTINFO_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${FASTINFO_ADMIN_PASSWORD:-admin@2026}"

# 等 api 容器进入 running 状态,最多 30s
for i in $(seq 1 30); do
  if docker compose ps api --status running --format json 2>/dev/null | grep -q '"Name":"fastinfo-api"'; then
    break
  fi
  sleep 1
done

if docker compose exec -T api python scripts/init_admin.py --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" > /tmp/fastinfo-init-admin.log 2>&1; then
  log "   ✅ admin 账号检查/创建完成(如已存在则幂等跳过)"
  grep -E "username:|password:" /tmp/fastinfo-init-admin.log || true
else
  err "   ❌ admin 初始化失败"
  cat /tmp/fastinfo-init-admin.log
  HEALTH_OK=false
fi

# === 5. 健康检查 ===
log "5/6 健康检查"
sleep 20

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

# === 6. 收尾 ===
echo ""
if [ "$HEALTH_OK" = true ]; then
  log "6/6 ✅ 部署完成 · $DEPLOYED_COMMIT · $(date -Iseconds)"
  log "   浏览器访问:http://<SERVER_IP>:18080/"
  exit 0
else
  err "6/6 ❌ 健康检查失败"
  log "   查日志:cd $PROJECT_ROOT && docker compose logs --tail=80 api"
  exit 1
fi
