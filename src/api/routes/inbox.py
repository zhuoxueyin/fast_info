"""
fastInfo · Inbox(用户个人推送历史)
"""
from fastapi import APIRouter, Depends, Query

from api.deps import require_user
from storage.mongo_writer import get_user_inbox
from api.schemas import InboxResponse

router = APIRouter(tags=["inbox"])


@router.get("/inbox", response_model=InboxResponse)
def list_inbox(
    user: dict = Depends(require_user),
    sort: str = Query("relevance", pattern="^(relevance|time)$"),
    subscription: str = Query(None, description="按订阅 ID 过滤"),
    category: str = Query(None, description="按类目过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """用户推送历史,支持按热度 / 时间排序,按订阅名 / 类目筛选"""
    return get_user_inbox(
        user_id=user["id"],
        sort=sort,
        subscription_id=subscription,
        category=category,
        page=page,
        page_size=page_size,
    )