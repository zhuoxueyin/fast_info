#!/usr/bin/env bash
# fastInfo · API 启动 / 停止 / 重启 (Linux/macOS)
# ==================================================
# 严格只动 fast_info 自己的 api_server 进程,不误伤其他项目。
# 用法:
#   bash scripts/restart_api.sh              # 默认:stop + start
#   bash scripts/restart_api.sh start
#   bash scripts/restart_api.sh stop
#   bash scripts/restart_api.sh restart      # 默认
#   bash scripts/restart_api.sh status
#   bash scripts/restart_api.sh log

set -euo pipefail

ACTION="${1:-restart}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
LOG_FILE="$PROJECT_ROOT/data/api-server.log"
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

get_api_pids() {
    # ps 输出找包含 fast_info + api_server 的 python 进程
    ps -ef | grep -E "python.*fast_info.*api_server" | grep -v grep | awk '{print $2}'
}

case "$ACTION" in
    status)
        PIDS=$(get_api_pids || true)
        if [ -n "$PIDS" ]; then
            ps -ef | grep -E "python.*fast_info.*api_server" | grep -v grep
        else
            echo "  (无 fastInfo API 进程在跑)"
        fi
        ;;

    stop)
        PIDS=$(get_api_pids || true)
        if [ -n "$PIDS" ]; then
            echo "  停止 fastInfo API 进程 (PID=$PIDS)"
            kill $PIDS
            sleep 1
        else
            echo "  (无进程可停)"
        fi
        ;;

    start)
        if [ ! -x "$VENV_PY" ]; then
            echo "  ✗ 找不到 venv: $VENV_PY" >&2
            echo "    请先建 venv: python3 -m venv .venv"
            exit 1
        fi
        PIDS=$(get_api_pids || true)
        if [ -n "$PIDS" ]; then
            echo "  fastInfo API 已在跑 (PID=$PIDS)"
            exit 0
        fi
        mkdir -p "$(dirname "$LOG_FILE")"
        echo "  启动 fastInfo API (后台,日志→$LOG_FILE)"
        nohup "$VENV_PY" "$PROJECT_ROOT/scripts/api_server.py" \
            > "$LOG_FILE" 2>&1 &
        sleep 2
        PIDS=$(get_api_pids || true)
        if [ -n "$PIDS" ]; then
            echo "  ✓ 启动成功 (PID=$PIDS)"
        else
            echo "  ✗ 启动失败,看日志: $LOG_FILE"
            tail -20 "$LOG_FILE"
            exit 1
        fi
        ;;

    restart)
        bash "$SCRIPT_DIR/restart_api.sh" stop
        bash "$SCRIPT_DIR/restart_api.sh" start
        ;;

    log)
        if [ -f "$LOG_FILE" ]; then
            tail -f -n 20 "$LOG_FILE"
        else
            echo "  (无日志)"
        fi
        ;;

    *)
        echo "用法: $0 {start|stop|restart|status|log}" >&2
        exit 1
        ;;
esac
