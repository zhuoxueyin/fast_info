"""通用源抓取适配器 (Day 5)

每天跑 fetch_all 时,每源写一条 source_runs 记录,自动维护 source_config 健康状态,
连续失败 N 次自动禁用源 + 写禁用原因。

镜像 fallback:
  - huxiu → mirrors.HUXIU_RSS (多 URL 顺序试)
  - X     → mirrors.NITTER_MIRRORS (多 nitter 实例)
  - 微博  → weibo_openapi.WeiboClient (有 token 走 OpenAPI,否则 scrape)
"""
from __future__ import annotations
import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from .rss_collector import Item, _strip_html, _title_hash, _make_id, USER_AGENT
from .sources import RSS_SOURCES, KOL_SOURCES
from .mirrors import (
    get_huxiu_urls,
    get_nitter_mirrors,
    get_wallstreetcn_urls,
    get_cls_urls,
    get_zhihu_hot_urls,
)
from storage.source_config import load_enabled_sources
from storage.source_runs import record_source_run, _classify_error

# Day 6v2:热搜 JSON URL(单独放在这,KOL_SOURCES 里只有 (name, kind) 两个槽)
# 微博 m.weibo.cn container API 走 JSON 被风控 302 → 失效
# 改用头条公开 JSON 热点 (公开 API,无风控)
RSS_HOT_URLS = {
    "weibo_hot": (
        "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
    ),
}


# ============================================================
# 公开 API: RSS (多镜像)
# ============================================================

async def fetch_rss_with_fallback(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    urls: list[str],
    limit: int = 15,
) -> list[Item]:
    """Try each URL in order, return first non-empty result."""
    last_err: Optional[Exception] = None
    for u in urls:
        try:
            resp = await client.get(u, follow_redirects=True)
            resp.raise_for_status()
            items = _parse_rss(resp.text, source_id, name, u, limit)
            if items:
                return items
            last_err = ValueError(f"empty feed ({u})")
        except Exception as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return []


async def fetch_rss(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    feed_url: str,
    limit: int = 15,
) -> list[Item]:
    """Legacy single-URL entry. New code: fetch_rss_with_fallback."""
    return await fetch_rss_with_fallback(client, source_id, name, [feed_url], limit)


def _parse_rss(text: str, source_id: str, name: str, feed_url: str, limit: int) -> list[Item]:
    feed = feedparser.parse(text)
    if feed.bozo and not feed.entries:
        return []
    items: list[Item] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for entry in feed.entries[:limit]:
        url = entry.get("link") or entry.get("id") or ""
        title = _strip_html(entry.get("title", "")).strip()
        if not url or not title:
            continue
        items.append(Item(
            id=_make_id(source_id, url),
            source=source_id,
            source_url=feed_url,
            url=url,
            title=title,
            title_hash=_title_hash(title),
            summary_html=_strip_html(entry.get("summary", "")),
            content_html="",
            published_at=_parse_published(entry),
            fetched_at=fetched_at,
            author=entry.get("author"),
            tags=[t.get("term", "") for t in entry.get("tags", []) if t.get("term")],
        ))
    return items


def _parse_published(entry) -> Optional[str]:
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                continue
    return None


# ============================================================
# 公开 API: KOL
# ============================================================

async def fetch_weibo_user(
    client: httpx.AsyncClient,
    uid: str,
    name: str,
    limit: int = 10,
    platform_config: Optional[dict] = None,
) -> list[Item]:
    from .weibo_openapi import make_weibo_client
    wb = make_weibo_client(platform_config or {})
    return await wb.fetch_user_timeline(client, uid, name, limit)


async def fetch_x_user_multi(
    client: httpx.AsyncClient,
    handle: str,
    name: str,
    limit: int = 10,
) -> list[Item]:
    """Try nitter mirrors in order. First non-empty wins."""
    mirrors = get_nitter_mirrors()
    last_err: Optional[Exception] = None
    for m in mirrors:
        url = f"{m}/{handle}/rss"
        try:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                items = _parse_rss(resp.text, f"x:{handle}", name, url, limit)
                if items:
                    return items
            last_err = ValueError(f"{m} status={resp.status_code}")
        except Exception as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return []


async def fetch_x_user(
    client: httpx.AsyncClient,
    handle: str,
    name: str,
    limit: int = 10,
) -> list[Item]:
    """Legacy single-mirror; routes to multi-mirror."""
    return await fetch_x_user_multi(client, handle, name, limit)


