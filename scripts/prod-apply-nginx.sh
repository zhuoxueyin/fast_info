#!/usr/bin/env bash
# 热更新生产 web 容器内的 nginx 配置(无需整镜像 rebuild)
# 用法: bash scripts/prod-apply-nginx.sh
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
CONF="$PROJECT_ROOT/docker/nginx/default.conf"
CONTAINER="${FASTINFO_WEB_CONTAINER:-fast_info-web-1}"

[ -f "$CONF" ] || { echo "missing $CONF"; exit 1; }
docker inspect "$CONTAINER" >/dev/null 2>&1 || { echo "container $CONTAINER not running"; exit 1; }

docker cp "$CONF" "$CONTAINER:/etc/nginx/conf.d/default.conf"
# 先测试配置,再 reload;失败则 restart
if docker exec "$CONTAINER" nginx -t; then
  docker exec "$CONTAINER" nginx -s reload
  echo "[OK] nginx config reloaded in $CONTAINER"
else
  echo "[WARN] nginx -t failed, restarting container"
  docker restart "$CONTAINER"
fi

sleep 2
code=$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 http://127.0.0.1:18080/healthz || echo 000)
echo "healthz via 18080 → HTTP $code"
[ "$code" = "200" ] || exit 1
