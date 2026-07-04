"""fastInfo · 临时话题 (Day 6 v0.3.0)

用户说一句话("关注世界杯") → 生成 24h 临时 workspace,
关联 items + L1/L2 分类。与 subscription 不同:
- 不持久化(24h TTL 自动删)
- 不推送(只读)
- 可一键转订阅(走常规订阅链路)

数据模型 (MongoDB temp_topics collection):
{
    _id: ObjectId,
    tid: str (URL 短 ID,8 字符),
    user_id: str,
    nl_query: str,                 # 原始 NL
    parsed: {
        title: str,
        keywords: list,
        categories_l1: list,
        categories_l2: list,
        sources: list,
    },
    items: list[str],               # item _id 列表
    item_count: int,
    created_at: iso,
    expires_at: iso,                # 24h 后,TTL 索引
    converted_to_sub_id: Optional[str],
}
"""
from __future__ import annotations
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from .mongo_writer import get_sync_client, get_async_client, DEFAULT_DB


TEMP_TTL_HOURS = 24


def _gen_tid() -> str:
    """生成 8 字符 URL-safe 短 ID"""
    return secrets.token_urlsafe(6)[:8]


def create_temp_topic(user_id: str, nl_query: str, parsed: dict, items: list[str]) -> dict:
    """创建临时话题,返回 doc(含 _id)"""
    db = get_sync_client()[DEFAULT_DB]
    now = datetime.now(timezone.utc)
    tid = _gen_tid()
    doc = {
        "tid": tid,
        "user_id": user_id,
        "nl_query": nl_query,
        "parsed": parsed,
        "items": items,
        "item_count": len(items),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=TEMP_TTL_HOURS)).isoformat(),
        "converted_to_sub_id": None,
    }
    res = db["temp_topics"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


def get_temp_topic(tid: str) -> Optional[dict]:
    db = get_sync_client()[DEFAULT_DB]
    return db["temp_topics"].find_one({"tid": tid})


def get_temp_topic_by_id(oid: str) -> Optional[dict]:
    """按 ObjectId 查(给 convert 用)"""
    from bson import ObjectId
    try:
        db = get_sync_client()[DEFAULT_DB]
        return db["temp_topics"].find_one({"_id": ObjectId(oid)})
    except Exception:
        return None


def list_user_topics(user_id: str, active_only: bool = True, limit: int = 50) -> list[dict]:
    db = get_sync_client()[DEFAULT_DB]
    q: dict = {"user_id": user_id}
    if active_only:
        q["expires_at"] = {"$gt": datetime.now(timezone.utc).isoformat()}
    return list(db["temp_topics"].find(q).sort("created_at", -1).limit(limit))


def convert_topic_to_sub(tid: str, user_id: str) -> Optional[str]:
    """把临时话题转为长期订阅,返回 sub_id(None = 失败)"""
    from subscription import parse_nl_to_subscription, save_subscription
    doc = get_temp_topic(tid)
    if not doc or doc.get("user_id") != user_id:
        return None
    if doc.get("converted_to_sub_id"):
        return doc["converted_to_sub_id"]  # idempotent
    # 调 NL 解析
    parsed_sub = asyncio.run(parse_nl_to_subscription(doc["nl_query"], user_id=user_id))
    parsed = doc["parsed"]
    parsed_sub["title"] = parsed.get("title") or parsed_sub.get("title")
    parsed_sub["keywords"] = parsed.get("keywords", parsed_sub.get("keywords", []))
    parsed_sub["sources"] = parsed.get("sources", parsed_sub.get("sources", ["all"]))
    parsed_sub["categories_l1"] = parsed.get("categories_l1", parsed_sub.get("categories_l1", []))
    parsed_sub["categories_l2"] = parsed.get("categories_l2", parsed_sub.get("categories_l2", []))
    parsed_sub["channels"] = parsed_sub.get("channels", ["inbox"])
    sub_id = save_subscription(parsed_sub)
    # 标记已转
    db = get_sync_client()[DEFAULT_DB]
    db["temp_topics"].update_one(
        {"tid": tid},
        {"$set": {"converted_to_sub_id": sub_id}}
    )
    return sub_id


async def setup_indexes() -> None:
    """在 temp_topics 上建索引(TTL + 短 ID unique + 用户索引)"""
    db = get_async_client()[DEFAULT_DB]
    try:
        # TTL:24h 自动删过期话题
        await db["temp_topics"].create_index("expires_at", expireAfterSeconds=0)
        # 短 ID 唯一
        await db["temp_topics"].create_index("tid", unique=True)
        # 用户列表查
        await db["temp_topics"].create_index([("user_id", 1), ("created_at", -1)])
    except Exception:
        pass


# ============================================================
# CLI sync 包装(给 fastinfo.py 用,不裸 asyncio.run 嵌套)
# ============================================================

def run_create_topic_now(nl_query: str, user_id: str, max_items: int = 12, hours: int = 48) -> dict:
    """CLI sync 入口:复用 LLM NL 解析 + Mongo 检索 + 落库"""
    parsed_sub = asyncio.run(parse_nl_to_subscription(nl_query, user_id=user_id))
    parsed = {
        "title": parsed_sub.get("title") or nl_query[:15],
        "keywords": parsed_sub.get("keywords", []),
        "categories_l1": parsed_sub.get("categories_l1", []),
        "categories_l2": parsed_sub.get("categories_l2", []),
        "sources": parsed_sub.get("sources", ["all"]),
    }
    db = get_sync_client()[DEFAULT_DB]
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q: dict = {"fetched_at": {"$gte": since}}
    if "all" not in parsed["sources"]:
        q["source"] = {"$in": parsed["sources"]}
    if parsed["keywords"]:
        k = []
        for kw in parsed["keywords"][:6]:
            k.append({"title": {"$regex": kw, "$options": "i"}})
            k.append({"summary": {"$regex": kw, "$options": "i"}})
        q["$or"] = k
    if parsed["categories_l1"]:
        l1 = [{"category_l1": {"$in": parsed["categories_l1"]}}, {"category": {"$in": parsed["categories_l1"]}}]
        if "$or" in q:
            q["$and"] = [{"$or": q["$or"]}, {"$or": l1}]
            del q["$or"]
        else:
            q["$or"] = l1
    items = list(db["items"].find(q).sort("fetched_at", -1).limit(max_items))
    item_ids = [str(it["_id"]) for it in items]
    doc = create_temp_topic(user_id=user_id, nl_query=nl_query, parsed=parsed, items=item_ids)
    return {"doc": doc, "items": items, "parsed": parsed}
