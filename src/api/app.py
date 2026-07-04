"""
fastInfo · FastAPI 实例
========================

启动:
    python scripts/api_server.py

打开浏览器:
    http://127.0.0.1:8000/docs            ← Swagger UI(本地默认,见 docs/ports-分配方案.md)
    http://127.0.0.1:8000/redoc           ← ReDoc

CORS:对 127.0.0.1:* 全部开(开发用),生产请收紧
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
import sys
import io

# Windows GBK 控制台兼容:强制 stdout/stderr 用 UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 让 src/ 可被 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import register_routes
from storage.mongo_writer import ensure_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时:确保索引 + 临时话题 TTL
    try:
        ensure_indexes()
        from storage.temp_topics import setup_indexes
        import asyncio
        asyncio.run(setup_indexes())
    except Exception as e:
        print(f"  ✗ startup hook failed: {e}")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="fastInfo API",
        version="0.2.0",
        description=(
            "fastInfo · 资讯中心 + AI 情报中枢 JSON API\n\n"
            "- `/api/search` MongoDB 全文检索\n"
            "- `/api/today` / `/api/hot` 内容浏览\n"
            "- `/api/subs` 自然语言订阅\n"
            "- `/api/auth/*` 注册/登录(JWT)\n"
            "- `/api/ingest/run` 手动触发抓取\n"
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # 开发用全开,生产收紧
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {
            "name": "fastInfo",
            "version": "0.2.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "api_base": "/api",
        }

    @app.get("/healthz")
    async def healthz():
        from storage.mongo_writer import get_sync_client
        try:
            info = get_sync_client().server_info()
            return {"status": "ok", "mongo_version": info.get("version")}
        except Exception as e:
            return {"status": "degraded", "mongo_error": str(e)}

    register_routes(app)
    return app


app = create_app()
