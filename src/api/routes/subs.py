"""POST /api/subs · GET /api/subs · POST /api/subs/{id}/run · DELETE /api/subs/{id}
PATCH /api/subs/{id} (Day 4)
"""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional

from subscription import (
    parse_nl_to_subscription,
    save_subscription,
    list_subscriptions,
    get_subscription,
    run_subscription,
    update_subscription_after_run,
)
from ..deps import require_user
from ..schemas import (
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionView,
    SubsListResponse,
    RunSubscriptionResponse,
)

router = APIRouter(tags=["subscriptions"])


class NLParseRequest(BaseModel):
    nl_query: str


class SubscribePatch(BaseModel):
    """Day 4:支持 PATCH 修改订阅(暂停/启用/改渠道/改频率)"""
    is_active: Optional[bool] = None
    title: Optional[str] = None
    channels: Optional[list[str]] = None
    cron_expr: Optional[str] = None
    interval_min: Optional[int] = None
    max_items: Optional[int] = None
    categories_l1: Optional[list[str]] = None
    categories_l2: Optional[list[str]] = None
    keywords: Optional[list[str]] = None


@router.post("/subs/parse")
async def parse_only(req: NLParseRequest, user: dict = Depends(require_user)):
    """NL → 结构化(不存库,给前端预览用)"""
    sub = await parse_nl_to_subscription(req.nl_query, user_id=user["id"])
    return {
        "title": sub.get("title"),
        "keywords": sub.get("keywords", []),
        "sources": sub.get("sources", []),
        "categories_l1": sub.get("categories_l1", []),
        "categories_l2": sub.get("categories_l2", []),
        "cron_expr": sub.get("cron_expr"),
        "max_items": sub.get("max_items", 5),
        "channels": sub.get("channels", ["inbox"]),
        "interval_min": sub.get("interval_min", 0),
        "nl_query": sub.get("nl_query"),
        "fallback": sub.get("fallback", False),
    }


@router.post("/subs", response_model=SubscribeResponse)
async def create_subscription(req: SubscribeRequest, user: dict = Depends(require_user)):
    """NL → 解析 → 存 MongoDB,返回 sub_id。"""
    sub = await parse_nl_to_subscription(req.nl_query, user_id=user["id"])
    # 用户传了 channels/categories 覆盖解析结果
    if req.channels:
        sub["channels"] = req.channels
    if req.categories_l1:
        sub["categories_l1"] = req.categories_l1
    if req.categories_l2:
        sub["categories_l2"] = req.categories_l2
    if req.keywords:
        sub["keywords"] = req.keywords
    sub_id = save_subscription(sub)
    sub["_id"] = ObjectId(sub_id)
    return SubscribeResponse(sub=_to_view(sub), parsed={
        "keywords": sub.get("keywords", []),
        "sources": sub.get("sources", []),
        "categories_l1": sub.get("categories_l1", []),
        "categories_l2": sub.get("categories_l2", []),
        "cron_expr": sub.get("cron_expr"),
        "channels": sub.get("channels", []),
    })


@router.get("/subs", response_model=SubsListResponse)
async def list_my_subscriptions(user: dict = Depends(require_user)):
    subs = list_subscriptions(user_id=user["id"], active_only=False)
    return SubsListResponse(
        total=len(subs),
        items=[_to_view(s) for s in subs],
    )


@router.get("/subs/{sub_id}", response_model=SubscriptionView)
async def get_my_subscription(sub_id: str, user: dict = Depends(require_user)):
    """编辑页用:读单条订阅"""
    sub = get_subscription(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="非本人订阅,无权操作")
    return _to_view(sub)


@router.post("/subs/{sub_id}/run", response_model=RunSubscriptionResponse)
async def run_my_subscription(sub_id: str, user: dict = Depends(require_user)):
    sub = get_subscription(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="非本人订阅,无权操作")
    try:
        result = await run_subscription(sub)
    except Exception as e:
        update_subscription_after_run(sub_id, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=f"订阅执行失败: {e}")
    update_subscription_after_run(sub_id, success=True)
    return RunSubscriptionResponse(subscription_id=sub_id, **result)


