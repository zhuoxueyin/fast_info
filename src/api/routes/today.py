"""GET /api/today?limit=20&source=...&category=..."""
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional

from storage.mongo_writer import get_sync_client, DEFAULT_DB
from ..schemas import TodayResponse, ItemView
from taxonomy import CATEGORY_L1

router = APIRouter(tags=["today"])


@router.get("/today", response_model=TodayResponse)
async def today_endpoint(
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = None,
    category: Optional[str] = None,
):
    db = get_sync_client()[DEFAULT_DB]
    q: dict = {}
    if source:
        q["source"] = source
    if category:
        if category in CATEGORY_L1:
            q["category_l1"] = category
        else:
            q["category"] = category
    cursor = db["items"].find(q).sort("fetched_at", -1).limit(limit)
    items = []
    for it in cursor:
        items.append(_to_view(it))
    return TodayResponse(limit=limit, items=items)


def _to_view(d: dict) -> ItemView:
    return ItemView(
        id=str(d.get("_id", "")),
        source=d.get("source", ""),
        url=d.get("url", ""),
        title=d.get("title", ""),
        summary=d.get("summary", ""),
        category=d.get("category"),
        category_l1=d.get("category_l1"),
        relevance=d.get("relevance"),
        published_at=d.get("published_at"),
        fetched_at=d.get("fetched_at"),
        author=d.get("author"),
        tags=d.get("tags", []) or [],
    )
