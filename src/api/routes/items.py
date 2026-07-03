"""GET /api/items/{id} · GET /api/items?ids=a,b,c"""
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from typing import List

from storage.mongo_writer import get_sync_client, DEFAULT_DB
from ..schemas import ItemView

router = APIRouter(tags=["items"])


@router.get("/items/{item_id}", response_model=ItemView)
async def get_item(item_id: str):
    """单条资讯详情。id 可以是 MongoDB ObjectId,也可以是 url_hash。"""
    db = get_sync_client()[DEFAULT_DB]
    doc = None
    # 先按 ObjectId 查
    if len(item_id) == 24:
        try:
            doc = db["items"].find_one({"_id": ObjectId(item_id)})
        except Exception:
            pass
    # 兜底:按 url_hash
    if not doc:
        doc = db["items"].find_one({"url_hash": item_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"item {item_id} 不存在")
    return _to_view(doc)


@router.get("/items", response_model=List[ItemView])
async def list_items(
    ids: str = Query(..., description="逗号分隔的 id 列表"),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_sync_client()[DEFAULT_DB]
    id_list = [i.strip() for i in ids.split(",") if i.strip()][:limit]
    items = []
    for iid in id_list:
        doc = None
        if len(iid) == 24:
            try:
                doc = db["items"].find_one({"_id": ObjectId(iid)})
            except Exception:
                pass
        if not doc:
            doc = db["items"].find_one({"url_hash": iid})
        if doc:
            items.append(_to_view(doc))
    return items


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
