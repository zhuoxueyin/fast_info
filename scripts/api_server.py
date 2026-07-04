"""
fastInfo · FastAPI 启动脚本
============================

跑法:
    python scripts/api_server.py                          # 默认 127.0.0.1:8000(本地开发)
    python scripts/api_server.py --port 18000             # 改端口
    python scripts/api_server.py --host 0.0.0.0           # 监听所有网卡(部署时)
    FASTINFO_API_PORT=18000 python scripts/api_server.py  # 用 env 控制

启动后(本地默认):
    Swagger UI:   http://127.0.0.1:8000/docs
    ReDoc:        http://127.0.0.1:8000/redoc
    Healthcheck:  http://127.0.0.1:8000/healthz

⚠️ 本地 / Docker 端口标准化方案见 docs/ports-分配方案.md
"""
import argparse
import os
import sys
import io
from pathlib import Path

# Windows GBK 控制台兼容:强制 stdout/stderr 用 UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 把 src/ 和项目根 放进 path(项目根让 scripts.* 命名空间包可被 import)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT))

# 加载 .env(本地开发 + Docker volume 挂 /app/.env 都覆盖)
from _env import load_env
load_env()

import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    # 优先用 --port CLI 参数;其次 env(FASTINFO_API_PORT);最后本地默认 8000
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("FASTINFO_API_PORT", "8000")),
    )
    parser.add_argument("--reload", action="store_true", help="开发模式 hot-reload")
    parser.add_argument("--keep-proxy", action="store_true", help="保留 HTTP_PROXY/HTTPS_PROXY(默认会清掉,避免 Clash 之类代理把 127.0.0.1 流量劫走返 502)")
    args = parser.parse_args()

    # 清代理:本机调试常被 Clash / v2rayN 之类的系统代理劫走,
    # 客户端请求 127.0.0.1:8000 时被代理解析失败,返 502 空响应。
    if not args.keep_proxy:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            os.environ.pop(k, None)

    print(f"  fastInfo API · http://{args.host}:{args.port}")
    print(f"  Swagger UI    http://{args.host}:{args.port}/docs")
    print(f"  ReDoc         http://{args.host}:{args.port}/redoc")
    print(f"  Healthz       http://{args.host}:{args.port}/healthz")
    if not args.keep_proxy:
        print(f"  Proxy         清空 (HTTP_PROXY/HTTPS_PROXY/ALL_PROXY)")
    print()

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
