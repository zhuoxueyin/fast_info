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
from .mirrors import get_huxiu_urls, get_nitter_mirrors
from storage.source_config import load_enabled_sources
from storage.source_runs import record_source_run, _classify_error


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
# Per-source run wrapper + 统一入口
# ============================================================

async def _run_one_source(source_id: str, fetcher, *, enabled: bool) -> list[Item]:
    """
    跑一个源,失败/成功记 source_runs,自动禁用按 source_config.auto_disable_threshold。
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
    )
    return items


async def fetch_all(limit_per_source: int = 15, enabled_sources: Optional[set[str]] = None) -> list[Item]:
    """
    全源抓取。顺序跑(每源间隔独立 source_runs 记录)。
    30 min 一次,18 个源顺序跑大概 30-60s,可以接受。
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
            urls = get_huxiu_urls() if sid == "huxiu" else [url]
            async def _run():
                return await fetch_rss_with_fallback(client, sid, name, urls, limit_per_source)
            items = await _run_one_source(sid, _run, enabled=enabled)
            all_items.extend(items)

        # === KOL ===
        for key, (name, kind) in KOL_SOURCES.items():
            enabled = (active is None) or (key in active)
            _, real_id = key.split(":", 1)
            if kind == "weibo_user":
                async def _run():
                    return await fetch_weibo_user(client, real_id, name, 5)
                items = await _run_one_source(key, _run, enabled=enabled)
            elif kind == "x_user":
                async def _run():
                    return await fetch_x_user_multi(client, real_id, name, 5)
                items = await _run_one_source(key, _run, enabled=enabled)
            elif kind == "xhs_note":
                async def _run():
                    return await fetch_xhs_note(client, real_id, name, 5)
                items = await _run_one_source(key, _run, enabled=enabled)
            else:
                continue
            all_items.extend(items)

        return all_items


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
