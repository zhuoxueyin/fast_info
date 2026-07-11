#!/usr/bin/env bash
# fast_info_dev 与 fast_info(180xx) 同机并行: 使用 280xx 端口段
set -euo pipefail
cd "$(dirname "$0")/.."
export FASTINFO_API_PORT=28000
export FASTINFO_WEB_PORT=28080
export FASTINFO_MONGO_PORT=27019
export FASTINFO_REDIS_PORT=6381
docker compose up -d "$@"
echo "Web: http://$(hostname -I | awk '{print $1}'):28080/"
echo "API: http://$(hostname -I | awk '{print $1}'):28000/healthz"