async def fetch_xhs_note(
    client: httpx.AsyncClient,
    uid: str,
    name: str,
    limit: int = 5,
    platform_config: Optional[dict] = None,
) -> list[Item]:
    """Day 5: Phase 4 升级前的占位。
    xhs: demo 已从 KOL_SOURCES 移除;Phase 4 接 Apify / 自签后再启用。
    返回 0 条 stub;触发 source_runs EMPTY_FEED。
    """
    return []


# ============================================================
# Day 6v2 新增:JSON 热搜源 fetcher
# ============================================================
# bilibili 官方排行 JSON + 微博热搜 JSON,不走 RSS 解析
# 输入是 RSS_SOURCES / KOL_SOURCES 注册表里的 JSON URL

async def fetch_bilibili_hot(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    feed_url: str,
    limit: int = 15,
) -> list[Item]:
    """Day 6v2:bilibili 官方排行 JSON。
    原 RSS 端点 /ranking/rss/all/rank/0/3/7 已 empty feed,改为 JSON。
    response.data.list[].{title, href, pic, hot, duration, ...}
    注意:B 站对裸请求 code=-352 风控,必须带 Referer + 真实浏览器 UA + web_location 白名单参数。
    内置 3 个 endpoint fallback:ranking/v2 (白名单) → popular → popular 全分类。
    """
    from datetime import datetime, timezone
    from crawler.rss_collector import Item, _strip_html, _title_hash, _make_id
    fetched_at = datetime.now(timezone.utc).isoformat()
    # B 站风控:Referer + 真实 Chrome UA 必填(默认 fastInfo UA 被风控 -352)
    headers = {
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    # 3 个 endpoint 逐个试,任一返回数据即用
    urls = [
        feed_url,                                                   # 主:ranking/v2 with web_location
        "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1",  # 备 1:popular 热门
    ]
    last_err: Optional[Exception] = None
    for u in urls:
        try:
            resp = await client.get(u, headers=headers, timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict) or payload.get("code") != 0:
                raise ValueError(f"bilibili API non-ok: code={payload.get('code') if isinstance(payload, dict) else '?'} msg={payload.get('message', '?')[:80]}")
            lst = ((payload.get("data") or {}).get("list") or [])
            if lst:
                # 成功,break
                feed_url = u
                break
            last_err = ValueError(f"empty list from {u}")
        except Exception as e:
            last_err = e
            continue
    else:
        # 所有 url 都 fail
        if last_err:
            raise last_err
        return []
    # 现在 lst 是成功的那个 endpoint 的列表
    items: list[Item] = []
    for i, row in enumerate(lst[:limit]):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        # B 站 row 没 link/arcurl 字段,从 bvid/short_link_v2 拼
        bvid = row.get("bvid") or ""
        short = row.get("short_link_v2") or ""
        url = short or (f"https://www.bilibili.com/video/{bvid}" if bvid else "")
        if not url:
            continue
        owner = row.get("owner") or {}
        author = (owner.get("name") if isinstance(owner, dict) else "") or row.get("author") or ""
        stat = row.get("stat") or {}
        hot_score = stat.get("view") or stat.get("like") or 0
        tags = ["bilibili_hot", "ranking"]
        summary = _strip_html(row.get("desc") or row.get("dynamic") or "")
        if hot_score:
            summary = (summary + f" | 播放:{hot_score}").strip(" |")
        items.append(Item(
            id=_make_id(source_id, bvid or url),
            source=source_id,
            source_url=feed_url,
            url=url,
            title=f"[B站#{i+1}] {title}",
            title_hash=_title_hash(title),
            summary_html=summary,
            content_html="",
            published_at=None,
            fetched_at=fetched_at,
            author=author or None,
            tags=tags,
        ))
    return items


async def fetch_weibo_hot(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    feed_url: str,
    limit: int = 15,
) -> list[Item]:
    """Day 6v2:微博热搜词热榜 — 实测走头条公开 JSON 热点 API。
    原 m.weibo.cn container API 被风控 302,改用 toutiao.com/hot-event/hot-board 公开 JSON。
    response.data[].{Title, Url, HotValue, QueryWord}
    """
    import json as _json
    from datetime import datetime, timezone
    from crawler.rss_collector import Item, _strip_html, _title_hash, _make_id
    fetched_at = datetime.now(timezone.utc).isoformat()
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.toutiao.com/",
        "Accept": "application/json, text/plain, */*",
    }
    resp = await client.get(feed_url, headers=headers, timeout=10.0)
    resp.raise_for_status()
    text = resp.text
    payload = _json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"hot API non-dict payload: {str(payload)[:80]}")
    # 头条格式可能是 {data: [...]} 或顶层是 list
    if isinstance(payload.get("data"), list):
        lst = payload["data"]
    elif isinstance(payload, list):
        lst = payload
    else:
        lst = []
    items: list[Item] = []
    for i, row in enumerate(lst[:limit]):
        title = (row.get("Title") or row.get("title") or row.get("word") or row.get("query") or "").strip()
        url = row.get("Url") or row.get("url") or row.get("scheme") or ""
        if not title:
            continue
        if not url:
            url = f"https://www.toutiao.com/search/?keyword={title}"
        hot = row.get("HotValue") or row.get("hot") or row.get("score") or 0
        summary = ""
        if hot:
            summary = f"热度:{hot}"
        items.append(Item(
            id=_make_id(source_id, url or title),
            source=source_id,
            source_url=feed_url,
            url=url,
            title=f"[热搜#{i+1}] {title}",
            title_hash=_title_hash(title),
            summary_html=summary,
            content_html="",
            published_at=None,
            fetched_at=fetched_at,
            author=None,
            tags=["weibo_hot", "hot_ranking"],
        ))
    return items


