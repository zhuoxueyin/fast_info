"""Day 5 · 源管理 admin API (Day 6 v0.3.0 加鉴权 require_admin)

所有 router 都已加 Depends(require_admin)。
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body, Depends

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api.deps_admin import require_admin
from storage.source_config import (
    list_sources, get_source, upsert_source, delete_source, toggle_source,
    set_source_active,
)
from storage.source_runs import (
    get_source_health, get_overall_health, get_recent_runs,
)


router = APIRouter(prefix="/admin/sources", tags=["admin:sources"])


@router.get("")
async def list_all(
    l1: Optional[str] = Query(None),
    active_only: bool = Query(False),
    user: dict = Depends(require_admin),
):
    """GET /api/admin/sources - 列出所有源"""
    return {
        "items": list_sources(l1=l1, active_only=active_only),
        "total": len(list_sources(l1=l1, active_only=active_only)),
    }


@router.get("/health/summary")
async def health_summary(
    window_days: int = Query(1, ge=1, le=30),
    user: dict = Depends(require_admin),
):
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
async def show_one(
    source_id: str,
    user: dict = Depends(require_admin),
):
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    return s


@router.post("")
async def create_source(
    body: dict = Body(...),
    user: dict = Depends(require_admin),
):
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
async def update_one(
    source_id: str,
    body: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """PATCH /api/admin/sources/{id} - 改任意字段"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    body["source_id"] = source_id
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    upsert_source(body)
    return {"ok": True}


@router.delete("/{source_id}")
async def remove_one(
    source_id: str,
    hard: bool = Query(False),
    user: dict = Depends(require_admin),
):
    """DELETE /api/admin/sources/{id} - 软删(is_active=false),hard=true 真删"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    ok = delete_source(source_id, hard=hard)
    return {"ok": ok}


@router.post("/{source_id}/toggle")
async def toggle_active(
    source_id: str,
    user: dict = Depends(require_admin),
):
    """启停切换"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    state = toggle_source(source_id)
    return {"ok": True, "is_active": state}


