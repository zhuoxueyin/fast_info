"""临时话题 API (Day 6 v0.3.0)

POST /api/topics/now              NL → 临时话题(检索 items)
GET  /api/topics/now/{tid}        查一个
POST /api/topics/now/{tid}/convert 转长期订阅
GET  /api/topics/list             列我的临时话题
GET  /api/topics/recent/{tid}/items 查关联的 items
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from subscription import parse_nl_to_subscription
from storage.temp_topics import (
    create_temp_topic, get_temp_topic, list_user_topics,
    convert_topic_to_sub,
)
from storage.mongo_writer import get_db
from ..deps import require_user


router = APIRouter(prefix="/topics", tags=["topics"])


class TopicNowRequest(BaseModel):
    nl_query: str
    max_items: int = 12
    hours: int = 48  # 检索最近 N 小时的 items
    sources: Optional[list[str]] = None  # 覆盖解析的 sources


def _to_items_view(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        out.append({
            "id": str(it.get("_id", "")),
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "source": it.get("source", ""),
            "category": it.get("category", "") or it.get("category_l1", ""),
            "summary": it.get("summary", "")[:400],
            "published_at": it.get("published_at"),
            "fetched_at": it.get("fetched_at"),
            "relevance": it.get("relevance", 0.5),
            "title_zh": it.get("title_zh"),
            "summary_zh": it.get("summary_zh"),
        })
    return out


def _to_view(doc: dict, items: list[dict] | None = None) -> dict:
    return {
        "tid": doc["tid"],
        "user_id": doc.get("user_id", ""),
        "nl_query": doc.get("nl_query", ""),
        "parsed": doc.get("parsed", {}),
        "items": _to_items_view(items) if items is not None else doc.get("items", []),
        "item_count": doc.get("item_count", 0),
        "created_at": doc.get("created_at", ""),
        "expires_at": doc.get("expires_at", ""),
        "converted_to_sub_id": doc.get("converted_to_sub_id"),
    }


@router.post("/now")
async def create_topic_now(req: TopicNowRequest, user: dict = Depends(require_user)):
    """NL → 临时话题 → 立刻从 items 库命中并返回"""
    # 1. NL 解析(复用订阅解析)
    parsed_sub = await parse_nl_to_subscription(req.nl_query, user_id=user["id"])
    parsed = {
        "title": parsed_sub.get("title") or req.nl_query[:15],
        "keywords": parsed_sub.get("keywords", []),
        "categories_l1": parsed_sub.get("categories_l1", []),
        "categories_l2": parsed_sub.get("categories_l2", []),
        "sources": req.sources or parsed_sub.get("sources", ["all"]),
    }
    # 2. 从 items 库检索
    db = get_db()
    since = (datetime.now(timezone.utc) - timedelta(hours=req.hours)).isoformat()
    q: dict = {"fetched_at": {"$gte": since}}
    if "all" not in parsed["sources"]:
        q["source"] = {"$in": parsed["sources"]}
    # 关键词正则 OR
    if parsed["keywords"]:
        keyword_clauses = []
        for kw in parsed["keywords"][:6]:
            keyword_clauses.append({"title": {"$regex": kw, "$options": "i"}})
            keyword_clauses.append({"summary": {"$regex": kw, "$options": "i"}})
        q["$or"] = keyword_clauses
    # L1 类目(兼容老 category 字段)
    if parsed["categories_l1"]:
        l1_clauses = [{"category_l1": {"$in": parsed["categories_l1"]}}, {"category": {"$in": parsed["categories_l1"]}}]
        if "$or" in q:
            q["$and"] = [{"$or": q["$or"]}, {"$or": l1_clauses}]
            del q["$or"]
        else:
            q["$or"] = l1_clauses
    items = list(db["items"].find(q).sort("fetched_at", -1).limit(req.max_items))
    # 3. 创建临时话题
    item_ids = [str(it["_id"]) for it in items]
    doc = create_temp_topic(
        user_id=user["id"],
        nl_query=req.nl_query,
        parsed=parsed,
        items=item_ids,
    )
    return _to_view(doc, items)


@router.get("/now/{tid}")
async def get_topic(tid: str, user: dict = Depends(require_user)):
    doc = get_temp_topic(tid)
    if not doc:
        raise HTTPException(404, "topic not found or expired (24h TTL)")
    if doc.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "not your topic")
    db = get_db()
    try:
        obj_ids = [ObjectId(i) for i in doc.get("items", []) if ObjectId.is_valid(i)]
        items = list(db["items"].find({"_id": {"$in": obj_ids}}).sort("fetched_at", -1))
    except Exception:
        items = []
    return _to_view(doc, items)


@router.post("/now/{tid}/convert")
async def convert_topic(tid: str, user: dict = Depends(require_user)):
    """临时话题 → 长期订阅"""
    sub_id = convert_topic_to_sub(tid, user_id=user["id"])
    if not sub_id:
        raise HTTPException(404, "topic not found")
    return {"converted": True, "subscription_id": sub_id, "tid": tid}


@router.get("/list")
async def list_topics(
    active_only: bool = Query(True),
    user: dict = Depends(require_user),
):
    """列我的临时话题(active_only=True 只列还没过期的)"""
    docs = list_user_topics(user_id=user["id"], active_only=active_only)
    out = []
    for d in docs:
        out.append({
            "tid": d.get("tid"),
            "nl_query": d.get("nl_query", ""),
            "title": d.get("parsed", {}).get("title", d.get("nl_query", "")[:15]),
            "item_count": d.get("item_count", 0),
            "created_at": d.get("created_at", ""),
            "expires_at": d.get("expires_at", ""),
            "converted_to_sub_id": d.get("converted_to_sub_id"),
        })
    return {"items": out, "total": len(out)}