async def fetch_cls_home(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    feed_url: str,
    limit: int = 15,
) -> list[Item]:
    """Day 11:cls 财联社 — 抓主页 SSR 内嵌的 hotArticleData JSON。

    背景:cls 官方 nodeapi 接口 418,公共 RSSHub 镜像(2026-07-05)全 503/404。
    主页 HTML 是 Next.js SSR,window.__INITIAL_STATE__ 里嵌了 hotArticleData:
        [{id, title, brief, ctime, readNum, author, img, ...}, ...]
    含当日热门电报,字段足够做 LLM 摘要输入源。
    """
    import json as _json
    import re as _re
    from datetime import datetime, timezone
    from crawler.rss_collector import Item, _strip_html, _title_hash, _make_id
    fetched_at = datetime.now(timezone.utc).isoformat()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = await client.get(feed_url, headers=headers, timeout=15.0)
    resp.raise_for_status()
    html = resp.text
    # 主页 __INITIAL_STATE__ 里 hotArticleData 是 JSON 数组字符串,中文是 raw UTF-8 字符,
    # 只有 \n \" 等 JSON 标准转义需要处理。直接 json.loads(strict=False 容错 raw 控制符)。
    m = _re.search(r'"hotArticleData"\s*:\s*(\[(?:[^[\]]|\[[^\]]*\])*\])', html)
    if not m:
        raise ValueError("cls home: hotArticleData not found in HTML")
    raw = m.group(1)
    try:
        arr = _json.loads(raw, strict=False)
    except Exception as e:
        raise ValueError(f"cls home: hotArticleData JSON parse failed: {e}")
    if not isinstance(arr, list):
        raise ValueError(f"cls home: hotArticleData is not list: {type(arr).__name__}")
    items: list[Item] = []
    for i, row in enumerate(arr[:limit]):
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or "").strip()
        if not title:
            continue
        aid = row.get("id") or ""
        url = f"https://www.cls.cn/detail/{aid}" if aid else (row.get("share_url") or feed_url)
        brief = _strip_html(row.get("brief") or "")
        read_num = row.get("readNum") or 0
        ctime = row.get("ctime")
        # 拼摘要:brief + readNum(读数做 hot ranking 提示)
        summary = brief
        if read_num:
            summary = (brief + f" | 阅读:{read_num}").strip(" |")
        # ctime 是 unix 秒
        published_at = None
        if ctime:
            try:
                dt = datetime.fromtimestamp(int(ctime), tz=timezone.utc)
                published_at = dt.isoformat()
            except Exception:
                pass
        author = (row.get("author") or "").strip() or None
        items.append(Item(
            id=_make_id(source_id, url or str(aid) or title),
            source=source_id,
            source_url=feed_url,
            url=url,
            title=title,
            title_hash=_title_hash(title),
            summary_html=summary,
            content_html="",
            published_at=published_at,
            fetched_at=fetched_at,
            author=author,
            tags=["cls_hot", "hot_ranking"],
        ))
    return items


# ============================================================
# Per-source run wrapper + 统一入口
# ============================================================