@router.post("/batch-toggle")
async def batch_toggle_active(
    body: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """批量启停 — body: {source_ids: [...], is_active: bool}

    返回 {ok, updated, skipped}
    - updated: 成功更新的条数
    - skipped: 不存在的 source_id 列表(便于前端展示)
    """
    source_ids = body.get("source_ids")
    is_active = body.get("is_active")
    if not isinstance(source_ids, list) or not source_ids:
        raise HTTPException(status_code=400, detail="source_ids 必须是非空数组")
    if not isinstance(is_active, bool):
        raise HTTPException(status_code=400, detail="is_active 必须是 bool")
    if len(source_ids) > 500:
        raise HTTPException(status_code=400, detail="单次最多 500 条")

    updated = 0
    skipped: list[str] = []
    for sid in source_ids:
        if not isinstance(sid, str) or not sid:
            skipped.append(str(sid))
            continue
        if set_source_active(sid, is_active):
            updated += 1
        else:
            skipped.append(sid)
    return {"ok": True, "updated": updated, "skipped": skipped, "is_active": is_active}


@router.post("/{source_id}/test")
async def test_one(
    source_id: str,
    limit: int = Query(5, ge=1, le=30),
    user: dict = Depends(require_admin),
):
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
async def metrics_one(
    source_id: str,
    window_days: int = Query(7, ge=1, le=30),
    user: dict = Depends(require_admin),
):
    """单源健康度时间窗(1d / 7d / 30d)"""
    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    return get_source_health(source_id, window_days=window_days)


@router.get("/{source_id}/runs")
async def runs_one(
    source_id: str,
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    """单源 source_runs 历史"""
    return {
        "source_id": source_id,
        "items": get_recent_runs(source_id=source_id, limit=limit),
    }


# ============================================================
# Day 10.5 · 调度策略接口(全局 + 单源 + 批量)
# ============================================================

@router.get("/schedule/overview")
async def schedule_overview(
    user: dict = Depends(require_admin),
):
    """GET /api/admin/sources/schedule/overview
    返回所有源的调度状态(下次运行时间、间隔、活跃状态)。
    给任务管理页 / SourcesPage 用,前端不直接读 source_config,要加计算字段。
    """
    from storage.ingest_schedule import compute_due_sources
    schedule = compute_due_sources()
    active = sum(1 for r in schedule if r["is_active"] and r["interval_seconds"] > 0)
    manual = sum(1 for r in schedule if r["interval_seconds"] <= 0)
    due_now = sum(1 for r in schedule if r["is_active"] and r["interval_seconds"] > 0 and r["due_in_seconds"] <= 0)
    return {
        "items": schedule,
        "total_sources": len(schedule),
        "active_scheduled": active,
        "manual_only": manual,
        "due_now": due_now,
    }


@router.post("/{source_id}/schedule")
async def update_schedule(
    source_id: str,
    body: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """POST /api/admin/sources/{id}/schedule
    body: {cron_interval_seconds: int} 或 {interval_seconds: int}
    - 0 = 仅手动(永不自动)
    - 任意正数 = 多少秒抓一次
    """
    from storage.source_config import get_source, upsert_source

    interval = body.get("cron_interval_seconds")
    if interval is None:
        interval = body.get("interval_seconds")
    if interval is None:
        raise HTTPException(status_code=400, detail="cron_interval_seconds required")
    try:
        interval = int(interval)
    except Exception:
        raise HTTPException(status_code=400, detail="cron_interval_seconds must be int")
    if interval < 0:
        raise HTTPException(status_code=400, detail="cron_interval_seconds must be >= 0")

    s = get_source(source_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"{source_id} not found")
    s["cron_interval_seconds"] = interval
    s["updated_at"] = datetime.now(timezone.utc).isoformat()
    upsert_source(s)
    return {
        "ok": True,
        "source_id": source_id,
        "cron_interval_seconds": interval,
        "label": (
            "手动" if interval == 0 else
            f"{interval} 秒" if interval < 60 else
            f"{interval // 60} 分钟" if interval < 3600 else
            f"{interval // 3600} 小时" if interval < 86400 else
            f"{interval // 86400} 天"
        ),
    }


@router.post("/schedule/batch")
async def batch_update_schedule(
    body: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """POST /api/admin/sources/schedule/batch
    批量改调度 — body:
        source_ids: list[str]
        cron_interval_seconds: int    (应用到所有)
    或:
        items: list[{source_id, cron_interval_seconds}]   (每个单独)
    """
    from storage.source_config import get_source, upsert_source

    items = body.get("items")
    if items:
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=400, detail="items 必须是非空数组")
        updated = 0
        skipped: list[str] = []
        for it in items:
            sid = it.get("source_id")
            iv = it.get("cron_interval_seconds")
            if not sid or iv is None:
                skipped.append(str(sid or "?"))
                continue
            try:
                iv = int(iv)
            except Exception:
                skipped.append(str(sid))
                continue
            if iv < 0:
                skipped.append(str(sid))
                continue
            s = get_source(sid)
            if not s:
                skipped.append(str(sid))
                continue
            s["cron_interval_seconds"] = iv
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            upsert_source(s)
            updated += 1
        return {"ok": True, "updated": updated, "skipped": skipped}

    source_ids = body.get("source_ids")
    interval = body.get("cron_interval_seconds")
    if not isinstance(source_ids, list) or not source_ids:
        raise HTTPException(status_code=400, detail="source_ids/items 必须是非空数组")
    if interval is None:
        raise HTTPException(status_code=400, detail="cron_interval_seconds required")
    try:
        interval = int(interval)
    except Exception:
        raise HTTPException(status_code=400, detail="cron_interval_seconds must be int")
    if interval < 0:
        raise HTTPException(status_code=400, detail="cron_interval_seconds must be >= 0")

    updated = 0
    skipped: list[str] = []
    for sid in source_ids:
        s = get_source(sid)
        if not s:
            skipped.append(str(sid))
            continue
        s["cron_interval_seconds"] = interval
        s["updated_at"] = datetime.now(timezone.utc).isoformat()
        upsert_source(s)
        updated += 1
    return {"ok": True, "updated": updated, "skipped": skipped, "cron_interval_seconds": interval}


@router.post("/{source_id}/run-now")
async def run_source_now(
    source_id: str,
    limit: int = Query(8, ge=1, le=50),
    user: dict = Depends(require_admin),
):
    """POST /api/admin/sources/{id}/run-now?limit=8
    立刻抓一个源(走 daemon 同样的 fetch_one_source + LLM 摘要 + 入库),
    同步返回结果。给"立即抓一次"按钮用。
    """
    from scripts.ingest_daemon import run_due_sources
    r = await run_due_sources([source_id], _RunOnceArgs(limit=limit, run_id=None, trigger="manual_admin"))
    return r


class _RunOnceArgs:
    """最小 args 子集,够 run_due_sources 用。"""
    def __init__(self, limit: int, run_id: str | None, trigger: str):
        self.limit = limit
        self.run_id = run_id
        self.trigger = trigger
        self.operator = None


# ============================================================
# Day 5 · system_alerts 接口(也加鉴权)
# ============================================================

@router.get("/alerts/list")
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None),
    unack_only: bool = Query(False),
    user: dict = Depends(require_admin),
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
async def ack_alert(
    alert_id: str,
    user: dict = Depends(require_admin),
):
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
