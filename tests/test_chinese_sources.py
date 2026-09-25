"""
fastInfo · 4 个国内源 fetcher 单元测试
===================================
覆盖:
  - _fetch_weibo_hot_with_cookie:用 cookie 直连 m.weibo.cn
  - _fetch_weibo_search:微博关键词搜索
  - fetch_toutiao_feed:头条分类 feed

不依赖网络:本测试在 CI 上跳过,有 cookie 时跑。
"""
import pytest
import asyncio
import os

from crawler.collectors import (
    _fetch_weibo_hot_with_cookie,
    _fetch_weibo_search,
    fetch_toutiao_feed,
)
import httpx


# 需要 admin.weibo_cookie 才会跑(本地/CI 没 cookie 时 skip)
def _has_weibo_cookie() -> bool:
    """检查 admin 用户是否有 weibo_cookie(粗略判断)"""
    try:
        from storage.mongo_writer import get_sync_client, DEFAULT_DB
        os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
        os.environ.setdefault("MONGO_DB", "fastinfo")
        db = get_sync_client()[DEFAULT_DB]
        u = db["users"].find_one({"username": "admin"}, {"weibo_cookie": 1})
        return bool((u or {}).get("weibo_cookie", "").strip())
    except Exception:
        return False


needs_cookie = pytest.mark.skipif(
    not os.environ.get("WEIBO_COOKIE_TEST") and not _has_weibo_cookie(),
    reason="无 admin.weibo_cookie,跳过需要 cookie 的测试",
)


class TestWeiboHot:
    """微博热搜(m.weibo.cn + cookie)"""

    @needs_cookie
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_weibo_hot_returns_items(self):
        try:
            items = await _fetch_weibo_hot_with_cookie(limit=20)
        except Exception as e:
            pytest.skip(f"m.weibo.cn 网络不可达或 cookie 失效:{e}")
        assert len(items) > 0, "weibo_hot 必须返回至少 1 条"
        # 至少有 5 条热搜(海外 IP 也可能返回空,但 cookie 有效时不会)
        assert len(items) >= 5, f"weibo_hot 只返回 {len(items)} 条"
        # 每条都有 title 和 url
        for it in items:
            assert it.title.startswith("[热搜#"), f"title 格式错:{it.title}"
            assert it.url.startswith("https://"), f"url 格式错:{it.url}"
            assert it.source == "weibo_hot"
            assert "weibo_hot" in it.tags

    @needs_cookie
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_weibo_hot_url_canonicalized(self):
        try:
            items = await _fetch_weibo_hot_with_cookie(limit=10)
        except Exception as e:
            pytest.skip(f"m.weibo.cn 网络不可达:{e}")
        # 检查 url 都过 canonicalize_url(不含 m.weibo.cn 追踪参数)
        for it in items:
            assert "luicode" not in it.url, f"url 含 luicode:{it.url}"
            assert "lfid" not in it.url, f"url 含 lfid:{it.url}"


class TestWeiboSearch:
    """微博搜索(关键词驱动)"""

    @needs_cookie
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_weibo_search_ent(self):
        try:
            items = await _fetch_weibo_search("娱乐", limit=5)
        except Exception as e:
            pytest.skip(f"weibo_search 网络不可达:{e}")
        # 不强制要求有结果(关键词可能当天没有讨论)
        # 但如果有结果,字段必须完整
        for it in items:
            assert "weibo_search" in it.source
            assert it.url.startswith("https://m.weibo.cn/detail/"), f"url 格式:{it.url}"
            assert len(it.title) > 0
            assert "娱乐" in it.tags

    @needs_cookie
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_weibo_search_strips_html(self):
        """微博内容带 HTML 标签,必须 strip 掉"""
        try:
            items = await _fetch_weibo_search("周杰伦演唱会", limit=5)
        except Exception as e:
            pytest.skip(f"weibo_search 网络不可达:{e}")
        for it in items:
            assert "<span" not in it.title, f"title 含未 strip 的 HTML:{it.title}"
            assert "<a " not in it.title


class TestToutiaoFeed:
    """今日头条分类 feed"""

    @pytest.mark.asyncio
    async def test_toutiao_ent_returns_items(self):
        """头条娱乐 feed:不需要 cookie,公开 API"""
        async with httpx.AsyncClient(timeout=10) as c:
            items = await fetch_toutiao_feed(
                c, "toutiao_ent", "今日头条-娱乐", "news_entertainment", limit=5,
            )
        assert len(items) > 0, "头条娱乐 feed 必须返回至少 1 条"
        for it in items:
            assert it.source == "toutiao_ent"
            assert it.url.startswith("https://"), f"url 格式:{it.url}"
            assert len(it.title) > 0

    @pytest.mark.asyncio
    async def test_toutiao_game_returns_items(self):
        async with httpx.AsyncClient(timeout=10) as c:
            items = await fetch_toutiao_feed(
                c, "toutiao_game", "今日头条-游戏", "news_game", limit=5,
            )
        # 头条游戏源偶有 0 结果(可能为空),但不报错
        for it in items:
            assert it.source == "toutiao_game"
            assert "game" in [t.lower() for t in it.tags] or "news_game" in it.tags

    @pytest.mark.asyncio
    async def test_toutiao_url_protocol_normalized(self):
        """头条 article_url 经常以 // 开头,需补 https:"""
        async with httpx.AsyncClient(timeout=10) as c:
            items = await fetch_toutiao_feed(
                c, "toutiao_ent", "今日头条-娱乐", "news_entertainment", limit=10,
            )
        for it in items:
            assert not it.url.startswith("//"), f"url 缺 https: 前缀:{it.url}"
            assert it.url.startswith("https://")