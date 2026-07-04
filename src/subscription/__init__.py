"""
fastInfo · 订阅引擎
====================

核心能力:
- NL → Subscription:把"帮我每天看 AI 推理论文"这类自然语言解析成结构化订阅
- 订阅执行:按订阅定义,跑"抓 RSS + 摘要 + 写库"流程
- 调度:支持 cron 表达式,简易调度器循环调度

数据模型(写入 MongoDB subscriptions 集合):
{
    id, user_id, title, nl_query,
    keywords, sources, categories, languages,
    cron_expr, timezone, delivery,
    summary_style, max_items,
    is_active, last_run_at, next_run_at, run_count, error_count, last_error,
    created_at, updated_at
}
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from storage.mongo_writer import get_sync_client, get_async_client, upsert_item_async
from llm.model_registry import build_default_registry


DEFAULT_DB = "fastinfo"


# ============================================================
# Cron 简化解析(只支持常见表达式,够 MVP)
# ============================================================

def _next_run_simple(cron: str, now: datetime) -> datetime:
    """
    简化版 cron 解析,支持:
        "0 9 * * *"          每天 9:00
        "0 */2 * * *"        每 2 小时
        "*/30 * * * *"       每 30 分钟
        "@hourly"            每小时
        "@daily" / "@midnight"  每天 0:00

    返回:下次运行时间(UTC)
    """
    cron = cron.strip()
    if cron == "@hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if cron in ("@daily", "@midnight"):
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return tomorrow
    if cron == "@weekly":
        days_to_sunday = 6 - now.weekday()
        return (now + timedelta(days=days_to_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)

    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"bad cron expr: {cron}")

    minute, hour, dom, mon, dow = parts

    # 简化策略:从 now+1min 开始,扫到 cron 匹配为止,最多扫 7 天
    cur = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(7 * 24 * 60):
        if _match_field(minute, cur.minute) and \
           _match_field(hour, cur.hour) and \
           _match_field(dom, cur.day) and \
           _match_field(mon, cur.month) and \
           _match_field(dow, cur.weekday() % 7):
            return cur
        cur += timedelta(minutes=1)
    raise ValueError(f"can't find next run for cron: {cron}")


def _match_field(spec: str, value: int) -> bool:
    """匹配单个 cron 字段(m,h,dom,mon,dow)"""
    if spec == "*":
        return True
    if spec.startswith("*/"):
        step = int(spec[2:])
        return value % step == 0
    if "," in spec:
        return any(_match_field(p, value) for p in spec.split(","))
    if "-" in spec:
        start, end = spec.split("-")
        return int(start) <= value <= int(end)
    return int(spec) == value


# ============================================================
# NL → Subscription
# ============================================================

async def parse_nl_to_subscription(nl_query: str, user_id: Optional[str] = None) -> dict:
    """
    把自然语言订阅描述解析成结构化 Subscription。

    用 nl_parse 模型组(M3 thinking 模式)。
    user_id 不传则从当前 CLI session 取(自动 by 用户)。
    """
    if user_id is None:
        try:
            from auth import current_user
            user = current_user()
            user_id = user["id"] if user else "anonymous"
        except Exception:
            user_id = "anonymous"
    registry = build_default_registry()
    messages = [
        {
            "role": "system",
            "content": (
                "你是 fastInfo 订阅解析助手。\n"
                "根据用户的自然语言描述,生成一个 JSON 订阅配置。\n\n"
                "字段说明:\n"
                "  title: 简短标题(15 字以内)\n"
                "  keywords: 关键词数组(中文 + 英文,3-8 个)\n"
                "  sources: 数据源数组,['all'] 即可\n"
                "  categories_l1: 一级类目,可选 ['科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他']\n"
                "  categories_l2: 二级类目,可选 ['大模型', 'AI芯片', 'AI应用', 'AI框架', '机器人', '互联网', '硬件', '数码评测', '科技融资', '开源', '足球', '篮球', '电竞', '影视', '音乐', '明星', '综艺', '动漫', '宏观', 'A股', '美股', '港股', '币圈', '创业', '新能源', '自动驾驶', '新势力', '传统车企']\n"
                "  cron_expr: cron 表达式,默认 '0 9 * * *'\n"
                "  max_items: 每次最多取 N 条,默认 10\n"
                "  channels: ['inbox'] (默认站内收件箱)\n"
                "  interval_min: 自定义间隔分钟;0=用 cron\n\n"
                "严格按 JSON 输出,不要 markdown 包裹,不要解释。"
            ),
        },
        {
            "role": "user",
            "content": nl_query,
        },
    ]

    parsed = None
    try:
        result = await registry.get("nl_parse").chat(messages, max_tokens=600, temperature=0.2)
        content = result["choices"][0]["message"]["content"].strip()
        cleaned = re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>", "", content, flags=re.DOTALL).strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", cleaned)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"[parse_nl] LLM 调用失败,使用默认解析: {type(e).__name__}: {str(e)[:100]}")

    if parsed is None:
        parsed = {
            "title": nl_query[:15],
            "keywords": re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", nl_query)[:5],
            "sources": ["all"],
            "categories_l1": [],
            "categories_l2": [],
            "cron_expr": "0 9 * * *",
            "max_items": 10,
            "channels": ["inbox"],
            "interval_min": 0,
        }

    parsed.setdefault("title", nl_query[:15])

    def _ensure_list(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return []

    parsed["keywords"] = _ensure_list(parsed.get("keywords", []))
    parsed["sources"] = _ensure_list(parsed.get("sources", ["all"])) or ["all"]
    parsed["categories_l1"] = _ensure_list(parsed.get("categories_l1", []))
    parsed["categories_l2"] = _ensure_list(parsed.get("categories_l2", []))
    parsed["channels"] = _ensure_list(parsed.get("channels", ["inbox"])) or ["inbox"]
    parsed.setdefault("cron_expr", "0 9 * * *")
    parsed.setdefault("max_items", 10)
    parsed.setdefault("interval_min", 0)

    now = datetime.now(timezone.utc)
    next_run = _next_run_simple(parsed["cron_expr"], now)
    sub = {
        "user_id": user_id,
        "title": parsed["title"],
        "nl_query": nl_query,
        "keywords": parsed["keywords"],
        "sources": parsed["sources"],
        "categories_l1": parsed["categories_l1"],
        "categories_l2": parsed["categories_l2"],
        "channels": parsed["channels"],
        "cron_expr": parsed["cron_expr"],
        "interval_min": int(parsed["interval_min"]),
        "max_items": int(parsed["max_items"]),
        "is_active": True,
        "last_run_at": None,
        "next_run_at": next_run.isoformat(),
        "run_count": 0,
        "error_count": 0,
        "last_error": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    return sub


def save_subscription(sub: dict) -> str:
    """写入 MongoDB,返回 _id"""
    # 如果 sub 没设 user_id,从当前 session 取
    if not sub.get("user_id") or sub.get("user_id") == "local":
        try:
            from auth import current_user
            u = current_user()
            if u:
                sub["user_id"] = u["id"]
        except Exception:
            pass
    db = get_sync_client()[DEFAULT_DB]
    res = db["subscriptions"].insert_one(sub)
    return str(res.inserted_id)


def list_subscriptions(user_id: Optional[str] = None, active_only: bool = True) -> list[dict]:
    """列出订阅,默认只列当前用户的"""
    if user_id is None:
        try:
            from auth import current_user
            u = current_user()
            user_id = u["id"] if u else None
        except Exception:
            user_id = None
    db = get_sync_client()[DEFAULT_DB]
    q: dict = {}
    if user_id:
        q["user_id"] = user_id
    if active_only:
        q["is_active"] = True
    return list(db["subscriptions"].find(q).sort("created_at", -1))


def get_subscription(sub_id: str) -> Optional[dict]:
    from bson import ObjectId
    db = get_sync_client()[DEFAULT_DB]
    try:
        return db["subscriptions"].find_one({"_id": ObjectId(sub_id)})
    except Exception:
        return None


def update_subscription_after_run(sub_id: str, success: bool, error: Optional[str] = None):
    from bson import ObjectId
    db = get_sync_client()[DEFAULT_DB]
    sub = db["subscriptions"].find_one({"_id": ObjectId(sub_id)})
    if not sub:
        return
    next_run = _next_run_simple(sub["cron_expr"], datetime.now(timezone.utc))
    update: dict = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "next_run_at": next_run.isoformat(),
        "run_count": sub.get("run_count", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if success:
        update["last_error"] = None
    else:
        update["error_count"] = sub.get("error_count", 0) + 1
        update["last_error"] = error
    db["subscriptions"].update_one({"_id": ObjectId(sub_id)}, {"$set": update})


# ============================================================
# 订阅执行
# ============================================================

async def _find_user_doc(db, user_id: str) -> dict | None:
    """根据 user_id (ObjectId hex string) 查 users 集合。"""
    from bson import ObjectId
    try:
        return await db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


async def run_subscription(sub: dict) -> dict:
    """
    执行一个订阅(Day 4 升级):
    - L1 硬过滤 + L2 软权重
    - 多渠道推送(inbox 默认 + email/feishu/wechat/webhook)
    """
    keywords = sub.get("keywords", [])
    sources = sub.get("sources", ["all"])
    categories = sub.get("categories", [])
    categories_l1 = sub.get("categories_l1", [])
    categories_l2 = sub.get("categories_l2", [])
    channels = sub.get("channels", ["inbox"])
    max_items = int(sub.get("max_items", 10))
    lookback_hours = int(sub.get("lookback_hours", 48))
    require_all_keywords = bool(sub.get("require_all_keywords", False))

    db = get_async_client()[DEFAULT_DB]

    # channels: 订阅自身字段，为空时默认仅 inbox
    if not channels:
        channels = ["inbox"]

    # 1. 从 MongoDB 读最近 lookback_hours 小时的 items
    since = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    q: dict = {"fetched_at": {"$gte": since}}
    if "all" not in sources:
        q["source"] = {"$in": sources}

    candidates = []
    kws_lower = [k.lower() for k in keywords]
    seen_ids: set[str] = set()
    async for item in db["items"].find(q).sort("fetched_at", -1).limit(max_items * 30):
        iid = str(item.get("_id", ""))
        if iid in seen_ids:
            continue

        # 关键词过滤(硬过滤)
        if keywords:
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            if require_all_keywords:
                hit = all(k in text for k in kws_lower)
            else:
                hit = any(k in text for k in kws_lower)
            if not hit:
                continue

        # L1/L2 分类过滤
        cat_raw = item.get("category", "")
        from taxonomy import normalize_l1
        item_l1 = normalize_l1(cat_raw)
        if categories_l1 and item_l1 not in categories_l1:
            continue  # L1 不命中 → 硬跳过

        # 排序权重
        boost = 0.0
        if categories_l2 and cat_raw in categories_l2:
            boost += 0.15
        if categories and any(c in cat_raw for c in categories):
            boost += 0.1

        item["_boost"] = boost
        seen_ids.add(iid)
        candidates.append(item)
        if len(candidates) >= max_items * 3:
            break

    candidates.sort(key=lambda x: (x.get("_boost", 0), x.get("relevance", 0)), reverse=True)
    candidates = candidates[:max_items]

    if not candidates:
        return {"scanned": 0, "matched": 0, "delivered": 0, "skipped": "no matches"}

    # 2. 跳过已推送
    sub_id = str(sub.get("_id", ""))
    user_id = sub.get("user_id", "anonymous")
    delivered = db["subscriptions_delivered"]
    delivered_ids = set()
    async for d in delivered.find({"subscription_id": sub_id}):
        delivered_ids.add(d["item_id"])

    new_items = [it for it in candidates if str(it["_id"]) not in delivered_ids][:max_items]

    # 3. 标记已推送
    if new_items:
        from datetime import datetime as _dt
        docs = [{
            "subscription_id": sub_id,
            "user_id": user_id,
            "item_id": str(it["_id"]),
            "delivered_at": _dt.now(timezone.utc).isoformat(),
        } for it in new_items]
        try:
            await delivered.insert_many(docs, ordered=False)
        except Exception:
            pass

    # 4. 多渠道推送
    if new_items:
        user_doc = await _find_user_doc(db, user_id) or {}
        print(f"  [sub run] {sub_id[:8]} channels={channels} feishu_webhook={'***' if user_doc.get('feishu_webhook') else 'MISSING'} items={len(new_items)}")
        await _render_and_send(user_doc, sub, new_items, channels)

    return {
        "scanned": max_items * 5,
        "matched": len(candidates),
        "delivered": len(new_items),
    }


async def _render_and_send(user_doc: dict, sub: dict, items: list, channels: list[str]):
    """渲染订阅消息 + 按 channels 多渠道推送(全部用 Notifier 抽象)"""
    from notifier import send_all
    from .format_push import format_html, format_markdown, format_feishu_card, inbox_url_for
    site_base = os.environ.get("FASTINFO_SITE_BASE", "")
    inbox_url = inbox_url_for(site_base)
    title = f"[fastInfo] {sub.get('title', '订阅')} · {len(items)} 条新内容"
    # 三种格式主体生成
    body_html  = format_html(sub, items, inbox_url)
    body_md    = format_markdown(sub, items, inbox_url)
    card       = format_feishu_card(sub, items, inbox_url)
    # 多渠道分发:
    #   - inbox / email: body_html
    #   - feishu / wechat / webhook: body_md
    return send_all(user_doc, channels, title, body_md, items, body_html=body_html, card=card)


def run_subscription_sync(sub: dict) -> dict:
    """同步入口,给 CLI 用"""
    return asyncio.run(run_subscription(sub))