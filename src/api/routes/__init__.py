"""
fastInfo · API 路由集合
======================
把 CLI 命令一对一映射到 HTTP endpoint。

注意:不构造带 `prefix="/api"` 的父 router 再 include
(那样会产生两层 include,内部 endpoint 解不出来,见 P0-1)。
改为:`app.include_router(child_router, prefix="/api")` 一次性把
前缀加到每个子 router 上,避免嵌套 _IncludedRouter。
"""
from fastapi import FastAPI

# 触发子模块 import(让 @router.get 装饰器跑完,挂上 endpoint)
from . import (
    auth, hot, ingest, items, search, stats, subs, today,
    banner, inbox, categories, admin,  # Day 3 新增
    topics, settings,  # topics: 临时话题 / settings: 推送配置
)  # noqa: F401


def register_routes(app: FastAPI) -> None:
    """把全部子路由挂到 FastAPI app 上(前缀 /api)。"""
    app.include_router(search.router, prefix="/api")
    app.include_router(today.router, prefix="/api")
    app.include_router(hot.router, prefix="/api")
    app.include_router(items.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")
    app.include_router(subs.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    # Day 3 新增
    app.include_router(banner.router, prefix="/api")
    app.include_router(inbox.router, prefix="/api")
    app.include_router(categories.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    # Day 5: source_admin (router prefix="/admin/sources")
    from .source_admin import router as source_admin_router  # noqa: F811
    app.include_router(source_admin_router, prefix="/api")
    # topics / settings
    app.include_router(topics.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
