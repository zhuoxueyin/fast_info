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

# 检查 env 模板与实例是否同步(防止 .example 更新后 .local 缺 key)
log "   检查 env 模板与实例同步..."
if ! bash scripts/check-env-sync.sh dotenv > /tmp/fastinfo-env-sync.log 2>&1; then
  err ".env 与 .env.example 不同步"
  cat /tmp/fastinfo-env-sync.log
  exit 1
fi
if [ -f docker/env.prod.local ]; then
  if ! bash scripts/check-env-sync.sh prod > /tmp/fastinfo-env-sync.log 2>&1; then
    err "docker/env.prod.local 与模板不同步"
    cat /tmp/fastinfo-env-sync.log
    exit 1
  fi
elif [ -f docker/env.docker.local ]; then
  if ! bash scripts/check-env-sync.sh docker > /tmp/fastinfo-env-sync.log 2>&1; then
    err "docker/env.docker.local 与模板不同步"
    cat /tmp/fastinfo-env-sync.log
    exit 1
  fi
fi
log "   ✅ env 同步检查通过"

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
# 根据系统内存自动选择构建策略：低内存机器串行 + 限内存构建
# shellcheck source=scripts/build-helpers.sh
source scripts/build-helpers.sh
build_with_memory_awareness
log "   ✅ build 完成"

# === 4. restart ===
log "4/6 restart containers"
# 生产机若残留 dev 项目,会抢 2C4G 内存/swap — 明确告警
if docker ps --format '{{.Names}}' | grep -q '^fast_info_dev-'; then
  warn "!! 检测到 fast_info_dev-* 容器在跑(同机 dev)"
  warn "!! 2C4G 生产建议: cd /home/ubuntu/fast_info_dev && docker compose stop"
fi

docker compose up -d --remove-orphans

# api 重建后,强制让 web 重新挂上网络/配置(防 Nginx 上游陈旧 + 确保新 conf 生效)
# 动态 resolver 已修根因,这里仍 recreate web 作为部署期双保险
log "   force-recreate web (ensure nginx↔api linkage)"
docker compose up -d --no-deps --force-recreate web

# 健康检查总开关,admin 初始化失败也视为部署异常
HEALTH_OK=true

# === 4.5 确保 admin 账号存在 ===
log "4.5/6 确保 admin 账号存在"
ADMIN_USERNAME="${FASTINFO_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${FASTINFO_ADMIN_PASSWORD:-admin@2026}"

# 等 api 容器进入 running 状态,最多 60s
for i in $(seq 1 60); do
  if docker compose ps api --status running --format json 2>/dev/null | grep -qE '"Service":"api"|"Name":"fast_info-api'; then
    break
  fi
  # 兼容旧 compose 输出
  if docker compose ps --status running 2>/dev/null | grep -qE 'api'; then
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

# === 5. 健康检查(带重试) ===
log "5/6 健康检查"
sleep 8

check_url() {
  local url="$1"
  local name="$2"
  local i code
  for i in 1 2 3 4 5 6; do
    code=$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 15 "$url" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then
      log "   ✅ $name 200"
      return 0
    fi
    sleep 5
  done
  err "   ❌ $name 失败(last HTTP $code)"
  return 1
}

# 5.1 直连 API
if ! check_url "http://127.0.0.1:18000/healthz" "API direct /healthz (18000)"; then
  HEALTH_OK=false
fi

# 5.2 经 Nginx
if ! check_url "http://127.0.0.1:18080/healthz" "Nginx /healthz (18080)"; then
  warn "   尝试热修 nginx 配置 / 重启 web..."
  bash "$PROJECT_ROOT/scripts/prod-apply-nginx.sh" || docker compose restart web || true
  sleep 4
  if ! check_url "http://127.0.0.1:18080/healthz" "Nginx /healthz (retry)"; then
    HEALTH_OK=false
  fi
fi

# 5.3 /api/stats
if ! check_url "http://127.0.0.1:18080/api/stats" "/api/stats"; then
  warn "   !! /api/stats 异常,可能是 mongo 没起"
  HEALTH_OK=false
fi

# 5.4 公网域名(若本机可解析)
if ! check_url "https://kemi-ai.cn/healthz" "public https://kemi-ai.cn/healthz"; then
  warn "   公网 healthz 失败 — 检查 Caddy 与证书,不直接判部署失败(可能是 DNS/证书窗口)"
fi

# 5.5 容器状态
RUNNING_COUNT=$(docker compose ps --status running 2>/dev/null | tail -n +2 | wc -l)
TOTAL_COUNT=$(docker compose ps 2>/dev/null | tail -n +2 | wc -l)
if [ "$RUNNING_COUNT" -eq "$TOTAL_COUNT" ] && [ "$RUNNING_COUNT" -gt 0 ]; then
  log "   ✅ 全部 $RUNNING_COUNT 个容器 Up"
else
  err "   ❌ 容器状态异常:$RUNNING_COUNT/$TOTAL_COUNT"
  HEALTH_OK=false
fi

# 5.6 安装/刷新 watchdog(幂等)
if [ -x "$PROJECT_ROOT/scripts/prod-watchdog.sh" ] || [ -f "$PROJECT_ROOT/scripts/prod-watchdog.sh" ]; then
  chmod +x "$PROJECT_ROOT/scripts/prod-watchdog.sh" "$PROJECT_ROOT/scripts/prod-apply-nginx.sh" 2>/dev/null || true
  bash "$PROJECT_ROOT/scripts/prod-watchdog.sh" --install || warn "watchdog cron 安装失败(可稍后手动)"
fi

# === 6. 收尾 ===
echo ""
if [ "$HEALTH_OK" = true ]; then
  log "6/6 ✅ 部署完成 · $DEPLOYED_COMMIT · $(date -Iseconds)"
  log "   浏览器访问:https://kemi-ai.cn/  或 http://<SERVER_IP>:18080/"
  log "   自愈检查:bash scripts/prod-watchdog.sh --status"
  exit 0
else
  err "6/6 ❌ 健康检查失败"
  log "   查日志:cd $PROJECT_ROOT && docker compose logs --tail=80 api web"
  log "   自愈:bash scripts/prod-watchdog.sh"
  exit 1
fi
