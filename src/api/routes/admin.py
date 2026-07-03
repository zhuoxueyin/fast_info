"""
fastInfo · 管理员路由
=====================
- 爬取任务时间线 / 明细
- 7 个 RSS 源 24h 状态
- LLM 模型组健康(熔断状态)
- 全部用户 / 全部订阅 / 全部推送(管理员视角)
"""
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.deps_admin import require_admin
from storage.mongo_writer import (
    get_db,
    get_recent_task_runs,
    get_task_run,
    get_source_status_24h,
    count_items,
    DEFAULT_DB,
)
from llm.model_registry import build_default_registry
from api.schemas import TaskRun, SourceStatus, LLMHealth

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tasks/runs", response_model=list[TaskRun])
def list_task_runs(
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """爬取任务时间线(最近 N 条)"""
    return get_recent_task_runs(limit=limit)


@router.get("/tasks/runs/{run_id}", response_model=TaskRun)
def get_task_run_detail(
    run_id: str,
    admin: dict = Depends(require_admin),
):
    """单次抓取明细"""
    doc = get_task_run(run_id)
    if not doc:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"run_id={run_id} 不存在")
    return doc


@router.get("/tasks/source-status", response_model=list[SourceStatus])
def source_status(admin: dict = Depends(require_admin)):
    """7 个 RSS 源 24h 抓取状态"""
    raw = get_source_status_24h()
    out = []
    for d in raw:
        failed = d.get("failed_24h", 0) or 0
        fetched = d.get("fetched_24h", 0) or 0
        healthy = (fetched > 0 and failed / max(fetched, 1) < 0.5) or fetched == 0
        out.append({
            "source": d.get("_id", "?"),
            "fetched_24h": fetched,
            "failed_24h": failed,
            "last_run_at": (d.get("last_run_at").isoformat() if d.get("last_run_at") else None),
            "last_latency_ms": d.get("last_latency_ms", 0) or 0,
            "healthy": healthy,
        })
    return out


@router.get("/llm/health", response_model=LLMHealth)
def llm_health(admin: dict = Depends(require_admin)):
    """LLM 模型组 × provider 状态(优先级 / 权重)"""
    from llm.model_registry import DEFAULT_GROUPS_SPEC
    groups: dict = {}
    for spec in DEFAULT_GROUPS_SPEC:
        gname = spec["name"]
        groups[gname] = {}
        for p in spec["providers"]:
            groups[gname][p["id"]] = {
                "priority": p["priority"],
                "weight": p.get("weight", 1),
                "model": p.get("model"),
                "max_tokens": p.get("max_tokens"),
                "protocol": p.get("protocol", "openai"),
            }
    return {"groups": groups}


@router.get("/users")
def list_all_users(admin: dict = Depends(require_admin)):
    """管理员:全部用户"""
    from datetime import datetime
    def _iso(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)
    db = get_db()
    out = []
    for u in db["users"].find({}, {"password_hash": 0}):
        out.append({
            "id": str(u.get("_id")),
            "username": u.get("username"),
            "email": u.get("email"),
            "role": u.get("role", "user"),
            "plan": u.get("plan", "free"),
            "created_at": _iso(u.get("created_at")),
            "last_login_at": _iso(u.get("last_login_at")),
        })
    return {"total": len(out), "items": out}


@router.get("/subscriptions")
def list_all_subscriptions(admin: dict = Depends(require_admin)):
    """管理员:全部订阅(每用户)"""
    db = get_db()
    out = []
    for s in db["subscriptions"].find().sort("created_at", -1 if hasattr(db["subscriptions"], "created_at") else 1).limit(500):
        out.append({
            "id": str(s.get("_id")),
            "user_id": s.get("user_id"),
            "title": s.get("title"),
            "nl_query": s.get("nl_query"),
            "keywords": s.get("keywords", []),
            "categories": s.get("categories", []),
            "cron_expr": s.get("cron_expr"),
            "is_active": s.get("is_active", True),
            "run_count": s.get("run_count", 0),
            "error_count": s.get("error_count", 0),
        })
    return {"total": len(out), "items": out}


@router.get("/stats")
def admin_stats(admin: dict = Depends(require_admin)):
    """管理员:汇总统计(总 items / 总用户 / 总订阅 / 总推送 + 类目 / 源分布)"""
    db = get_db()
    return {
        "total_items": db["items"].count_documents({}),
        "total_users": db["users"].count_documents({}),
        "total_subscriptions": db["subscriptions"].count_documents({}),
        "total_delivered": db["subscriptions_delivered"].count_documents({}),
        "by_source": list(db["items"].aggregate([
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
        "by_category": list(db["items"].aggregate([
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
        "by_user": list(db["subscriptions"].aggregate([
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
    }


@router.post("/ingest/run")
def admin_ingest_run(
    limit: int = Query(8, ge=1, le=30),
    admin: dict = Depends(require_admin),
):
    """管理员:手动触发一次抓取(同步等结果)"""
    import asyncio
    from scripts.ingest_daemon import run_once

    class _Args:
        pass
    args = _Args()
    args.limit = limit
    n = asyncio.run(run_once(args))
    return {
        "run_id": "manual_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "items_fetched": n,
        "items_summarized": n,
        "items_failed": 0,
        "summarized": n,
        "fetched": n,
        "failed": 0,
    }


# ============================================================
# Day 4:源开关 + 调度频率配置
# ============================================================
class SourceConfigUpdate(BaseModel):
    """管理员:更新源开关"""
    enabled: List[str]   # 启用的 source id 列表


@router.get("/sources")
def admin_list_sources(admin: dict = Depends(require_admin)):
    """列出所有可用源(包含 RSS + KOL)及其当前开关状态"""
    from crawler.sources import RSS_SOURCES, KOL_SOURCES, DEFAULT_CRON, SOURCE_L1_MAP
    from crawler.collectors import load_enabled_sources
    enabled_set = load_enabled_sources()  # None 表示全开

    rss = []
    for sid, (name, url) in RSS_SOURCES.items():
        rss.append({
            "id": sid, "name": name, "kind": "rss",
            "url": url, "default_interval_sec": DEFAULT_CRON["rss"],
            "category_l1": SOURCE_L1_MAP.get(sid, "其他"),
            "enabled": (sid in enabled_set) if enabled_set is not None else True,
        })
    kol = []
    for key, (name, kind) in KOL_SOURCES.items():
        kol.append({
            "id": key, "name": name, "kind": kind,
            "url": "", "default_interval_sec": DEFAULT_CRON["kol"],
            "category_l1": SOURCE_L1_MAP.get(key, "其他"),
            "enabled": (key in enabled_set) if enabled_set is not None else True,
        })
    return {"rss": rss, "kol": kol, "all_enabled": enabled_set is None}


@router.put("/sources")
def admin_update_sources(req: SourceConfigUpdate, admin: dict = Depends(require_admin)):
    """更新源开关(白名单:不在列表里的源会被关停)"""
    from crawler.collectors import save_enabled_sources
    save_enabled_sources(req.enabled)
    return {"ok": True, "enabled_count": len(req.enabled)}


# ============================================================
# Day 4:二级分类体系
# ============================================================
@router.get("/taxonomy")
def admin_get_taxonomy(admin: dict = Depends(require_admin)):
    """返回 L1 / L2 分类树(给前端订阅页用)"""
    from crawler.sources import CATEGORY_L1, CATEGORY_L2
    return {"l1": CATEGORY_L1, "l2": CATEGORY_L2}