"""临时话题 / 雷达 · 实体优先检索

问题根因(实测「王力宏」):
  旧逻辑把 LLM 扩展出的泛词(歌手/明星/音乐人)和实体名一起 $or,
  再按 fetched_at 截 topN → 最新的无关娱乐新闻占满名额,实体真相关被挤掉。

策略:
  1. 抽出 **core 实体词**(硬门槛): track_entity / nl 原文 / 与实体相关的 keyword
  2. 丢掉噪音泛词(明星/动态/最新…)
  3. Mongo 只按 core 做 $or(title|summary),类目只作软加分不硬滤
  4. 内存打分排序: 标题全命中 > 标题命中数 > 摘要命中 > 相关度 > 新鲜度
  5. 标题近似去重
  6. 命中不足时自动放宽时间窗(48h → 7d → 30d)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from storage.mongo_writer import get_db

# 不能当硬匹配的泛词 / 修饰
_NOISE_TERMS = {
    "歌手", "音乐人", "明星", "艺人", "演员", "偶像", "名人", "网红",
    "动态", "最新", "新闻", "资讯", "消息", "相关", "事件", "热点",
    "关注", "跟踪", "订阅", "更新", "速递", "日报", "早报", "简报",
    "娱乐", "科技", "财经", "体育", "汽车", "其他", "ai",
    "star", "singer", "celebrity", "actor", "actress", "idol",
    "news", "latest", "update", "updates", "daily", "hot",
    "music", "entertainment", "artist", "artists",
}

# 中文连续词 / 英文词
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9._-]{1,}")


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _is_noise(term: str) -> bool:
    t = _norm(term)
    if not t or len(t) < 2:
        return True
    if t in _NOISE_TERMS:
        return True
    # 纯数字
    if t.isdigit():
        return True
    return False


def extract_core_terms(nl_query: str, parsed: Optional[dict] = None) -> list[str]:
    """抽出必须命中的实体词(去重保序)。"""
    parsed = parsed or {}
    raw: list[str] = []

    entity = (parsed.get("track_entity") or "").strip()
    if entity:
        raw.append(entity)

    nl = (nl_query or "").strip()
    if nl:
        raw.append(nl)
        raw.extend(_TOKEN_RE.findall(nl))

    title = (parsed.get("title") or "").strip()
    if title:
        # 标题常带「动态」「最新」等,先剥再切
        title_clean = re.sub(
            r"(动态|最新|新闻|资讯|跟踪|关注|相关|速递)$",
            "",
            title,
        ).strip()
        if title_clean:
            raw.append(title_clean)
            raw.extend(_TOKEN_RE.findall(title_clean))

    keywords = parsed.get("keywords") or []
    # 先收集候选 entity 串,用于判断 keyword 是否相关
    seed = {_norm(x) for x in raw if x and not _is_noise(x)}

    for kw in keywords:
        k = (kw or "").strip()
        if not k or _is_noise(k):
            continue
        kn = _norm(k)
        # 与 nl/entity 有包含关系 → 认为是别名/扩展
        related = False
        for s in seed:
            if not s:
                continue
            if s in kn or kn in s:
                related = True
                break
        if related or not seed:
            raw.append(k)

    # 去噪 + 去重(保序);优先更长的实体(避免单字)
    seen: set[str] = set()
    out: list[str] = []
    for t in sorted(
        [x.strip() for x in raw if x and not _is_noise(x)],
        key=lambda x: (-len(x), x),
    ):
        key = _norm(t)
        if key in seen:
            continue
        # 被已有更长词完全覆盖的短词跳过? 保留别名(Leehom vs 王力宏)都要
        seen.add(key)
        out.append(t)

    # 若只剩噪音,退回 nl 全串
    if not out and nl and not _is_noise(nl):
        out = [nl]
    return out[:8]


def _escape_regex(s: str) -> str:
    return re.escape(s)


def _item_text(item: dict) -> tuple[str, str, str]:
    title = item.get("title") or ""
    title_zh = item.get("title_zh") or ""
    summary = item.get("summary") or ""
    summary_zh = item.get("summary_zh") or ""
    # 标题优先中文翻译
    t = f"{title} {title_zh}".strip()
    s = f"{summary} {summary_zh}".strip()
    return t, s, f"{t} {s}".lower()


def _score_item(item: dict, core_terms: list[str], now: datetime, hours: int) -> float:
    title, summary, blob = _item_text(item)
    title_l = title.lower()
    summary_l = summary.lower()

    score = 0.0
    title_hits = 0
    summary_hits = 0
    for term in core_terms:
        tl = term.lower()
        if tl in title_l:
            title_hits += 1
            # 标题全等 / 标题开头加权
            if title_l.strip() == tl or title_l.startswith(tl):
                score += 8.0
            else:
                score += 5.0
        elif tl in summary_l:
            summary_hits += 1
            score += 1.5

    if title_hits == 0 and summary_hits == 0:
        return -1.0  # 不应出现(硬过滤后)

    # 多词命中加成
    score += 1.2 * max(0, title_hits - 1)
    score += 0.3 * max(0, summary_hits - 1)

    # 原始 relevance
    try:
        score += 0.8 * float(item.get("relevance") or 0)
    except (TypeError, ValueError):
        pass

    # 新鲜度 0~1.5
    try:
        fa = item.get("fetched_at") or item.get("published_at") or ""
        if isinstance(fa, datetime):
            fetched = fa if fa.tzinfo else fa.replace(tzinfo=timezone.utc)
        else:
            fetched = datetime.fromisoformat(str(fa).replace("Z", "+00:00"))
        age_h = max(0.0, (now - fetched).total_seconds() / 3600.0)
        score += 1.5 * max(0.0, 1.0 - age_h / float(max(hours, 1)))
    except Exception:
        pass

    return score


def _title_dedupe_key(title: str) -> str:
    t = re.sub(r"\s+", "", title or "")
    t = re.sub(r"[^\w\u4e00-\u9fff]", "", t)
    return t[:24]


def search_items_for_topic(
    *,
    nl_query: str,
    parsed: dict,
    max_items: int = 12,
    hours: int = 48,
    sources: Optional[list[str]] = None,
) -> tuple[list[dict], dict]:
    """检索临时话题关联 items。

    Returns:
        (items, debug_meta)
        debug_meta: {core_terms, hours_used, scanned, matched_before_dedupe}
    """
    db = get_db()
    core = extract_core_terms(nl_query, parsed)
    srcs = sources if sources is not None else (parsed.get("sources") or ["all"])
    max_items = max(1, min(int(max_items or 12), 50))

    # 递进放宽时间窗
    windows = []
    base = max(1, int(hours or 48))
    for h in (base, max(base, 24 * 7), max(base, 24 * 30)):
        if h not in windows:
            windows.append(h)

    now = datetime.now(timezone.utc)
    meta = {
        "core_terms": core,
        "hours_used": base,
        "scanned": 0,
        "matched_before_dedupe": 0,
    }

    if not core:
        # 无实体可硬匹配:退回类目+时间(弱模式),最多给一点结果
        return _weak_category_fallback(db, parsed, max_items, base, srcs, now, meta)

    # 硬条件:至少命中一个 core term
    or_clauses = []
    for term in core:
        rx = _escape_regex(term)
        or_clauses.append({"title": {"$regex": rx, "$options": "i"}})
        or_clauses.append({"summary": {"$regex": rx, "$options": "i"}})
        or_clauses.append({"title_zh": {"$regex": rx, "$options": "i"}})
        or_clauses.append({"summary_zh": {"$regex": rx, "$options": "i"}})

    best: list[dict] = []
    for win in windows:
        since = (now - timedelta(hours=win)).isoformat()
        q: dict = {
            "fetched_at": {"$gte": since},
            "$or": or_clauses,
        }
        if srcs and "all" not in srcs:
            q["source"] = {"$in": list(srcs)}

        # 多取一些再打分/去重
        cursor = db["items"].find(q).sort("fetched_at", -1).limit(max(max_items * 15, 80))
        rows = list(cursor)
        meta["scanned"] = len(rows)
        meta["hours_used"] = win

        scored: list[tuple[float, dict]] = []
        for it in rows:
            sc = _score_item(it, core, now, win)
            if sc < 0:
                continue
            # 类目软加分:与 parsed L1 一致 +0.4
            cats = parsed.get("categories_l1") or []
            l1 = it.get("category_l1") or it.get("category") or ""
            if cats and l1 in cats:
                sc += 0.4
            scored.append((sc, it))

        scored.sort(key=lambda x: x[0], reverse=True)
        meta["matched_before_dedupe"] = len(scored)

        # 标题去重
        seen: set[str] = set()
        out: list[dict] = []
        for sc, it in scored:
            key = _title_dedupe_key(it.get("title") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            # 写回排序分,方便前端调试
            it = dict(it)
            it["_topic_score"] = round(sc, 3)
            out.append(it)
            if len(out) >= max_items:
                break

        best = out
        # 命中够用就停;太少则放宽时间窗
        if len(best) >= min(max_items, 5) or len(best) >= max_items:
            break

    return best, meta


def _weak_category_fallback(db, parsed, max_items, hours, sources, now, meta) -> tuple[list[dict], dict]:
    """无 core term 时的弱兜底:只按类目+时间,相关度排序(宁缺勿滥,limit 收紧)。"""
    since = (now - timedelta(hours=hours)).isoformat()
    q: dict = {"fetched_at": {"$gte": since}}
    cats = parsed.get("categories_l1") or []
    if cats:
        q["$or"] = [
            {"category_l1": {"$in": cats}},
            {"category": {"$in": cats}},
        ]
    if sources and "all" not in sources:
        q["source"] = {"$in": list(sources)}
    rows = list(db["items"].find(q).sort([("relevance", -1), ("fetched_at", -1)]).limit(max_items))
    meta["hours_used"] = hours
    meta["scanned"] = len(rows)
    meta["matched_before_dedupe"] = len(rows)
    meta["weak_fallback"] = True
    return rows[: max(1, max_items // 2)], meta
