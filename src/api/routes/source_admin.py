"""Day 5 · 源管理 admin API

公开路由(Base /api/admin/sources/),鉴权由前端页面层控制。
生产环境应加上 Bearer + role=="admin" 验证。
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from storage.source_config import (
    list_sources, get_source, upsert_source, delete_source, toggle_source,
)
from storage.source_runs import (
    get_source_health, get_overall_health, get_recent_runs,
)


router = APIRouter(prefix="/api/admin/sources", tags=["admin:sources"])


@router.get("")
async def list_all(
    l1: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    """GET /api/admin/sources - 列出所有源"""
    return {
        "items": list_sources(l1=l1, active_only=active_only),
        "total": len(list_sources(l1=l1, active_only=active_only)),
    }


@router.get("/health/summary")
async def health_summary(window_days: int = Query(1, ge=1, le=30)):
    """全平台健康度 + 启停状态"""
    rows = get_overall_health(window_days=window_days)
    return {
        "window_days": window_days,
        "items": rows,
        "total_sources": len(rows),
        "active_sources": sum(1 for r in rows if r.get("is_active")),
        "disabled_sources": sum(1 for r in rows if not r.get("is_active")),
    }


@router.get("/{source_id}")
async def show_one(source_id: str):
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    return s


@router.post("")
async def create_source(body: dict = Body(...)):
    """POST /api/admin/sources - 新建"""
    sid = body.get("source_id")
    if not sid:
        raise HTTPException(status_code=400, detail="source_id required")
    if get_source(sid):
        raise HTTPException(status_code=409, detail=f"{sid} already exists")
    body.setdefault("is_active", True)
    body.setdefault("auto_disable_threshold", 5)
    body.setdefault("cron_interval_seconds", 1800)
    body.setdefault("limit_per_run", 15)
    upsert_source(body)
    return {"ok": True, "source_id": sid}


@router.patch("/{source_id}")
async def update_one(source_id: str, body: dict = Body(...)):
    """PATCH /api/admin/sources/{id} - 改任意字段"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    body["source_id"] = source_id
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    upsert_source(body)
    return {"ok": True}


@router.delete("/{source_id}")
async def remove_one(source_id: str, hard: bool = Query(False)):
    """DELETE /api/admin/sources/{id} - 软删(is_active=false),hard=true 真删"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    ok = delete_source(source_id, hard=hard)
    return {"ok": ok}


@router.post("/{source_id}/toggle")
async def toggle_active(source_id: str):
    """启停切换"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    state = toggle_source(source_id)
    return {"ok": True, "is_active": state}


@router.post("/{source_id}/test")
async def test_one(source_id: str, limit: int = Query(5, ge=1, le=30)):
    """手动试抓一次(不入库),返回采样"""
    from crawler.collectors import (
        fetch_rss_with_fallback, fetch_x_user_multi, fetch_weibo_user,
        fetch_xhs_note,
    )
    from crawler.sources import RSS_SOURCES, KOL_SOURCES
    from crawler.mirrors import get_huxiu_urls
    import httpx
    from crawler.rss_collector import USER_AGENT
    
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    
    started = time.monotonic()
    items = []
    error: Optional[str] = None
    status = "ok"
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, */*"},
    ) as client:
        try:
            kind = s.get("kind")
            display = s.get("display_name", "?")
            if kind == "rss":
                urls = s.get("urls") or ([s["url"]] if s.get("url") else [])
                if not urls:
                    raise ValueError("no url configured")
                items = await fetch_rss_with_fallback(client, source_id, display, urls, limit)
            elif kind == "weibo_user":
                _, uid = source_id.split(":", 1)
                items = await fetch_weibo_user(client, uid, display, limit,
                                              s.get("platform_config"))
            elif kind == "x_user":
                _, handle = source_id.split(":", 1)
                items = await fetch_x_user_multi(client, handle, display, limit)
            elif kind == "xhs_note":
                _, uid = source_id.split(":", 1)
                items = await fetch_xhs_note(client, uid, display, limit,
                                             s.get("platform_config"))
            else:
                raise ValueError(f"unsupported kind: {kind}")
            
            if not items:
                status = "partial"
                error = "empty"
        except Exception as e:
            status = "fail"
            error = f"{type(e).__name__}: {str(e)[:200]}"
    
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "ok": status in ("ok", "partial"),
        "status": status,
        "duration_ms": duration_ms,
        "fetched_count": len(items),
        "items": [
            {
                "title": it.title[:80],
                "url": it.url,
                "source": it.source,
                "published_at": it.published_at,
            }
            for it in items[:limit]
        ],
        "error": error,
    }


@router.get("/{source_id}/metrics")
async def metrics_one(source_id: str, window_days: int = Query(7, ge=1, le=30)):
    """单源健康度时间窗(1d / 7d / 30d)"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    return get_source_health(source_id, window_days=window_days)


@router.get("/{source_id}/runs")
async def runs_one(source_id: str, limit: int = Query(50, ge=1, le=200)):
    """单源 source_runs 历史"""
    return {
        "source_id": source_id,
        "items": get_recent_runs(source_id=source_id, limit=limit),
    }


# ============================================================
# Day 5 · system_alerts 接口
# ============================================================

@router.get("/alerts/list")
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None),
    unack_only: bool = Query(False),
):
    """列出 system_alerts,默认 50 条最新"""
    db_d = __import__("storage.mongo_writer", fromlist=["get_db"]).get_db()
    q = {}
    if severity:
        q["severity"] = severity
    if unack_only:
        q["ack"] = False
    cur = db_d["system_alerts"].find(q).sort("created_at", -1).limit(limit)
    out = []
    for r in cur:
        r["_id"] = str(r["_id"])
        out.append(r)
    return {"items": out, "total": len(out)}


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(alert_id: str):
    """标记告警已确认"""
    from bson import ObjectId
    db_d = __import__("storage.mongo_writer", fromlist=["get_db"]).get_db()
    try:
        r = db_d["system_alerts"].update_one(
            {"_id": ObjectId(alert_id)},
            {"$set": {"ack": True, "acked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="bad alert_id")
    if r.modified_count == 0:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}
