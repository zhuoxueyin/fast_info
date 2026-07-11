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

from storage.mongo_writer import get_sync_client, get_async_client, upsert_item_async, DEFAULT_DB
from llm.model_registry import build_default_registry


# 注意(原 P2 违规):早期版本这里硬编码了 DEFAULT_DB = "fastinfo",
# 会跟 docker 里 MONGO_DB=fastinfo_docker 错位 → 订阅读不到 items。
# 已改为跟 mongo_writer 共享同一份 DEFAULT_DB,任何环境(Docker / 本地 / ECS)自动跟随。


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


def compute_next_run_at(sub: dict, now: Optional[datetime] = None) -> datetime:
    """统一计算下一次触发时间。

    规则:
    - `interval_min > 0` 时,严格按分钟间隔顺延
    - 否则按 `cron_expr` 计算下一个命中时间
    """
    now = now or datetime.now(timezone.utc)
    interval_min = int(sub.get("interval_min", 0) or 0)
    if interval_min > 0:
        return now + timedelta(minutes=interval_min)
    cron_expr = (sub.get("cron_expr") or "0 9 * * *").strip()
    return _next_run_simple(cron_expr, now)


# ============================================================
# NL → Subscription
# ============================================================

async def parse_nl_to_subscription(
    nl_query: str,
    user_id: Optional[str] = None,
    track_mode: str = "long",
    duration_days: Optional[int] = None,
) -> dict:
    """
    把自然语言订阅描述解析成结构化 Subscription。

    用 nl_parse 模型组(M3 thinking 模式)。
    user_id 不传则从当前 CLI session 取(自动 by 用户)。
    track_mode: 'long' (默认,长期订阅) / 'short' (短期,带 expires_at)
    duration_days: 短期订阅天数(track_mode='short' 时生效,默认 7)
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
                "  interval_min: 自定义间隔分钟;0=用 cron\n"
                "  track_entity: 事件/人物/主题实体名(如果能从描述中识别出具体人物/事件/赛事/发布会等,如 '王力宏'、'世界杯'、'GTC 2026'),用于二次精准跟踪;无法识别时输出 null\n\n"
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
            "track_entity": None,
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
    parsed.setdefault("track_entity", None)
    # 清理 track_entity:null/空串 → None
    if not parsed["track_entity"]:
        parsed["track_entity"] = None

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
        "feishu_targets": [],  # 订阅实例维度;创建 API 可覆盖
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
        # Day 9:短期跟踪元数据
        "track_mode": track_mode,
        "track_entity": parsed.get("track_entity"),
    }
    # 短期跟踪:加 expires_at + 缩短 cron
    if track_mode == "short":
        d = duration_days if duration_days and duration_days > 0 else 7
        sub["expires_at"] = (now + timedelta(days=d)).isoformat()
        sub["duration_days"] = d
        # 短期订阅:每 6 小时一次,事件类热点更及时
        sub["cron_expr"] = "0 */6 * * *"
        sub["next_run_at"] = _next_run_simple(sub["cron_expr"], now).isoformat()
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
    now = datetime.now(timezone.utc)
    next_run = compute_next_run_at(sub, now)
    update: dict = {
        "last_run_at": now.isoformat(),
        "next_run_at": next_run.isoformat(),
        "run_count": sub.get("run_count", 0) + 1,
        "updated_at": now.isoformat(),
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


async def run_subscription(sub: dict, *, trigger: str = "manual", operator: str = "auto") -> dict:
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
    require_all_keywords = bool(sub.get("require_all_keywords", False))

    # lookback 窗口: 订阅可自定义;否则按频率自动:
    #   interval/realtime → 跟 interval_min 一致(最少 1h)
    #   cron daily/weekly → 24h(只看今天的新内容,避免重复推昨天的)
    interval_min = int(sub.get("interval_min", 0) or 0)
    if "lookback_hours" in sub and sub["lookback_hours"]:
        lookback_hours = int(sub["lookback_hours"])
    elif interval_min > 0:
        lookback_hours = max(1, interval_min // 60)
    else:
        lookback_hours = 24

    db = get_async_client()[DEFAULT_DB]

    # channels: 订阅自身字段;空时尝试从 user.default_channels 兜底(Day 7 一致性)
    user_doc_for_channels: dict | None = None
    if not channels:
        from bson import ObjectId
        u = None
        try:
            u = await db["users"].find_one({"_id": ObjectId(user_id)})
        except Exception:
            u = None
        if u:
            user_doc_for_channels = dict(u)
            defaults = u.get("default_channels") or ["inbox"]
            try:
                from api.routes.settings import _available_channels, CHANNEL_FIELDS
                avail = _available_channels(dict(u))
                channels = [c for c in defaults if c in avail and c in CHANNEL_FIELDS]
            except Exception:
                channels = list(defaults)
            if not channels:
                channels = ["inbox"]
        else:
            channels = ["inbox"]

    # 1. 从 MongoDB 读最近 lookback_hours 小时的 items
    now_run = datetime.now(timezone.utc)
    since = (now_run - timedelta(hours=lookback_hours)).isoformat()
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

        # 排序权重: L2 软加权 + 新鲜度(越新越高)
        boost = 0.0
        if categories_l2 and cat_raw in categories_l2:
            boost += 0.15
        if categories and any(c in cat_raw for c in categories):
            boost += 0.1
        # 新鲜度: 距 now 的小时数，越小越新；转成 0~1 的衰减分
        try:
            fetched_at = datetime.fromisoformat(item.get("fetched_at", "").replace("Z", "+00:00"))
            age_hours = max(0.0, (now_run - fetched_at).total_seconds() / 3600.0)
        except Exception:
            age_hours = float(lookback_hours)
        # 24h 内 → 0.5~1.0, 48h 内 → 0~0.5; 保证新内容排在旧内容前面
        freshness = max(0.0, 1.0 - age_hours / float(lookback_hours))
        item["_boost"] = boost
        item["_freshness"] = freshness

        seen_ids.add(iid)
        candidates.append(item)
        if len(candidates) >= max_items * 3:
            break

    # 排序: 新鲜度优先 > L2 boost > relevance
    # freshness 放第一位保证最新内容优先被推
    candidates.sort(
        key=lambda x: (x.get("_freshness", 0), x.get("_boost", 0), x.get("relevance", 0)),
        reverse=True,
    )
    candidates = candidates[:max_items]

    if not candidates:
        return {"scanned": 0, "matched": 0, "delivered": 0, "skipped": "no matches"}

    # 2. 跳过已推送 + 同批 / 历史 title_hash 去重
    # 热搜源曾因 URL 追踪参数生成多条"假新 item"(同一话题不同 url_hash),
    # 仅靠 item_id 去重挡不住;用 title_hash 做内容级兜底。
    sub_id = str(sub.get("_id", ""))
    user_id = sub.get("user_id", "anonymous")
    delivered = db["subscriptions_delivered"]
    delivered_ids: set[str] = set()
    async for d in delivered.find({"subscription_id": sub_id}):
        delivered_ids.add(d["item_id"])

    delivered_title_hashes: set[str] = set()
    if delivered_ids:
        from bson import ObjectId
        oid_list = []
        for iid in delivered_ids:
            try:
                oid_list.append(ObjectId(iid))
            except Exception:
                pass
        if oid_list:
            async for it in db["items"].find(
                {"_id": {"$in": oid_list}, "title_hash": {"$exists": True, "$ne": ""}},
                {"title_hash": 1},
            ):
                delivered_title_hashes.add(it["title_hash"])

    new_items: list = []
    batch_title_hashes: set[str] = set()
    for it in candidates:
        iid = str(it.get("_id", ""))
        if iid in delivered_ids:
            continue
        th = (it.get("title_hash") or "").strip()
        if th and (th in delivered_title_hashes or th in batch_title_hashes):
            continue
        if th:
            batch_title_hashes.add(th)
        new_items.append(it)
        if len(new_items) >= max_items:
            break

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
    push_recorded = False
    if new_items:
        # 复用第 1 步拉过的 user_doc(避免重复 Mongo 查询)
        if user_doc_for_channels is None:
            user_doc = await _find_user_doc(db, user_id) or {}
        else:
            user_doc = user_doc_for_channels
        has_feishu = bool(user_doc.get('feishu_webhooks')) or bool(user_doc.get('feishu_webhook'))
        print(f"  [sub run] {sub_id[:8]} channels={channels} feishu={'***' if has_feishu else 'MISSING'} items={len(new_items)}")
        t0 = time.time()
        results = await _render_and_send(user_doc, sub, new_items, channels)
        duration_ms = int((time.time() - t0) * 1000)
        # Day 9:写 push_history(触发来源 + 渠道结果 + items)
        try:
            from storage.push_history import record_push
            await record_push(
                user_id=user_id,
                subscription_id=sub_id,
                subscription_title=sub.get("title", ""),
                trigger=trigger,
                operator=operator,
                channel_results=results,
                items=[
                    {
                        "item_id": str(it.get("_id", "")),
                        "title": it.get("title", ""),
                        "url": it.get("url", ""),
                        "source": it.get("source", ""),
                    }
                    for it in new_items
                ],
                duration_ms=duration_ms,
            )
            push_recorded = True
        except Exception as e:
            print(f"  [push_history] write failed (non-fatal): {e}")

    return {
        "scanned": max_items * 5,
        "matched": len(candidates),
        "delivered": len(new_items),
        "push_recorded": push_recorded,
        "trigger": trigger,
    }


def _user_doc_for_sub_send(user_doc: dict, sub: dict, channels: list[str]) -> dict:
    """按订阅实例裁剪推送目标。

    飞书:sub.feishu_targets 非空时,只推选定群;空则推用户已配置全部群。
    其它渠道仍走用户 settings 全局凭证(邮箱 / 企微 / webhook URL)。
    """
    send_user = dict(user_doc or {})
    if "feishu" not in channels:
        return send_user
    from notifier import get_feishu_webhooks
    all_hooks = get_feishu_webhooks(send_user)
    targets = sub.get("feishu_targets") or []
    if isinstance(targets, str):
        targets = [t.strip() for t in targets.split(",") if t.strip()]
    names = {str(t).strip() for t in targets if t}
    if names:
        selected = [h for h in all_hooks if h.get("name") in names]
        # 指定了目标但一个都匹配不上 → 空列表,FeishuNotifier 会报 no webhook
        send_user["feishu_webhooks"] = selected
        send_user["feishu_webhook"] = ""
    else:
        # 未指定 → 全部已配置群
        send_user["feishu_webhooks"] = all_hooks
        send_user["feishu_webhook"] = ""
    return send_user


async def _render_and_send(user_doc: dict, sub: dict, items: list, channels: list[str]) -> dict:
    """Day 9:返回 {channel: {ok, http_status, error}} 让 push_history 能落库。

    Day 7:send_all 第 4 位是 content_html(给 email 用),我们把 HTML 放 keyword
    body_html=，feishu/wechat/webhook 用 keyword body_md=，feishu interactive
    用 keyword card=。第 4 位显式传空字符串,避免把 markdown 误填给 content_html。

    Day 9 修复 inbox:
    "inbox" 不在 notifier 注册表里(它是 Mongo subscriptions_delivered 实现),
    send_all 看到 inbox 会返 unknown。手工把它映射为 ok(因为 items 已经写过 Mongo,
    = inbox 已经"送达")。

    Day 13:飞书按订阅实例 feishu_targets 过滤群。
    """
    from notifier import send_all
    from .format_push import format_html, format_markdown, format_feishu_card, inbox_url_for
    site_base = os.environ.get("FASTINFO_SITE_BASE", "")
    inbox_url = inbox_url_for(site_base)
    title = f"[fastInfo] {sub.get('title', '订阅')} · {len(items)} 条新内容"
    body_html  = format_html(sub, items, inbox_url)
    body_md    = format_markdown(sub, items, inbox_url)
    card       = format_feishu_card(sub, items, inbox_url)

    send_user = _user_doc_for_sub_send(user_doc, sub, channels)

    # 拆分 inbox 和 其他 notifier 渠道
    notifier_channels = [c for c in channels if c != "inbox"]
    results = send_all(
        send_user, notifier_channels, title, "",          # content_html = ""(走 keyword)
        items,
        body_md=body_md, body_html=body_html, card=card,
    )
    # inbox 渠道的成功判定:items 已写入 subscriptions_delivered 集合
    # (外层 run_subscription 已经做完),所以这里无条件 ok
    if "inbox" in channels:
        results["inbox"] = {"ok": True, "http_status": None, "error": None}
    return results


def run_subscription_sync(sub: dict, *, trigger: str = "cli", operator: str = "cli") -> dict:
    """同步入口,给 CLI 用"""
    return asyncio.run(run_subscription(sub, trigger=trigger, operator=operator))
