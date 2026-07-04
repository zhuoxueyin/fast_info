"""
fastInfo · 快速冒烟测试
=======================
仅验证核心链路可用性,用于 CI / pre-commit hook。
运行: pytest tests/test_smoke.py -v
"""

from __future__ import annotations
import pytest


@pytest.mark.smoke
class TestSmokeHealth:
    """核心健康检查"""

    def test_api_healthz(self, client):
        """API 健康检查"""
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] in ("ok", "degraded")

    def test_api_root(self, client):
        """根路径"""
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "fastInfo"


@pytest.mark.smoke
class TestSmokeAuth:
    """认证核心链路"""

    def test_login(self, client):
        """登录获取 token"""
        r = client.post("/api/auth/login", json={
            "username": "test_auto_user",
            "password": "TestPass123!",
        })
        assert r.status_code == 200
        assert len(r.json()["token"]) > 10

    def test_me(self, client, auth_headers):
        """获取当前用户"""
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["username"] == "test_auto_user"


@pytest.mark.smoke
class TestSmokePublicEndpoints:
    """公开接口可用性"""

    def test_today(self, client):
        r = client.get("/api/today?limit=5")
        assert r.status_code == 200

    def test_hot(self, client):
        r = client.get("/api/hot?limit=5")
        assert r.status_code == 200

    def test_search(self, client):
        r = client.get("/api/search?q=AI&limit=5")
        assert r.status_code == 200

    def test_banner(self, client):
        r = client.get("/api/banner")
        assert r.status_code == 200

    def test_channels(self, client):
        r = client.get("/api/notifier/channels")
        assert r.status_code == 200


@pytest.mark.smoke
class TestSmokeSubs:
    """订阅核心链路"""

    def test_parse(self, client, auth_headers):
        r = client.post("/api/subs/parse", headers=auth_headers, json={
            "nl_query": "每天推送科技新闻",
        })
        assert r.status_code == 200

    def test_list(self, client, auth_headers):
        r = client.get("/api/subs", headers=auth_headers)
        assert r.status_code == 200


@pytest.mark.smoke
class TestSmokeSettings:
    """设置核心链路"""

    def test_get_settings(self, client, auth_headers):
        r = client.get("/api/settings", headers=auth_headers)
        assert r.status_code == 200

    def test_test_inbox(self, client, auth_headers):
        r = client.post("/api/notifier/test", headers=auth_headers, json={
            "channel": "inbox",
        })
        assert r.status_code == 200
        assert "ok" in r.json()
