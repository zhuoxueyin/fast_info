"""
fastInfo · Inbox 与 Stats 回归测试
==================================
覆盖: GET /api/inbox (分页/排序/过滤) / GET /api/stats / GET /api/healthz
"""

from __future__ import annotations
import pytest


# ============================================================
# Inbox (用户推送历史)
# ============================================================

class TestInbox:
    """用户收件箱"""

    def test_inbox_authenticated(self, client, auth_headers):
        """已登录获取 inbox"""
        r = client.get("/api/inbox", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_inbox_no_auth(self, client):
        """未登录获取应 401"""
        r = client.get("/api/inbox")
        assert r.status_code == 401

    def test_inbox_pagination(self, client, auth_headers):
        """分页参数"""
        r = client.get("/api/inbox?page=1&page_size=5", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["items"]) <= 5

    def test_inbox_sort_time(self, client, auth_headers):
        """按时间排序"""
        r = client.get("/api/inbox?sort=time", headers=auth_headers)
        assert r.status_code == 200

    def test_inbox_sort_relevance(self, client, auth_headers):
        """按相关度排序"""
        r = client.get("/api/inbox?sort=relevance", headers=auth_headers)
        assert r.status_code == 200

    def test_inbox_invalid_sort(self, client, auth_headers):
        """无效排序参数应 422"""
        r = client.get("/api/inbox?sort=invalid", headers=auth_headers)
        assert r.status_code == 422

    def test_inbox_page_bounds(self, client, auth_headers):
        """分页边界"""
        # 最小值
        r = client.get("/api/inbox?page=1&page_size=1", headers=auth_headers)
        assert r.status_code == 200

        # 最大值
        r = client.get("/api/inbox?page=1&page_size=100", headers=auth_headers)
        assert r.status_code == 200

        # 超限
        r = client.get("/api/inbox?page=1&page_size=101", headers=auth_headers)
        assert r.status_code == 422

        # 负页码
        r = client.get("/api/inbox?page=0", headers=auth_headers)
        assert r.status_code == 422

    def test_inbox_category_filter(self, client, auth_headers):
        """按类目过滤"""
        r = client.get("/api/inbox?category=科技", headers=auth_headers)
        assert r.status_code == 200


# ============================================================
# Stats (数据库统计)
# ============================================================

class TestStats:
    """GET /api/stats 统计信息"""

    def test_stats_basic(self, client, auth_headers):
        """获取统计（需要登录）"""
        r = client.get("/api/stats", headers=auth_headers)
        # stats 可能需要 admin,或普通用户也可
        assert r.status_code in (200, 403)

    def test_stats_no_auth(self, client):
        """stats 公开可读"""
        r = client.get("/api/stats")
        # stats 可能是公开接口，也可能是需登录
        assert r.status_code in (200, 401, 403)


# ============================================================
# Healthz (健康检查)
# ============================================================

class TestHealthz:
    """GET /healthz 健康检查"""

    def test_healthz(self, client):
        """健康检查公开可用"""
        r = client.get("/healthz")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] in ("ok", "degraded")

    def test_root(self, client):
        """根路径"""
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "fastInfo"
        assert "version" in data
        assert data["api_base"] == "/api"


# ============================================================
# Admin 入口（仅路由可用性，不做数据验证）
# ============================================================

class TestAdminEntrypoints:
    """管理员接口路由可用性"""

    def test_admin_routes_exist(self, client, auth_headers):
        """验证管理路由存在且返回正确状态码"""
        admin_endpoints = [
            "/api/admin/tasks/runs",
            "/api/admin/tasks/source-status",
            "/api/admin/llm/health",
            "/api/admin/sources",
            "/api/admin/taxonomy",
        ]
        for ep in admin_endpoints:
            r = client.get(ep, headers=auth_headers)
            # admin 接口可能 200(admin 用户) 或 403(普通用户)
            assert r.status_code in (200, 403), f"{ep} 返回 {r.status_code},预期 200/403"
