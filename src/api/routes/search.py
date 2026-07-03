"""GET /api/search?q=...&limit=20&source=...&category=..."""
from fastapi import APIRouter, Query
from typing import Optional

from retrieval import hybrid_search
from ..schemas import SearchResponse, ItemView

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., min_length=1, description="关键词(空格=OR)"),
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None, description="限定源 qbitai/ifanr/..."),
    category: Optional[str] = None,
):
    results = hybrid_search(q, limit=limit, source=source, category=category)
    return SearchResponse(
        query=q,
        total=len(results),
        items=[_to_view(r) for r in results],
    )


def _to_view(d: dict) -> ItemView:
    return ItemView(
        id=str(d.get("_id", "")) or d.get("id"),
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
        score=d.get("score"),
    )
