"""通用源抓取适配器(Day 4)

把 RSS / 隐藏 RSS / KOL 公开页 全部包装成统一 fetch_source()。
被 ingest_daemon.py 调用。
"""
from __future__ import annotations
import asyncio
import re
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from .rss_collector import (
    Item,
    _strip_html,
    _normalize_title,
    _title_hash,
    _make_id,
    USER_AGENT,
)
from .sources import RSS_SOURCES, KOL_SOURCES


# ============================================================
# RSS 抓取(已有,稍微加重试)
# ============================================================
async def fetch_rss(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    feed_url: str,
    limit: int = 15,
) -> list[Item]:
    """抓 RSS/Atom,失败重试 2 次"""
    for attempt in range(3):
        try:
            resp = await client.get(feed_url, follow_redirects=True)
            resp.raise_for_status()
            return _parse_rss(resp.text, source_id, name, feed_url, limit)
        except Exception as e:
            if attempt == 2:
                print(f"  ✗ [{source_id}] {type(e).__name__}: {str(e)[:80]}")
                return []
            await asyncio.sleep(2 ** attempt)
    return []


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
    print(f"  ✓ [{source_id}] {len(items)} 条")
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
# KOL 抓取 — 微博 / X / 小红书 (公开页 MVP)
# ============================================================
async def fetch_weibo_user(client: httpx.AsyncClient, uid: str, name: str, limit: int = 10) -> list[Item]:
    """
    微博用户时间线(公开页 scrape)。
    URL: https://m.weibo.cn/u/{uid}
    真实生产请用 Weibo OpenAPI: https://open.weibo.com/wiki/API
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    url = f"https://m.weibo.cn/u/{uid}"
    items: list[Item] = []
    try:
        resp = await client.get(url, headers={"Referer": "https://m.weibo.cn/"})
        resp.raise_for_status()
        # 找嵌入的 status JSON(简化:MVP 不解析,给个壳子)
        m = re.findall(r"\"text\":\\?\"([^\\]{30,200})\\?\"", resp.text)
        for txt in m[:limit]:
            txt = txt.replace("<br/>", "\n").replace("&nbsp;", " ")
            txt = re.sub(r"<[^>]+>", "", txt)[:140]
            item_url = f"{url}#{hash(txt)%10000}"
            title = txt.strip().split("\n")[0][:80]
            items.append(Item(
                id=_make_id(f"weibo:{uid}", item_url),
                source=f"weibo:{uid}",
                source_url=url,
                url=item_url,
                title=title,
                title_hash=_title_hash(title),
                summary_html=txt,
                content_html="",
                published_at=fetched_at,
                fetched_at=fetched_at,
                author=name,
                tags=["微博"],
            ))
        print(f"  ✓ [weibo:{name}] {len(items)} 条")
    except Exception as e:
        print(f"  ✗ [weibo:{name}] {type(e).__name__}: {str(e)[:80]}")
    return items


async def fetch_x_user(client: httpx.AsyncClient, handle: str, name: str, limit: int = 10) -> list[Item]:
    """
    X / Twitter 用户推文 — 走 nitter.net RSS 镜像(无需 API Key)。
    镜像地址可能不稳,生产请用 X API v2 Basic ($100/月)。
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    url = f"https://nitter.net/{handle}/rss"
    items: list[Item] = []
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            print(f"  ✗ [x:{name}] nitter 不可达({resp.status_code})")
            return []
        items = _parse_rss(resp.text, f"x:{handle}", name, url, limit)
    except Exception as e:
        print(f"  ✗ [x:{name}] {type(e).__name__}: {str(e)[:80]}")
    return items


async def fetch_xhs_note(client: httpx.AsyncClient, uid: str, name: str, limit: int = 10) -> list[Item]:
    """
    小红书用户笔记 — 公开页 scrape(MVP 演示)。
    真实生产:小红书开放平台 / 第三方 API (需签名,成本 ~$0.001/条)
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    url = f"https://www.xiaohongshu.com/user/profile/{uid}"
    items: list[Item] = []
    try:
        resp = await client.get(url)
        # 真实生产需要走签名 / web cookie。这里只 stub
        title = f"[小红书-{name}] (采集器需要签名,MVP 占位)"
        item_url = f"{url}#note-demo"
        items.append(Item(
            id=_make_id(f"xhs:{uid}", item_url),
            source=f"xhs:{uid}",
            source_url=url,
            url=item_url,
            title=title,
            title_hash=_title_hash(title),
            summary_html="小红书采集需要签名,Day 5 接入第三方 API",
            content_html="",
            published_at=fetched_at,
            fetched_at=fetched_at,
            author=name,
            tags=["小红书"],
        ))
        print(f"  ✓ [xhs:{name}] {len(items)} 条 (MVP stub)")
    except Exception as e:
        print(f"  ✗ [xhs:{name}] {type(e).__name__}: {str(e)[:80]}")
    return items


# ============================================================
# 统一入口
# ============================================================
async def fetch_all(limit_per_source: int = 15, enabled_sources: Optional[set[str]] = None) -> list[Item]:
    """
    抓所有启用的源。

    enabled_sources: None 表示全部启用,否则只拉集合里的 source_id
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=8.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
    ) as client:
        tasks = []
        # RSS 源
        for sid, (name, url) in RSS_SOURCES.items():
            if enabled_sources and sid not in enabled_sources:
                continue
            tasks.append(fetch_rss(client, sid, name, url, limit_per_source))

        # KOL 源
        for key, (name, kind) in KOL_SOURCES.items():
            if enabled_sources and key not in enabled_sources:
                continue
            _, real_id = key.split(":", 1)
            if kind == "weibo_user":
                tasks.append(fetch_weibo_user(client, real_id, name, 5))
            elif kind == "x_user":
                tasks.append(fetch_x_user(client, real_id, name, 5))
            elif kind == "xhs_note":
                tasks.append(fetch_xhs_note(client, real_id, name, 5))

        results = await asyncio.gather(*tasks, return_exceptions=False)
        items = [it for batch in results for it in batch]
        return items


# ============================================================
# 源开关(从 Mongo 读 enabled 配置)
# ============================================================
def load_enabled_sources() -> set[str] | None:
    """从 source_config 集合读启用的源 ID 列表。
    没配过 → 返回 None(全部启用)。
    """
    try:
        from storage.mongo_writer import get_db
        db = get_db()
        cfg = db["source_config"].find_one({"_id": "global"})
        if not cfg:
            return None
        enabled = cfg.get("enabled")
        if enabled is None:
            return None
        return set(enabled)
    except Exception:
        return None


def save_enabled_sources(enabled: list[str]) -> None:
    from storage.mongo_writer import get_db
    db = get_db()
    db["source_config"].update_one(
        {"_id": "global"},
        {"$set": {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )