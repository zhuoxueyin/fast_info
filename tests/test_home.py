"""
fastInfo · 首页各入口可用性回归测试
===================================
覆盖: /api/today /api/hot /api/search /api/banner /api/categories
      参数校验 / 分页 / 无鉴权公开接口 / 错误边界
"""

from __future__ import annotations
import pytest


# ============================================================
# Today (最近内容流)
# ============================================================

class TestToday:
    """GET /api/today 公开内容流"""

    def test_today_basic(self, client):
        """基本查询"""
        r = client.get("/api/today")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "limit" in data
        assert isinstance(data["items"], list)

    def test_today_with_limit(self, client):
        """自定义 limit"""
        r = client.get("/api/today?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) <= 5
        assert data["limit"] == 5

    def test_today_with_source_filter(self, client):
        """按 source 过滤"""
        r = client.get("/api/today?source=test_auto_source_0")
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert item["source"] == "test_auto_source_0"

    def test_today_with_category_filter(self, client):
        """按 category 过滤"""
        r = client.get("/api/today?category=tech")
        assert r.status_code == 200

    def test_today_with_l1_filter(self, client):
        """按 L1 类目过滤"""
        r = client.get("/api/today?category=科技")
        assert r.status_code == 200

    def test_today_limit_bounds(self, client):
        """limit 边界值"""
        # 最小值
        r = client.get("/api/today?limit=1")
        assert r.status_code == 200

        # 最大值
        r = client.get("/api/today?limit=100")
        assert r.status_code == 200

        # 超限
        r = client.get("/api/today?limit=101")
        assert r.status_code == 422

        # 负数
        r = client.get("/api/today?limit=0")
        assert r.status_code == 422

    def test_today_item_structure(self, client):
        """返回条目结构校验"""
        r = client.get("/api/today?limit=1")
        if r.json()["items"]:
            item = r.json()["items"][0]
            required = ["source", "url", "title", "summary", "category"]
            for field in required:
                assert field in item, f"缺少字段 {field}"


# ============================================================
# Hot (热门内容)
# ============================================================

class TestHot:
    """GET /api/hot 热门排行"""

    def test_hot_basic(self, client):
        """基本查询"""
        r = client.get("/api/hot")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "hours" in data
        assert "threshold" in data

    def test_hot_with_hours(self, client):
        """自定义时间窗口"""
        r = client.get("/api/hot?hours=48")
        assert r.status_code == 200
        assert r.json()["hours"] == 48

    def test_hot_with_threshold(self, client):
        """自定义阈值"""
        r = client.get("/api/hot?threshold=0.5")
        assert r.status_code == 200

    def test_hot_with_category(self, client):
        """按类目过滤热门"""
        r = client.get("/api/hot?category=科技")
        assert r.status_code == 200

    def test_hot_limit_bounds(self, client):
        """limit 边界"""
        r = client.get("/api/hot?limit=1")
        assert r.status_code == 200

        r = client.get("/api/hot?limit=50")
        assert r.status_code == 200

        r = client.get("/api/hot?limit=51")
        assert r.status_code == 422

    def test_hot_hours_bounds(self, client):
        """hours 边界"""
        r = client.get("/api/hot?hours=1")
        assert r.status_code == 200

        r = client.get("/api/hot?hours=168")
        assert r.status_code == 200

        r = client.get("/api/hot?hours=169")
        assert r.status_code == 422


# ============================================================
# Search (搜索)
# ============================================================

class TestSearch:
    """GET /api/search 混合搜索"""

    def test_search_basic(self, client):
        """基本搜索"""
        r = client.get("/api/search?q=测试资讯")
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "total" in data
        assert "items" in data

    def test_search_empty_query(self, client):
        """空查询应拒绝"""
        r = client.get("/api/search?q=")
        assert r.status_code == 422

    def test_search_missing_query(self, client):
        """缺少 q 参数"""
        r = client.get("/api/search")
        assert r.status_code == 422

    def test_search_with_source(self, client):
        """带 source 过滤"""
        r = client.get("/api/search?q=AI&source=test_auto_source_0")
        assert r.status_code == 200

    def test_search_with_category(self, client):
        """带 category 过滤"""
        r = client.get("/api/search?q=AI&category=科技")
        assert r.status_code == 200

    def test_search_with_limit(self, client):
        """带 limit"""
        r = client.get("/api/search?q=AI&limit=5")
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 5

    def test_search_limit_bounds(self, client):
        """limit 边界"""
        r = client.get("/api/search?q=test&limit=100")
        assert r.status_code == 200

        r = client.get("/api/search?q=test&limit=101")
        assert r.status_code == 422


# ============================================================
# Banner (首页分类配置)
# ============================================================

class TestBanner:
    """GET /api/banner 公开 + PUT 管理员写"""

    def test_get_banner_public(self, client):
        """公开读 banner（无需登录）"""
        r = client.get("/api/banner")
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_put_banner_no_auth(self, client):
        """未登录写 banner 应 401（或 403）"""
        r = client.put("/api/banner", json={
            "categories": ["科技", "AI"],
            "max_per_category": 3,
        })
        assert r.status_code in (401, 403)

    def test_put_banner_as_user(self, client, auth_headers):
        """普通用户写 banner 应 403"""
        r = client.put("/api/banner", headers=auth_headers, json={
            "categories": ["科技"],
            "max_per_category": 3,
        })
        assert r.status_code in (401, 403)


# ============================================================
# Categories (类目列表)
# ============================================================

class TestCategories:
    """GET /api/categories 类目列表"""

    def test_categories_basic(self, client):
        """获取类目列表（公开接口）"""
        r = client.get("/api/categories")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or "categories" in data

    def test_categories_has_common(self, client):
        """应包含常见类目"""
        r = client.get("/api/categories")
        data = r.json()
        categories = data if isinstance(data, list) else data.get("categories", [])
        # 至少应有科技类（种子数据中设的）
        if categories:
            assert any("科技" in str(c) or "tech" in str(c).lower() for c in categories)


# ============================================================
# Items 详情
# ============================================================

class TestItems:
    """GET /api/items/{id} 资讯详情"""

    def test_items_batch(self, client):
        """批量查询"""
        r = client.get("/api/items?ids=test_auto_hash_000000,test_auto_hash_111111")
        # 可能 200 或 404，取决于 ids 是否精确匹配
        assert r.status_code in (200, 404, 422)
