"""fastInfo · 推送历史(Day 9)

目的:
- 用户能区分"这条消息是从哪来的"(订阅 / 手动 / 测试 / 调度)
- 知道推送走了哪些渠道 + 各渠道结果(成功/失败/状态码)
- 知道推送了哪些内容(items 快照)

数据模型:
    push_history docs:
    {
      _id, user_id,
      subscription_id | None,
      subscription_title,
      trigger: "manual" | "schedule" | "test" | "cli" | "unknown",
      channels_ok:  ["feishu", "inbox"],
      channels_fail: ["email"],
      channel_results: {
        "feishu": {"ok": true, "http_status": 200, "error": None},
        "inbox":  {"ok": true, "http_status": None, "error": None},
        "email":  {"ok": false, "http_status": None, "error": "no recipient email"},
      },
      items: [{item_id, title, url, source}, ...],
      item_count: N,
      sent_at: ISO string,            (UTC)
      duration_ms: N,                 (推送本身耗时)
      operator: "auto" | "<username>",  (手动触发时记谁点的)
      error: None | str,               (整个 sub run 出错时)
    }

索引:
    (user_id, sent_at DESC) — 主查询
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from storage.mongo_writer import get_async_client, get_sync_client, DEFAULT_DB


def _now_iso() -> str:
    """统一 UTC ISO 字符串,跟现有 *_at 字段格式一致。"""
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 写
# ============================================================

async def record_push(
    *,
    user_id: str,
    subscription_id: Optional[str] = None,
    subscription_title: str = "",
    trigger: str = "unknown",
    channel_results: dict[str, dict] | None = None,
    items: list[dict] | None = None,
    duration_ms: int = 0,
    operator: str = "auto",
    error: Optional[str] = None,
) -> str:
    """落一条 push_history,返回 _id。"""
    channel_results = channel_results or {}
    items = items or []
    channels_ok = [ch for ch, r in channel_results.items() if r.get("ok")]
    channels_fail = [ch for ch, r in channel_results.items() if not r.get("ok")]

    doc = {
        "user_id":             user_id,
        "subscription_id":     subscription_id,
        "subscription_title":  subscription_title,
        "trigger":             trigger,
        "operator":            operator,
        "channels_ok":         channels_ok,
        "channels_fail":       channels_fail,
        "channel_results":     channel_results,
        "items":               items,
        "item_count":          len(items),
        "sent_at":             _now_iso(),
        "duration_ms":         duration_ms,
        "error":               error,
    }
    db = get_async_client()[DEFAULT_DB]
    res = await db["push_history"].insert_one(doc)
    return str(res.inserted_id)


def record_push_sync(**kwargs) -> str:
    """同步版,给 CLI 用。"""
    channel_results = kwargs.get("channel_results") or {}
    items = kwargs.get("items") or []
    channels_ok = [ch for ch, r in channel_results.items() if r.get("ok")]
    channels_fail = [ch for ch, r in channel_results.items() if not r.get("ok")]

    doc = {
        "user_id":             kwargs.get("user_id"),
        "subscription_id":     kwargs.get("subscription_id"),
        "subscription_title":  kwargs.get("subscription_title", ""),
        "trigger":             kwargs.get("trigger", "unknown"),
        "operator":            kwargs.get("operator", "auto"),
        "channels_ok":         channels_ok,
        "channels_fail":       channels_fail,
        "channel_results":     channel_results,
        "items":               items,
        "item_count":          len(items),
        "sent_at":             _now_iso(),
        "duration_ms":         kwargs.get("duration_ms", 0),
        "error":               kwargs.get("error"),
    }
    res = get_sync_client()[DEFAULT_DB]["push_history"].insert_one(doc)
    return str(res.inserted_id)


# ============================================================
# 读
# ============================================================

async def list_for_user(
    user_id: str,
    *,
    limit: int = 50,
    trigger: Optional[str] = None,
) -> list[dict]:
    """拉一个用户的推送历史,按时间倒序。trigger 非空时过滤。"""
    db = get_async_client()[DEFAULT_DB]
    q: dict = {"user_id": user_id}
    if trigger:
        q["trigger"] = trigger
    cur = db["push_history"].find(q).sort("sent_at", -1).limit(limit)
    return [doc async for doc in cur]


def list_for_user_sync(
    user_id: str,
    *,
    limit: int = 50,
    trigger: Optional[str] = None,
) -> list[dict]:
    db = get_sync_client()[DEFAULT_DB]
    q: dict = {"user_id": user_id}
    if trigger:
        q["trigger"] = trigger
    return list(db["push_history"].find(q).sort("sent_at", -1).limit(limit))


async def get_by_id(history_id: str, user_id: str) -> Optional[dict]:
    """拉一条详情,带 user 鉴权(只能看自己的)。"""
    from bson import ObjectId
    from bson.errors import InvalidId
    db = get_async_client()[DEFAULT_DB]
    try:
        oid = ObjectId(history_id)
    except (InvalidId, TypeError):
        return None
    return await db["push_history"].find_one({"_id": oid, "user_id": user_id})


# ============================================================
# 统计(给 MonitoringPage 备用)
# ============================================================

async def stats_for_user(user_id: str) -> dict:
    """总推送次数 / 按 trigger 分组 / 最近 24h / 失败率。"""
    db = get_async_client()[DEFAULT_DB]
    cur = db["push_history"].find({"user_id": user_id}, {"trigger": 1, "sent_at": 1})
    by_trigger: dict[str, int] = {}
    last_24h = 0
    now = datetime.now(timezone.utc)
    total = 0
    cutoff_iso = (now - timedelta(hours=24)).isoformat()
    async for d in cur:
        total += 1
        by_trigger[d.get("trigger", "unknown")] = by_trigger.get(d.get("trigger", "unknown"), 0) + 1
        if (d.get("sent_at") or "") >= cutoff_iso:
            last_24h += 1
    return {"total": total, "by_trigger": by_trigger, "last_24h": last_24h}