@router.patch("/subs/{sub_id}", response_model=SubscriptionView)
async def patch_my_subscription(sub_id: str, req: SubscribePatch, user: dict = Depends(require_user)):
    """Day 4:暂停 / 启用 / 改字段"""
    sub = get_subscription(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="非本人订阅,无权操作")
    from storage.mongo_writer import get_db
    update: dict = {}
    for k, v in req.model_dump(exclude_unset=True).items():
        update[k] = v
    if update:
        from datetime import datetime, timezone
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        get_db()["subscriptions"].update_one({"_id": ObjectId(sub_id)}, {"$set": update})
    sub = get_subscription(sub_id)
    return _to_view(sub)


@router.post("/subs/{sub_id}/nl-patch")
async def nl_patch_my_subscription(
    sub_id: str,
    body: dict = Body(...),
    user: dict = Depends(require_user),
):
    """Day 6 v0.3.0:对话式改订阅(NL → 字段 delta)"""
    sub = get_subscription(sub_id)
    if not sub:
        raise HTTPException(404, "订阅不存在")
    if sub.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "非本人订阅,无权操作")
    nl_command = body.get("nl_command") or ""
    if not nl_command.strip():
        raise HTTPException(400, "nl_command 不能为空")
    from subscription.nl_patch import parse_nl_patch
    delta = await parse_nl_patch(nl_command, sub)
    if not delta:
        return {"delta": {}, "applied": [], "sub_id": sub_id, "message": "no fields to update"}
    # 字段类型校验 + 清洗
    update: dict = {}
    for k, v in delta.items():
        if k in {"max_items", "interval_min"}:
            try:
                update[k] = int(v)
            except (TypeError, ValueError):
                continue
        elif k == "is_active":
            update[k] = bool(v)
        elif k in {"channels", "categories_l1", "categories_l2", "keywords"}:
            if isinstance(v, list):
                update[k] = [str(x).strip() for x in v if x]
            elif isinstance(v, str):
                update[k] = [s.strip() for s in v.split(",") if s.strip()]
        else:
            update[k] = v
    if not update:
        return {"delta": delta, "applied": [], "sub_id": sub_id}
    # 写库 + 重算 next_run
    from datetime import datetime, timezone
    from storage.mongo_writer import get_db
    from bson import ObjectId
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "cron_expr" in update:
        try:
            from subscription import _next_run_simple
            update["next_run_at"] = _next_run_simple(update["cron_expr"], datetime.now(timezone.utc)).isoformat()
        except Exception:
            pass
    get_db()["subscriptions"].update_one({"_id": ObjectId(sub_id)}, {"$set": update})
    return {"delta": delta, "applied": list(update.keys()), "sub_id": sub_id}


@router.delete("/subs/{sub_id}")
async def delete_my_subscription(sub_id: str, user: dict = Depends(require_user)):
    sub = get_subscription(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    # admin 可以删除任何订阅,普通用户只能删自己的
    if sub.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="非本人订阅,无权操作")
    from storage.mongo_writer import get_db
    db = get_db()
    db["subscriptions"].delete_one({"_id": ObjectId(sub_id)})
    # 同时清理推送记录
    db["subscriptions_delivered"].delete_many({"subscription_id": sub_id})
    return {"deleted": sub_id}


def _to_view(d: dict) -> SubscriptionView:
    sources = d.get("sources", [])
    if isinstance(sources, str):
        sources = [sources]
    keywords = d.get("keywords", []) or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    categories_l1 = d.get("categories_l1", []) or []
    if isinstance(categories_l1, str):
        categories_l1 = [c.strip() for c in categories_l1.split(",") if c.strip()]
    categories_l2 = d.get("categories_l2", []) or []
    if isinstance(categories_l2, str):
        categories_l2 = [c.strip() for c in categories_l2.split(",") if c.strip()]
    channels = d.get("channels", ["inbox"]) or ["inbox"]
    if isinstance(channels, str):
        channels = [c.strip() for c in channels.split(",") if c.strip()]
    return SubscriptionView(
        id=str(d.get("_id", "")),
        user_id=str(d.get("user_id", "")),
        title=d.get("title", ""),
        nl_query=d.get("nl_query"),
        keywords=keywords,
        sources=sources,
        categories_l1=categories_l1,
        categories_l2=categories_l2,
        channels=channels,
        cron_expr=d.get("cron_expr", "0 9 * * *"),
        interval_min=int(d.get("interval_min", 0) or 0),
        next_run_at=d.get("next_run_at"),
        last_run_at=d.get("last_run_at"),
        is_active=d.get("is_active", True),
        max_items=d.get("max_items", 10),
    )