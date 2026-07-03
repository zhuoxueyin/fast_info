"""fastInfo · source_runs collection — 每源每次抓取一条记录 (Day 5)

启用:
    from storage.source_runs import record_source_run, get_source_health, get_overall_health, get_recent_runs
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

from storage.mongo_writer import get_db


ErrorCode = Literal[
    "TIMEOUT", "PARSE_ERROR", "HTTP_5XX", "HTTP_404",
    "CONNECTION_REFUSED", "DNS_FAIL", "DISABLED", "EMPTY_FEED",
    "LLM_FAIL", "MONGO_FAIL", "OTHER", None,
]

Status = Literal["ok", "partial", "fail", "disabled"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_error(exc: Exception) -> ErrorCode:
    """根据异常类型推断错误码"""
    name = type(exc).__name__
    msg = str(exc).lower()
    if "timeout" in name.lower() or "timeout" in msg:
        return "TIMEOUT"
    if "dns" in name.lower() or "resolve" in msg or "name or service" in msg:
        return "DNS_FAIL"
    if "connect" in name.lower() or "refused" in msg or "111" in msg:
        return "CONNECTION_REFUSED"
    return "OTHER"


# ============================================================
# 写
# ============================================================

def record_source_run(
    source_id: str,
    status: Status,
    started_at: str,
    duration_ms: int,
    *,
    fetched_count: int = 0,
    new_count: int = 0,
    deduped_count: int = 0,
    summarized_count: int = 0,
    failed_count: int = 0,
    error_code: Optional[ErrorCode] = None,
    error_msg: Optional[str] = None,
    extra: Optional[dict] = None,
) -> str:
    """记录一条 source_run,返回 run_id"""
    db = get_db()
    run_id = str(uuid.uuid4())
    doc = {
        "run_id": run_id,
        "source_id": source_id,
        "started_at": started_at,
        "ended_at": now_iso(),
        "duration_ms": int(duration_ms),
        "status": status,
        "fetched_count": int(fetched_count),
        "new_count": int(new_count),
        "deduped_count": int(deduped_count),
        "summarized_count": int(summarized_count),
        "failed_count": int(failed_count),
        "error_code": error_code,
        "error_msg": (error_msg or "")[:500],
        "created_at": now_iso(),
    }
    if extra:
        doc["extra"] = extra
    db["source_runs"].insert_one(doc)

    # 联动更新 source_config 健康状态 + 自动禁用
    sc = db["source_config"].find_one({"source_id": source_id})
    if sc is not None:
        threshold = sc.get("auto_disable_threshold", 5)
        if status in ("ok", "partial"):
            db["source_config"].update_one(
                {"source_id": source_id},
                {"$set": {
                    "last_success_at": now_iso(),
                    "consecutive_fails": 0,
                    "updated_at": now_iso(),
                }},
            )
        elif status == "fail":
            fails = int(sc.get("consecutive_fails", 0)) + 1
            update = {
                "last_fail_at": now_iso(),
                "consecutive_fails": fails,
                "updated_at": now_iso(),
            }
            if fails >= threshold and sc.get("is_active") is not False:
                update["is_active"] = False
                update["disabled_reason"] = f"consecutive_fails={fails} >= {threshold}"
                update["disabled_at"] = now_iso()
            db["source_config"].update_one(
                {"source_id": source_id},
                {"$set": update},
            )
    return run_id


# ============================================================
# 读
# ============================================================

def get_source_health(source_id: str, window_days: int = 1) -> dict:
    """单源 24h/7d 健康度"""
    db = get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    cur = db["source_runs"].find({
        "source_id": source_id,
        "created_at": {"$gte": since},
    }).sort("created_at", -1)
    runs = list(cur)
    total = len(runs)
    ok = sum(1 for r in runs if r.get("status") in ("ok", "partial"))
    fail = sum(1 for r in runs if r.get("status") == "fail")
    return {
        "source_id": source_id,
        "window_days": window_days,
        "total_runs": total,
        "ok_runs": ok,
        "fail_runs": fail,
        "success_rate": (ok / total) if total > 0 else None,
        "total_fetched": sum(int(r.get("fetched_count", 0)) for r in runs),
        "total_new": sum(int(r.get("new_count", 0)) for r in runs),
        "total_summarized": sum(int(r.get("summarized_count", 0)) for r in runs),
        "total_deduped": sum(int(r.get("deduped_count", 0)) for r in runs),
        "avg_duration_ms": (
            int(sum(r.get("duration_ms", 0) for r in runs) / total) if total > 0 else None
        ),
        "last_run_at": runs[0]["ended_at"] if runs else None,
        "last_status": runs[0]["status"] if runs else None,
        "last_error_code": runs[0].get("error_code") if runs else None,
    }


def get_overall_health(window_days: int = 1) -> list[dict]:
    """全平台健康度列表 + 当前 source_config 状态"""
    db = get_db()
    sources = list(db["source_config"].find({}))
    out = []
    for s in sources:
        h = get_source_health(s["source_id"], window_days)
        out.append({
            "source_id": s["source_id"],
            "display_name": s.get("display_name"),
            "kind": s.get("kind"),
            "l1": s.get("l1"),
            "is_active": s.get("is_active", True),
            "last_success_at": s.get("last_success_at"),
            "last_fail_at": s.get("last_fail_at"),
            "consecutive_fails": int(s.get("consecutive_fails", 0)),
            "auto_disable_threshold": int(s.get("auto_disable_threshold", 5)),
            "disabled_reason": s.get("disabled_reason"),
            **h,
        })
    return out


def get_recent_runs(source_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    db = get_db()
    q = {} if source_id is None else {"source_id": source_id}
    cur = db["source_runs"].find(q).sort("created_at", -1).limit(limit)
    out = []
    for r in cur:
        r["_id"] = str(r["_id"])
        out.append(r)
    return out


def ensure_indexes():
    db = get_db()
    db["source_runs"].create_index([("source_id", 1), ("created_at", -1)])
    db["source_runs"].create_index([("status", 1), ("created_at", -1)])
    db["source_config"].create_index("source_id", unique=True)
