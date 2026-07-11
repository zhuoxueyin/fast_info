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
    """Day 4:支持 PATCH 修改订阅(暂停/启用/改渠道/改频率)
    Day 9:支持改 track_mode/duration_days/track_entity
    Day 13:支持改 feishu_targets(订阅实例维度指定飞书群)"""
    is_active: Optional[bool] = None
    title: Optional[str] = None
    channels: Optional[list[str]] = None
    feishu_targets: Optional[list[str]] = None
    cron_expr: Optional[str] = None
    interval_min: Optional[int] = None
    max_items: Optional[int] = None
    categories_l1: Optional[list[str]] = None
    categories_l2: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    track_mode: Optional[str] = None      # 'long' / 'short'
    duration_days: Optional[int] = None   # 改 short 时重算 expires_at
    track_entity: Optional[str] = None


def _normalize_feishu_targets(user: dict, targets: list | None) -> list[str]:
    """只保留用户 settings 里真实存在的飞书群 name。"""
    if not targets:
        return []
    from notifier import get_feishu_webhooks
    valid = {h["name"] for h in get_feishu_webhooks(user)}
    out: list[str] = []
    seen: set[str] = set()
    for t in targets:
        name = str(t or "").strip()
        if name and name in valid and name not in seen:
            out.append(name)
            seen.add(name)
    return out


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
    # Day 9:支持 track_mode / duration_days(临时话题转订阅默认 short)
    track_mode = req.track_mode if req.track_mode in ("short", "long") else "long"
    sub = await parse_nl_to_subscription(
        req.nl_query,
        user_id=user["id"],
        track_mode=track_mode,
        duration_days=req.duration_days,
    )
    # 用户传了 channels/categories 覆盖解析结果
    from .settings import _available_channels, CHANNEL_FIELDS
    avail = _available_channels(user)
    if req.channels is not None:
        # Day 7 一致性:即便用户传了,也要按 settings 实际可用的过滤一次
        # (勾了"邮件"但没配 SMTP,被静默 reject)
        sub["channels"] = [c for c in (req.channels or []) if c in avail and c in CHANNEL_FIELDS]
        # 用户全选了不可用的 → 兜底用 default_channels
        if not sub["channels"]:
            defaults = user.get("default_channels") or ["inbox"]
            sub["channels"] = [c for c in defaults if c in avail and c in CHANNEL_FIELDS] or ["inbox"]
    else:
        # 兜底(Day 7 一致性):没传 → 用用户全局默认;
        # 没有默认 → 至少给 inbox。
        # 保证入库的 channels 永远是可用渠道,且绝不为空。
        defaults = user.get("default_channels") or ["inbox"]
        sub["channels"] = [c for c in defaults if c in avail and c in CHANNEL_FIELDS] or ["inbox"]

    # 表单字段覆盖 LLM 解析(前端 Step2 已调过的以用户为准)
    if req.title and str(req.title).strip():
        sub["title"] = str(req.title).strip()
    if req.categories_l1:
        sub["categories_l1"] = req.categories_l1
    if req.categories_l2:
        sub["categories_l2"] = req.categories_l2
    if req.keywords:
        sub["keywords"] = req.keywords
    if req.track_entity:
        sub["track_entity"] = req.track_entity
    sub["max_items"] = int(req.max_items)
    sub["interval_min"] = int(req.interval_min or 0)
    # 非 short 跟踪才允许用表单 cron 覆盖(short 在 parse 里已锁 6h)
    if sub.get("track_mode") != "short" and req.cron_expr:
        from datetime import datetime, timezone
        from subscription import _next_run_simple
        sub["cron_expr"] = req.cron_expr
        try:
            sub["next_run_at"] = _next_run_simple(req.cron_expr, datetime.now(timezone.utc)).isoformat()
        except Exception:
            pass

    # 订阅实例维度飞书群:仅 channels 含 feishu 时生效
    if "feishu" in sub["channels"]:
        sub["feishu_targets"] = _normalize_feishu_targets(user, req.feishu_targets)
    else:
        sub["feishu_targets"] = []

    sub_id = save_subscription(sub)
    sub["_id"] = ObjectId(sub_id)
    return SubscribeResponse(sub=_to_view(sub), parsed={
        "keywords": sub.get("keywords", []),
        "sources": sub.get("sources", []),
        "categories_l1": sub.get("categories_l1", []),
        "categories_l2": sub.get("categories_l2", []),
        "cron_expr": sub.get("cron_expr"),
        "channels": sub.get("channels", []),
        "feishu_targets": sub.get("feishu_targets", []),
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
        # Day 9:手动触发的推送标记 trigger=manual,operator=当前用户名
        result = await run_subscription(sub, trigger="manual", operator=user.get("username", ""))
    except Exception as e:
        update_subscription_after_run(sub_id, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=f"订阅执行失败: {e}")
    update_subscription_after_run(sub_id, success=True)
    return RunSubscriptionResponse(subscription_id=sub_id, **result)


@router.patch("/subs/{sub_id}", response_model=SubscriptionView)
async def patch_my_subscription(sub_id: str, req: SubscribePatch, user: dict = Depends(require_user)):
    """Day 4:暂停 / 启用 / 改字段
    Day 9:支持改 track_mode / duration_days(转短期时自动重算 expires_at)"""
    sub = get_subscription(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="非本人订阅,无权操作")
    from storage.mongo_writer import get_db
    from datetime import datetime, timezone, timedelta
    from .settings import _available_channels, CHANNEL_FIELDS
    update: dict = {}
    for k, v in req.model_dump(exclude_unset=True).items():
        update[k] = v
    # 渠道按 settings 实际可用过滤
    if "channels" in update and update["channels"] is not None:
        avail = _available_channels(user)
        ch = [c for c in (update["channels"] or []) if c in avail and c in CHANNEL_FIELDS]
        update["channels"] = ch or ["inbox"]
    # 飞书群目标:与 channels 联动
    if "feishu_targets" in update or "channels" in update:
        final_channels = update.get("channels", sub.get("channels") or ["inbox"])
        if "feishu" not in final_channels:
            update["feishu_targets"] = []
        elif "feishu_targets" in update:
            update["feishu_targets"] = _normalize_feishu_targets(user, update.get("feishu_targets"))
    # Day 9:改 track_mode → duration_days 时,重算 expires_at
    if update.get("track_mode") == "short" or (update.get("track_mode") is None and sub.get("track_mode") == "short"):
        d = update.get("duration_days")
        if d is None:
            d = sub.get("duration_days") or 7
        if update.get("track_mode") is None:
            # 仅改 duration_days,沿用旧的 track_mode
            d = int(d)
            update["duration_days"] = d
            update["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()
        else:
            d = int(d) if d else 7
            update["duration_days"] = d
            update["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()
            # 转 short:缩短 cron 到 6h
            update["cron_expr"] = "0 */6 * * *"
    elif update.get("track_mode") == "long":
        # 转长期:清掉 expires_at,还原默认 cron
        update["expires_at"] = None
        update["duration_days"] = None
        update["cron_expr"] = "0 9 * * *"
    if update:
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        # cron 改了 → 重算 next_run
        if "cron_expr" in update:
            try:
                from subscription import _next_run_simple
                update["next_run_at"] = _next_run_simple(update["cron_expr"], datetime.now(timezone.utc)).isoformat()
            except Exception:
                pass
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


@router.get("/me/push-history")
async def list_my_push_history(
    user: dict = Depends(require_user),
    limit: int = Query(50, ge=1, le=200),
    trigger: Optional[str] = Query(None, description="manual / schedule / test / cli"),
):
    """Day 9:用户的推送历史(谁触发的、推什么、走哪些渠道、是否成功)。

    默认只返回当前用户自己的(以防 admin 偷窥别人的)。
    """
    from storage.push_history import list_for_user
    items = await list_for_user(user["id"], limit=limit, trigger=trigger)
    return {
        "total": len(items),
        "items": [
            {
                "id": str(d.get("_id", "")),
                "user_id": d.get("user_id", ""),
                "subscription_id": d.get("subscription_id"),
                "subscription_title": d.get("subscription_title", ""),
                "trigger": d.get("trigger", "unknown"),
                "operator": d.get("operator", "auto"),
                "channels_ok": d.get("channels_ok", []),
                "channels_fail": d.get("channels_fail", []),
                "channel_results": d.get("channel_results", {}),
                "items": d.get("items", []),
                "item_count": d.get("item_count", 0),
                "sent_at": d.get("sent_at"),
                "duration_ms": d.get("duration_ms", 0),
                "error": d.get("error"),
            }
            for d in items
        ],
    }


@router.get("/me/push-history/{history_id}")
async def get_my_push_history(
    history_id: str,
    user: dict = Depends(require_user),
):
    """Day 9:推送历史单条详情。"""
    from storage.push_history import get_by_id
    d = await get_by_id(history_id, user["id"])
    if not d:
        raise HTTPException(status_code=404, detail="推送记录不存在")
    return {
        "id": str(d.get("_id", "")),
        "user_id": d.get("user_id", ""),
        "subscription_id": d.get("subscription_id"),
        "subscription_title": d.get("subscription_title", ""),
        "trigger": d.get("trigger", "unknown"),
        "operator": d.get("operator", "auto"),
        "channels_ok": d.get("channels_ok", []),
        "channels_fail": d.get("channels_fail", []),
        "channel_results": d.get("channel_results", {}),
        "items": d.get("items", []),
        "item_count": d.get("item_count", 0),
        "sent_at": d.get("sent_at"),
        "duration_ms": d.get("duration_ms", 0),
        "error": d.get("error"),
    }


@router.get("/me/push-history-stats")
async def push_history_stats(user: dict = Depends(require_user)):
    """Day 9:按 trigger 聚合的推送统计。"""
    from storage.push_history import stats_for_user
    return await stats_for_user(user["id"])


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
    # 兜底(Day 7):空数组 / 全是 unknown → 给 inbox
    if not channels:
        channels = ["inbox"]
    feishu_targets = d.get("feishu_targets") or []
    if isinstance(feishu_targets, str):
        feishu_targets = [t.strip() for t in feishu_targets.split(",") if t.strip()]
    feishu_targets = [str(t).strip() for t in feishu_targets if t]
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
        feishu_targets=feishu_targets,
        cron_expr=d.get("cron_expr", "0 9 * * *"),
        interval_min=int(d.get("interval_min", 0) or 0),
        next_run_at=d.get("next_run_at"),
        last_run_at=d.get("last_run_at"),
        is_active=d.get("is_active", True),
        max_items=d.get("max_items", 10),
        # Day 9:短期跟踪字段
        track_mode=d.get("track_mode", "long"),
        expires_at=d.get("expires_at"),
        duration_days=d.get("duration_days"),
        track_entity=d.get("track_entity"),
    )