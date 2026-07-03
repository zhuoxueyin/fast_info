"""GET /api/hot?limit=10&hours=24&threshold=0.7&category=..."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from storage.mongo_writer import get_sync_client, DEFAULT_DB
from ..schemas import HotResponse, ItemView
from taxonomy import CATEGORY_L1

router = APIRouter(tags=["hot"])


@router.get("/hot", response_model=HotResponse)
async def hot_endpoint(
    limit: int = Query(10, ge=1, le=50),
    hours: int = Query(24, ge=1, le=168, description="最近 N 小时"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="相关度阈值"),
    category: Optional[str] = None,
):
    db = get_sync_client()[DEFAULT_DB]
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q: dict = {
        "fetched_at": {"$gte": since},
        "relevance": {"$gte": threshold},
    }
    if category:
        if category in CATEGORY_L1:
            q["category_l1"] = category
        else:
            q["category"] = category
    cursor = db["items"].find(q).sort(
        [("relevance", -1), ("fetched_at", -1)]
    ).limit(limit)
    items = []
    for it in cursor:
        items.append(_to_view(it))
    return HotResponse(hours=hours, threshold=threshold, total=len(items), items=items)


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
