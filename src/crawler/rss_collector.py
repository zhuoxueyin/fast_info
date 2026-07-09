"""
fastInfo · RSS 采集器
=====================

支持站点:
- 36kr         https://36kr.com
- 虎嗅         https://huxiu.com
- 爱范儿        https://www.ifanr.com
- 量子位        https://www.qbitai.com
- 机器之心      https://www.jiqizhixin.com
- InfoQ        https://www.infoq.cn
- 少数派        https://sspai.com

输出:统一格式的 Item dataclass,可直接喂给 summarizer / 写入 MongoDB
"""
from __future__ import annotations
import asyncio
import hashlib
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import AsyncIterator, Optional

import feedparser
import httpx


@dataclass
class Item:
    id: str                 # hash(source_url) 唯一 ID
    source: str             # 站点简称,如 "36kr"
    source_url: str
    url: str
    title: str
    summary_html: str       # RSS 自带的简短描述
    content_html: str       # 完整正文(MVP 可选,留空)
    published_at: Optional[str]    # ISO 8601
    fetched_at: str         # ISO 8601
    title_hash: str = ""    # 规范化标题 hash(跨源去重用)
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    language: str = "zh"


# ============================================================
# 站点配置
# ============================================================

SOURCES = {
    "36kr":       ("36氪",          "https://36kr.com/feed"),
    "huxiu":      ("虎嗅",          "https://www.huxiu.com/rss/0.xml"),
    "ifanr":      ("爱范儿",         "https://www.ifanr.com/feed"),
    "qbitai":     ("量子位",         "https://www.qbitai.com/feed"),
    "infoq":      ("InfoQ中国",      "https://www.infoq.cn/feed.xml"),
    "sspai":      ("少数派",         "https://sspai.com/feed"),
    "ithome":     ("IT之家",         "https://www.ithome.com/rss/"),
}

USER_AGENT = "Mozilla/5.0 (compatible; fastInfo/1.0; +https://github.com/fastinfo)"


# ============================================================
# 抓取与解析
# ============================================================

def _parse_published(entry) -> Optional[str]:
    """从 RSS entry 抽出发布时间,统一 ISO 8601"""
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                continue
    return None


def _strip_html(s: str) -> str:
    """去掉 HTML 标签(MVP 用,Beta 切 trafilatura 提正文)"""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _normalize_title(t: str) -> str:
    """规范化标题用于去重:去标点 / 数字 / 多余空白,统一小写。"""
    if not t:
        return ""
    s = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", t)
    s = re.sub(r"\s+", "", s)
    return s.lower().strip()


def _title_hash(title: str) -> str:
    """标题哈希(规范化后 sha256[:16]),用于跨源去重。"""
    return hashlib.sha256(_normalize_title(title).encode()).hexdigest()[:16]


# 常见追踪/会话参数:参与 url_hash 会导致同一文章每次抓取都变新 id
_TRACKING_QUERY_KEYS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_reader", "spm", "from", "ref", "refer", "share_token",
    "share_from", "tt_from", "log_pb", "rank", "style_id", "category_name",
    "event_type", "enter_from", "entrance_hotspot", "hot_board_impr_id",
    "hot_board_cluster_id", "page_location", "location", "jump_page",
    "source", "topic_id",  # topic_id 已嵌在 path /trending/{id}
})


def canonicalize_url(url: str) -> str:
    """去掉追踪参数,抽出稳定正文 URL,供 url_hash 去重。

    典型故障:头条热搜 URL 每次带不同 log_pb/impr_id,
    导致同一话题被当成 N 条新 item 推送(见 2026世界杯资讯「新华社：国足…」重复)。
    """
    if not url:
        return ""
    try:
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        raw = url.strip()
        p = urlparse(raw)
        host = (p.netloc or "").lower()
        path = p.path or ""

        # 头条热榜/文章:path 里已有稳定 id
        if "toutiao.com" in host:
            m = re.match(r"^/(trending|article|group)/(\d+)", path)
            if m:
                return f"https://www.toutiao.com/{m.group(1)}/{m.group(2)}"

        # 知乎 question/answer
        if "zhihu.com" in host:
            m = re.match(r"^/(question|answer|p)/(\d+)", path)
            if m:
                return f"https://www.zhihu.com/{m.group(1)}/{m.group(2)}"

        # 通用:剥 tracking query + fragment
        if p.query:
            kept = [
                (k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
                if k.lower() not in _TRACKING_QUERY_KEYS
                and not k.lower().startswith("utm_")
            ]
            query = urlencode(kept)
        else:
            query = ""
        return urlunparse((p.scheme or "https", p.netloc, path.rstrip("/") or path, "", query, ""))
    except Exception:
        return url.strip()


def _make_id(source: str, url: str) -> str:
    """基于 source + 规范化 URL 生成稳定 24 位 hash id。"""
    canon = canonicalize_url(url) or (url or "")
    h = hashlib.sha256(f"{source}|{canon}".encode()).hexdigest()
    return h[:24]


async def fetch_source(
    client: httpx.AsyncClient,
    source_id: str,
    name: str,
    feed_url: str,
    limit: int = 15,
) -> list[Item]:
    """抓取一个 RSS 源,返回 Item 列表"""
    try:
        resp = await client.get(feed_url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ✗ [{source_id}] {type(e).__name__}: {str(e)[:80]}")
        return []

    feed = feedparser.parse(resp.text)
    if feed.bozo and not feed.entries:
        print(f"  ✗ [{source_id}] parse error: {str(feed.bozo_exception)[:80]}")
        return []

    items: list[Item] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for entry in feed.entries[:limit]:
        url = entry.get("link", "").strip()
        if not url:
            continue
        title = _strip_html(entry.get("title", "")).strip()
        if not title:
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


async def fetch_all(limit_per_source: int = 15) -> list[Item]:
    """兼容入口:转发到 collectors.fetch_all,支持 KOL + 源开关 + 自动 dedup。"""
    from .collectors import fetch_all as _fetch_all
    return await _fetch_all(limit_per_source=limit_per_source)


# ============================================================
# CLI 入口
# ============================================================

async def main():
    print("=" * 60)
    print(f"  fastInfo · RSS 抓取 (共 {len(SOURCES)} 个源)")
    print("=" * 60)
    items = await fetch_all()
    print()
    print(f"总计 {len(items)} 条(已去重)")
    print()
    for i, it in enumerate(items[:5], 1):
        print(f"  [{i}] {it.source} | {it.published_at[:10] if it.published_at else '????-??-??'}")
        print(f"      {it.title[:60]}")
        print(f"      {it.url}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
