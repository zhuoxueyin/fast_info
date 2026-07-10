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
            "topic_score": it.get("_topic_score"),
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
    """NL → 临时话题 → 立刻从 items 库命中并返回

    检索策略(Day 13 实体优先):
      - core 实体词硬匹配(title/summary),丢掉「明星/歌手」等泛词
      - 相关度打分 + 标题去重 + 时间窗递进放宽
    """
    from retrieval.topic_search import search_items_for_topic, extract_core_terms

    # 1. NL 解析(复用订阅解析)
    parsed_sub = await parse_nl_to_subscription(req.nl_query, user_id=user["id"])
    track_entity = parsed_sub.get("track_entity")
    # 若 LLM 没吐 track_entity,用 core 抽取兜底
    if not track_entity:
        cores = extract_core_terms(req.nl_query, {
            "title": parsed_sub.get("title"),
            "keywords": parsed_sub.get("keywords", []),
        })
        track_entity = cores[0] if cores else None

    parsed = {
        "title": parsed_sub.get("title") or req.nl_query[:15],
        "keywords": parsed_sub.get("keywords", []),
        "categories_l1": parsed_sub.get("categories_l1", []),
        "categories_l2": parsed_sub.get("categories_l2", []),
        "sources": req.sources or parsed_sub.get("sources", ["all"]),
        "track_entity": track_entity,
    }

    # 2. 实体优先检索(见 retrieval.topic_search)
    items, search_meta = search_items_for_topic(
        nl_query=req.nl_query,
        parsed=parsed,
        max_items=req.max_items,
        hours=req.hours,
        sources=parsed["sources"],
    )
    # 把检索元信息挂到 parsed,方便前端/排障(不影响旧字段)
    parsed["search"] = {
        "core_terms": search_meta.get("core_terms", []),
        "hours_used": search_meta.get("hours_used"),
        "scanned": search_meta.get("scanned", 0),
    }

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
        raw_ids = [i for i in doc.get("items", []) if ObjectId.is_valid(i)]
        obj_ids = [ObjectId(i) for i in raw_ids]
        found = {
            str(it["_id"]): it
            for it in db["items"].find({"_id": {"$in": obj_ids}})
        }
        # 保持创建时的相关度排序(item_ids 顺序),不要再按 fetched_at 打乱
        items = [found[i] for i in raw_ids if i in found]
    except Exception:
        items = []
    return _to_view(doc, items)


@router.post("/now/{tid}/convert")
async def convert_topic(
    tid: str,
    duration_days: Optional[int] = None,
    track_mode: Optional[str] = None,
    user: dict = Depends(require_user),
):
    """临时话题 → 订阅(Day 9:支持短期 / 长期)
    duration_days: 短期天数(None = 用默认 7)
    track_mode: 'short' / 'long'(None = 默认识别为短期)
    """
    # 1. 先 await LLM 解析(在 FastAPI event loop 里,不能再 asyncio.run 嵌套)
    from storage.temp_topics import get_temp_topic
    doc = get_temp_topic(tid)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(404, "topic not found")
    if doc.get("converted_to_sub_id"):
        # idempotent
        return {
            "converted": True,
            "subscription_id": doc["converted_to_sub_id"],
            "tid": tid,
            "idempotent": True,
        }
    parsed_sub = await parse_nl_to_subscription(doc["nl_query"], user_id=user["id"])
    # 2. 决定 track_mode:显式传 → 用显式;没传 → 默认 short(临时话题天生是短期诉求)
    mode = track_mode if track_mode in ("short", "long") else "short"
    # 3. 同步转订阅(纯写库,不会再调 LLM)
    sub_id = convert_topic_to_sub(
        tid,
        user_id=user["id"],
        parsed_sub=parsed_sub,
        duration_days=duration_days,
        track_mode=mode,
    )
    if not sub_id:
        raise HTTPException(404, "topic not found")
    return {
        "converted": True,
        "subscription_id": sub_id,
        "tid": tid,
        "track_mode": mode,
        "track_entity": parsed_sub.get("track_entity"),
    }


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