async def _run_one_source(source_id: str, fetcher, *, enabled: bool, task_run_id: Optional[str] = None) -> list[Item]:
    """
    跑一个源,失败/成功记 source_runs,自动禁用按 source_config.auto_disable_threshold。
    task_run_id: 关联的 task_runs.run_id(用于调用树跟踪)
    """
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    status = "fail"
    error_code: Optional[str] = None
    error_msg: Optional[str] = None
    items: list[Item] = []

    if not enabled:
        duration = int((time.monotonic() - t0) * 1000)
        record_source_run(
            source_id=source_id, status="disabled",
            started_at=started, duration_ms=duration,
            error_code="DISABLED", error_msg="is_active=False",
            task_run_id=task_run_id,
        )
        return []

    try:
        items = await fetcher()
        fetched = len(items)
        if fetched > 0:
            status = "ok"
        else:
            status = "partial"
            error_code = "EMPTY_FEED"
            error_msg = "fetcher returned empty list"
    except Exception as e:
        status = "fail"
        error_code = _classify_error(e)
        error_msg = f"{type(e).__name__}: {str(e)[:200]}"

    duration = int((time.monotonic() - t0) * 1000)
    record_source_run(
        source_id=source_id, status=status,
        started_at=started, duration_ms=duration,
        fetched_count=len(items),
        error_code=error_code, error_msg=error_msg,
        task_run_id=task_run_id,
    )
    return items


async def fetch_all(limit_per_source: int = 15, enabled_sources: Optional[set[str]] = None, task_run_id: Optional[str] = None) -> list[Item]:
    """
    全源抓取。顺序跑(每源间隔独立 source_runs 记录)。
    30 min 一次,18 个源顺序跑大概 30-60s,可以接受。
    task_run_id: 关联的 task_runs.run_id(用于调用树跟踪)
    """
    active = enabled_sources
    if active is None:
        loaded = load_enabled_sources()
        active = loaded  # None 表示全启用 / 历史 fallback

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=8.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
    ) as client:
        all_items: list[Item] = []

        # === RSS ===
        for sid, (name, url) in RSS_SOURCES.items():
            enabled = (active is None) or (sid in active)
            # Day 6v2:bilibili 走 JSON fetcher (RSS 端点已废)
            if sid == "bilibili":
                async def _run():
                    return await fetch_bilibili_hot(client, sid, name, url, limit_per_source)
                items = await _run_one_source(sid, _run, enabled=enabled, task_run_id=task_run_id)
            elif sid == "cls":
                # Day 11:cls 改走主页 hotArticleData JSON(SSR 内嵌,稳定可用)
                async def _run():
                    return await fetch_cls_home(client, sid, name, url, limit_per_source)
                items = await _run_one_source(sid, _run, enabled=enabled, task_run_id=task_run_id)
            else:
                # Day 6v2:走 RSSHub 多镜像的源
                if sid == "huxiu":
                    urls = get_huxiu_urls()
                elif sid == "wallstreetcn":
                    urls = get_wallstreetcn_urls()
                elif sid == "zhihu_hot":
                    urls = get_zhihu_hot_urls()
                else:
                    urls = [url]
                async def _run():
                    return await fetch_rss_with_fallback(client, sid, name, urls, limit_per_source)
                items = await _run_one_source(sid, _run, enabled=enabled, task_run_id=task_run_id)
            all_items.extend(items)

        # === KOL ===
        for key, (name, kind) in KOL_SOURCES.items():
            enabled = (active is None) or (key in active)
            _, real_id = key.split(":", 1)
            if kind == "weibo_user":
                async def _run():
                    return await fetch_weibo_user(client, real_id, name, 5)
                items = await _run_one_source(key, _run, enabled=enabled, task_run_id=task_run_id)
            elif kind == "weibo_hot":
                # Day 6v2 新增:微博热搜走 JSON fetcher
                url = RSS_HOT_URLS.get("weibo_hot", "")
                async def _run():
                    return await fetch_weibo_hot(client, key, name, url, 20)
                items = await _run_one_source(key, _run, enabled=enabled, task_run_id=task_run_id)
            elif kind == "x_user":
                async def _run():
                    return await fetch_x_user_multi(client, real_id, name, 5)
                items = await _run_one_source(key, _run, enabled=enabled, task_run_id=task_run_id)
            elif kind == "xhs_note":
                async def _run():
                    return await fetch_xhs_note(client, real_id, name, 5)
                items = await _run_one_source(key, _run, enabled=enabled, task_run_id=task_run_id)
            else:
                continue
            all_items.extend(items)

        return all_items


# ============================================================
# Day 10.5: 单源抓取(给调度器 daemon 用,取代全量 fetch_all)
# ============================================================

