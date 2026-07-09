#!/usr/bin/env bash
# fastInfo · 生产入口自愈(轻量 watchdog)
# =====================================================
# 目标:保证 https://kemi-ai.cn 入口链路可用
# 检查: Caddy(:443) → web(:18080) → api(:8000)
# 策略:
#   1) 直连 API 不通 → 重启 api(严重)
#   2) API 通但经 web/nginx 502 → 重启 web(经典 DNS 缓存坑)
#   3) 本机 18080 通但公网/本机 https 不通 → 重启 caddy
# 用法:
#   bash scripts/prod-watchdog.sh           # 单次检查
#   bash scripts/prod-watchdog.sh --install # 安装到 cron(每 2 分钟)
#   bash scripts/prod-watchdog.sh --status  # 看最近日志
# =====================================================
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
LOG_DIR="${PROJECT_ROOT}/data"
LOG_FILE="${LOG_DIR}/prod-watchdog.log"
LOCK_FILE="/tmp/fastinfo-prod-watchdog.lock"
COMPOSE_PROJECT="${FASTINFO_COMPOSE_PROJECT:-fast_info}"
WEB_URL="${FASTINFO_WATCH_WEB_URL:-http://127.0.0.1:18080/healthz}"
API_URL="${FASTINFO_WATCH_API_URL:-http://127.0.0.1:18000/healthz}"
PUBLIC_URL="${FASTINFO_WATCH_PUBLIC_URL:-https://kemi-ai.cn/healthz}"

mkdir -p "$LOG_DIR"

ts() { date -Iseconds; }
log()  { echo "$(ts) [OK]  $*" | tee -a "$LOG_FILE"; }
warn() { echo "$(ts) [WARN] $*" | tee -a "$LOG_FILE"; }
err()  { echo "$(ts) [FAIL] $*" | tee -a "$LOG_FILE"; }

http_code() {
  local url="$1"
  curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 12 "$url" 2>/dev/null || echo "000"
}

compose() {
  docker compose -p "$COMPOSE_PROJECT" -f "$PROJECT_ROOT/docker-compose.yml" "$@"
}

restart_service() {
  local svc="$1"
  warn "restarting compose service: $svc"
  if compose restart "$svc" >>"$LOG_FILE" 2>&1; then
    log "restarted $svc"
    return 0
  fi
  err "failed to restart $svc"
  return 1
}

restart_caddy() {
  if systemctl is-active --quiet caddy 2>/dev/null; then
    warn "restarting caddy"
    if sudo -n systemctl restart caddy >>"$LOG_FILE" 2>&1; then
      log "restarted caddy"
      return 0
    fi
    err "failed to restart caddy (need passwordless sudo systemctl restart caddy?)"
    return 1
  fi
  warn "caddy not active via systemd, skip"
  return 0
}

install_cron() {
  local cron_line="*/2 * * * * cd $PROJECT_ROOT && /bin/bash $SCRIPT_DIR/prod-watchdog.sh >> $LOG_FILE 2>&1"
  # 幂等:先删旧行再加
  ( crontab -l 2>/dev/null | grep -v 'scripts/prod-watchdog.sh' || true
    echo "$cron_line"
  ) | crontab -
  log "installed cron: every 2 min → $SCRIPT_DIR/prod-watchdog.sh"
  crontab -l | grep prod-watchdog || true
}

show_status() {
  echo "=== last 30 log lines ($LOG_FILE) ==="
  tail -n 30 "$LOG_FILE" 2>/dev/null || echo "(no log yet)"
  echo
  echo "=== live probes ==="
  echo "api  $API_URL  → $(http_code "$API_URL")"
  echo "web  $WEB_URL  → $(http_code "$WEB_URL")"
  echo "pub  $PUBLIC_URL → $(http_code "$PUBLIC_URL")"
  echo
  echo "=== containers ($COMPOSE_PROJECT) ==="
  docker ps --filter "name=${COMPOSE_PROJECT}-" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
}

check_once() {
  # 防并发
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    warn "another watchdog running, skip"
    return 0
  fi

  local api_code web_code pub_code
  api_code="$(http_code "$API_URL")"
  web_code="$(http_code "$WEB_URL")"
  pub_code="$(http_code "$PUBLIC_URL")"

  if [ "$api_code" = "200" ] && [ "$web_code" = "200" ] && [ "$pub_code" = "200" ]; then
    # 正常时不刷屏:每小时落一条心跳(靠分钟判断粗粒度)
    local minute
    minute="$(date +%M)"
    if [ "$minute" = "00" ] || [ "$minute" = "30" ]; then
      log "healthy api=$api_code web=$web_code public=$pub_code"
    fi
    return 0
  fi

  err "unhealthy api=$api_code web=$web_code public=$pub_code — healing"

  # 1) API 挂 → 重启 api,等健康
  if [ "$api_code" != "200" ]; then
    restart_service api || true
    sleep 8
    api_code="$(http_code "$API_URL")"
  fi

  # 2) API 好但 web 反代坏 → 重启 web
  web_code="$(http_code "$WEB_URL")"
  if [ "$api_code" = "200" ] && [ "$web_code" != "200" ]; then
    restart_service web || true
    sleep 4
    web_code="$(http_code "$WEB_URL")"
  fi

  # 3) 本机 web 好但公网/https 不通 → 重启 caddy
  pub_code="$(http_code "$PUBLIC_URL")"
  web_code="$(http_code "$WEB_URL")"
  if [ "$web_code" = "200" ] && [ "$pub_code" != "200" ]; then
    restart_caddy || true
    sleep 3
    pub_code="$(http_code "$PUBLIC_URL")"
  fi

  api_code="$(http_code "$API_URL")"
  web_code="$(http_code "$WEB_URL")"
  pub_code="$(http_code "$PUBLIC_URL")"

  if [ "$api_code" = "200" ] && [ "$web_code" = "200" ] && [ "$pub_code" = "200" ]; then
    log "healed api=$api_code web=$web_code public=$pub_code"
    return 0
  fi

  err "still unhealthy after heal api=$api_code web=$web_code public=$pub_code"
  return 1
}

case "${1:-}" in
  --install) install_cron ;;
  --status)  show_status ;;
  ""|--check) check_once ;;
  *)
    echo "usage: $0 [--check|--install|--status]"
    exit 2
    ;;
esac
