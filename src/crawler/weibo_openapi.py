"""Weibo 客户端 (Day 5)

双模式:
  - "openapi"  : 走 Weibo OpenAPI (需要 access_token,生产推荐)
  - "scraper"  : 走 m.weibo.cn 公开页 scrape(MVP 兜底,易被风控)

后续接 OpenAPI: 在 source_config.platform_config.access_token 填入即可切换。
"""
from __future__ import annotations
import re
from typing import Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from crawler.rss_collector import Item


class WeiboClient:
    def __init__(
        self,
        *,
        access_token: Optional[str] = None,
        cookie: Optional[str] = None,
        timeout_s: float = 8.0,
    ):
        self.access_token = access_token or ""
        self.cookie = cookie or ""
        self.mode = "openapi" if self.access_token else "scraper"
        self.timeout_s = timeout_s

    async def fetch_user_timeline(self, client: httpx.AsyncClient, uid: str, name: str, limit: int = 10) -> list["Item"]:
        """拉用户最近微博。
        返回格式与 RSS Item dataclass 一致,直接交给 ingest pipeline。
        """
        if self.mode == "openapi":
            return await self._fetch_openapi(client, uid, name, limit)
        return await self._fetch_scraper(client, uid, name, limit)

    async def _fetch_openapi(self, client: httpx.AsyncClient, uid: str, name: str, limit: int) -> list:
        """Weibo OpenAPI 实现脚手架。
        真实接入:
          GET https://api.weibo.com/2/statuses/user_timeline.json
          params: access_token, uid, count
          response: statuses[].text / created_at
        未配 access_token 时不会走这里。
        """
        # 这里只放占位,生产需按 OpenAPI 文档实现
        from crawler.rss_collector import Item
        return [Item(
            id=f"weibo:{uid}:empty",
            source=f"weibo:{uid}",
            source_url=f"https://api.weibo.com/2/statuses/user_timeline/{uid}",
            url=f"https://weibo.com/{uid}",
            title=f"[微博/{name}] (OpenAPI 未配 access_token)",
            title_hash="",
            summary_html="",
            content_html="",
            published_at=None,
            fetched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            author=name,
            tags=["微博", "openapi-stub"],
        )]

    async def _fetch_scraper(self, client: httpx.AsyncClient, uid: str, name: str, limit: int) -> list:
        """公开页 scrape。维持 MVP 现有实现,加 cookie / frequency 后续。"""
        from datetime import datetime, timezone
        from crawler.rss_collector import Item, _strip_html, _title_hash, _make_id
        fetched_at = datetime.now(timezone.utc).isoformat()
        url = f"https://m.weibo.cn/u/{uid}"
        items: list = []
        try:
            headers = {"Referer": "https://m.weibo.cn/"}
            if self.cookie:
                headers["Cookie"] = self.cookie
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
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
        except Exception as e:
            raise e
        return items


def make_weibo_client(platform_config: dict | None) -> WeiboClient:
    cfg = platform_config or {}
    return WeiboClient(
        access_token=cfg.get("openapi_token") or None,
        cookie=cfg.get("cookie") or None,
    )