async def fetch_one_source(
    source_id: str,
    limit: int = 15,
    task_run_id: Optional[str] = None,
) -> list[Item]:
    """按 source_id 抓一个源。

    - RSS_SOURCES → 走 RSS 路径(支持 huxiu/wallstreetcn/cls/zhihu_hot 多镜像, bilibili 走 JSON)
    - KOL_SOURCES  → 按 kind 分发(weibo_user/x_user/weibo_hot/xhs_note)
    - source_runs 记录由 _run_one_source 内部完成

    返回 Item 列表(原始抓取,未去重);失败/禁用由 _run_one_source 写 source_runs 并 raise 或返 []。
    """
    from storage.source_config import get_source

    cfg = get_source(source_id)
    if not cfg:
        # 兜底:从 RSS_SOURCES / KOL_SOURCES 找(防 source_config 漏 seed)
        if source_id in RSS_SOURCES:
            cfg = {"source_id": source_id, "kind": "rss",
                   "display_name": RSS_SOURCES[source_id][0],
                   "url": RSS_SOURCES[source_id][1], "urls": [RSS_SOURCES[source_id][1]],
                   "limit_per_run": limit, "is_active": True}
        elif source_id in KOL_SOURCES:
            name, kind = KOL_SOURCES[source_id]
            cfg = {"source_id": source_id, "kind": kind, "display_name": name,
                   "limit_per_run": 5, "is_active": True}
        else:
            raise ValueError(f"unknown source_id: {source_id}")

    kind = cfg.get("kind", "rss")
    display = cfg.get("display_name", source_id)
    is_active = bool(cfg.get("is_active", True))
    lim = int(cfg.get("limit_per_run") or limit)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=8.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
    ) as client:
        async def _run():
            if kind == "rss":
                if source_id == "bilibili":
                    url = cfg.get("url") or RSS_SOURCES.get(source_id, ("", ""))[1]
                    return await fetch_bilibili_hot(client, source_id, display, url, lim)
                if source_id == "huxiu":
                    urls = get_huxiu_urls()
                elif source_id == "wallstreetcn":
                    urls = get_wallstreetcn_urls()
                elif source_id == "cls":
                    urls = get_cls_urls()
                elif source_id == "zhihu_hot":
                    urls = get_zhihu_hot_urls()
                else:
                    urls = cfg.get("urls") or ([cfg["url"]] if cfg.get("url") else [])
                return await fetch_rss_with_fallback(client, source_id, display, urls, lim)
            elif kind == "weibo_user":
                _, real_id = source_id.split(":", 1)
                return await fetch_weibo_user(client, real_id, display, lim, cfg.get("platform_config"))
            elif kind == "weibo_hot":
                url = RSS_HOT_URLS.get("weibo_hot", "")
                return await fetch_weibo_hot(client, source_id, display, url, lim)
            elif kind == "x_user":
                _, handle = source_id.split(":", 1)
                return await fetch_x_user_multi(client, handle, display, lim)
            elif kind == "xhs_note":
                _, uid = source_id.split(":", 1)
                return await fetch_xhs_note(client, uid, display, lim, cfg.get("platform_config"))
            else:
                raise ValueError(f"unsupported kind: {kind}")

        return await _run_one_source(source_id, _run, enabled=is_active, task_run_id=task_run_id)


# ============================================================
# Backward compat (旧 API 别名,避免 break 老代码)
# ============================================================

def load_enabled_sources_legacy() -> Optional[set[str]]:
    """旧 API: 从 global doc 读 enabled 列表。
    已被 source_config.load_enabled_sources() 取代,这里仅作 keep-import 桥接。"""
    try:
        from storage.mongo_writer import get_db
        db = get_db()
        docs = list(db["source_config"].find({"is_active": True}))
        if docs:
            return {d["source_id"] for d in docs}
        cfg = db["source_config"].find_one({"_id": "global"})
        if not cfg:
            return None
        enabled = cfg.get("enabled")
        if enabled is None:
            return None
        return set(enabled)
    except Exception:
        return None


def save_enabled_sources_legacy(enabled: list[str]) -> None:
    """旧 API: 写 enabled 到 global doc。新代码不应再调用。"""
    from storage.mongo_writer import get_db
    db = get_db()
    db["source_config"].update_one(
        {"_id": "global"},
        {"$set": {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


# Old function name alias — 已被新版本替代但保留入口
load_enabled_sources = load_enabled_sources_legacy
save_enabled_sources = save_enabled_sources_legacy
