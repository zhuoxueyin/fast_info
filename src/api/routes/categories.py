"""
fastInfo · 类目列表(公开)
"""
from fastapi import APIRouter
from storage.mongo_writer import list_categories

router = APIRouter(tags=["categories"])


@router.get("/categories")
def list_all_categories():
    """items.category 的 distinct 列表"""
    return {"categories": list_categories()}