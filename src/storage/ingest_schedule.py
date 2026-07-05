"""Day 10.5 · 按源调度工具函数

daemon 用它来算哪些源到期该跑 — 取代原 daemon 写死的全局 interval。

数据流:
    source_config.cron_interval_seconds  →  每源自己节奏
    source_runs.started_at               →  上次跑的时间
    两者对比 → due set
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from storage.source_config import list_sources
from storage.source_runs import get_recent_runs
from storage.mongo_writer import get_db


# 各 kind 的默认 interval(秒) — fallback 给 cron_interval_seconds 缺失的源
DEFAULT_INTERVAL_BY_KIND = {
    "rss": 1800,        # 30 min
    "kol": 3600,        # 60 min
    "weibo_user": 3600,
    "weibo_hot": 600,   # 热搜快一些
    "x_user": 3600,
    "xhs_note": 3600,
    "rss_hot": 600,     # 热搜类快一些
}


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def get_effective_interval(source: dict) -> int:
    """取一个源的有效 interval(秒)。
    - cron_interval_seconds <= 0 → 0(永不自动跑,只手动)
    - 缺字段 → 按 kind fallback
    """
    interval = source.get("cron_interval_seconds")
    if interval is None:
        kind = source.get("kind", "rss")
        return DEFAULT_INTERVAL_BY_KIND.get(kind, 1800)
    try:
        return int(interval)
    except Exception:
        return DEFAULT_INTERVAL_BY_KIND.get(source.get("kind", "rss"), 1800)


def get_last_run_at(source_id: str) -> Optional[datetime]:
    """从 source_runs 取该源最近一次启动时间(任意 status)。
    返回 tz-aware UTC datetime。
    """
    try:
        db = get_db()
        d = db["source_runs"].find_one(
            {"source_id": source_id},
            sort=[("started_at", -1)],
            projection={"started_at": 1, "_id": 0},
        )
        return _parse_dt(d.get("started_at")) if d else None
    except Exception:
        return None


def get_last_run_map() -> dict[str, datetime]:
    """批量取所有源的最近一次跑时间 — 一次 aggregate 搞定。
    用于 daemon 启动时初始化 next_run_at 表。
    """
    try:
        db = get_db()
        pipe = [
            {"$sort": {"started_at": -1}},
            {"$group": {"_id": "$source_id", "started_at": {"$first": "$started_at"}}},
        ]
        out = {}
        for d in db["source_runs"].aggregate(pipe):
            sid = d.get("_id")
            dt = _parse_dt(d.get("started_at"))
            if sid and dt:
                out[sid] = dt
        return out
    except Exception:
        return {}


def compute_due_sources(now: Optional[datetime] = None) -> list[dict]:
    """算哪些源到期该跑。

    返回 list of dict:
        [{
            "source_id": str,
            "interval_seconds": int,
            "last_run_at": iso str or None,
            "next_run_at": iso str,
            "due_in_seconds": int,       # 负数=已逾期
        }, ...]

    - is_active=False → 跳过
    - cron_interval_seconds <= 0 → 跳过(永不自动跑)
    - 其它 → 算 due_in_seconds
    """
    if now is None:
        now = datetime.now(timezone.utc)

    sources = list_sources()  # 全部
    last_map = get_last_run_map()
    out: list[dict] = []

    for s in sources:
        sid = s["source_id"]
        is_active = bool(s.get("is_active", True))
        interval = get_effective_interval(s)
        last_dt = last_map.get(sid)
        next_dt = (last_dt + timedelta(seconds=interval)) if last_dt else now
        due_in = (next_dt - now).total_seconds()

        out.append({
            "source_id": sid,
            "display_name": s.get("display_name", sid),
            "kind": s.get("kind", "?"),
            "l1": s.get("l1", ""),
            "is_active": is_active,
            "interval_seconds": interval,
            "interval_label": _humanize_interval(interval),
            "last_run_at": last_dt.isoformat() if last_dt else None,
            "next_run_at": next_dt.isoformat() if is_active else None,
            "due_in_seconds": int(due_in),
            "status": s.get("status", "active"),
        })

    return out


def _humanize_interval(sec: int) -> str:
    if sec <= 0:
        return "手动"
    if sec < 60:
        return f"{sec} 秒"
    if sec < 3600:
        return f"{sec // 60} 分钟"
    if sec < 86400:
        return f"{sec // 3600} 小时"
    return f"{sec // 86400} 天"


def pick_due_sources(schedule_rows: list[dict], now: Optional[datetime] = None) -> list[str]:
    """从 schedule_rows 里筛出 due 的 source_id 列表。"""
    if now is None:
        now = datetime.now(timezone.utc)
    due = []
    for r in schedule_rows:
        if not r.get("is_active"):
            continue
        if r.get("interval_seconds", 0) <= 0:
            continue
        next_dt = _parse_dt(r.get("next_run_at"))
        if next_dt is None:
            continue
        if next_dt <= now:
            due.append(r["source_id"])
    return due