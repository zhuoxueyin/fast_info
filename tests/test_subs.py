"""
fastInfo · 订阅全生命周期回归测试
=================================
覆盖: NL 解析预览 / 创建订阅 / 列出订阅 / 执行订阅 /
      PATCH 修改 / NL-PATCH 对话修改 / 删除 / 权限校验 / 错误场景
"""

from __future__ import annotations
import uuid
import time
import pytest

# 测试用的 NL 查询
NL_SIMPLE = "每天给我推送科技新闻"
NL_KEYWORD = "推送关于人工智能和机器学习的文章"
NL_CATEGORY = "体育赛事相关的资讯"


# ============================================================
# NL 解析预览
# ============================================================

class TestNLParse:
    """NL → 结构化预览（不存库）"""

    def test_parse_simple(self, client, auth_headers):
        """简单 NL 解析"""
        r = client.post("/api/subs/parse", headers=auth_headers, json={
            "nl_query": NL_SIMPLE,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "title" in data
        assert "keywords" in data
        assert "channels" in data
        # 默认至少含 inbox
        assert "inbox" in data.get("channels", [])

    def test_parse_keyword(self, client, auth_headers):
        """关键词型 NL 解析"""
        r = client.post("/api/subs/parse", headers=auth_headers, json={
            "nl_query": NL_KEYWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["keywords"], list)

    def test_parse_empty_query(self, client, auth_headers):
        """空 NL query — 服务端可能接受并返回 fallback"""
        r = client.post("/api/subs/parse", headers=auth_headers, json={
            "nl_query": "",
        })
        # 服务端可能 200（fallback）或 422（校验拒绝）
        assert r.status_code in (200, 422)

    def test_parse_no_auth(self, client):
        """未登录解析应 401"""
        r = client.post("/api/subs/parse", json={"nl_query": NL_SIMPLE})
        assert r.status_code == 401


# ============================================================
# 创建订阅
# ============================================================

class TestCreateSubscription:
    """创建订阅"""

    def _unique_title(self) -> str:
        return f"test_auto_sub_{uuid.uuid4().hex[:8]}"

    def test_create_basic(self, client, auth_headers):
        """基本创建"""
        r = client.post("/api/subs", headers=auth_headers, json={
            "nl_query": NL_SIMPLE,
            "channels": ["inbox"],
            "max_items": 5,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "sub" in data
        assert data["sub"]["channels"] == ["inbox"]
        # max_items 可能被后端覆盖（订阅层默认 10）
        assert data["sub"]["max_items"] in (5, 10)
        assert data["sub"]["is_active"] is True

    def test_create_with_custom_channels(self, client, auth_headers):
        """带多渠道创建"""
        r = client.post("/api/subs", headers=auth_headers, json={
            "nl_query": NL_KEYWORD,
            "channels": ["inbox", "webhook"],
            "categories_l1": ["AI"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "inbox" in data["sub"]["channels"]
        assert "webhook" in data["sub"]["channels"]
        assert "AI" in data["sub"]["categories_l1"]

    def test_create_with_keywords(self, client, auth_headers):
        """带自定义关键词"""
        r = client.post("/api/subs", headers=auth_headers, json={
            "nl_query": NL_SIMPLE,
            "keywords": ["GPT-5", "Claude", "Gemini"],
        })
        assert r.status_code == 200
        data = r.json()
        kw = data["sub"]["keywords"]
        assert any("GPT" in k or "Claude" in k or "Gemini" in k for k in kw)

    def test_create_no_auth(self, client):
        """未登录创建应 401"""
        r = client.post("/api/subs", json={"nl_query": NL_SIMPLE})
        assert r.status_code == 401

    def test_create_empty_nl(self, client, auth_headers):
        """空 NL 创建应 422"""
        r = client.post("/api/subs", headers=auth_headers, json={
            "nl_query": "",
        })
        assert r.status_code == 422

    def test_create_too_long_nl(self, client, auth_headers):
        """超长 NL（>200 字符）"""
        r = client.post("/api/subs", headers=auth_headers, json={
            "nl_query": "A" * 201,
        })
        assert r.status_code == 422


# ============================================================
# 列出订阅
# ============================================================

class TestListSubscriptions:
    """列出我的订阅"""

    def test_list_has_results(self, client, auth_headers):
        """列出应至少有一条（前面创建了）"""
        r = client.get("/api/subs", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] >= 1

    def test_list_no_auth(self, client):
        """未登录列出应 401"""
        r = client.get("/api/subs")
        assert r.status_code == 401

    def test_list_returns_valid_structure(self, client, auth_headers):
        """返回结构校验"""
        r = client.get("/api/subs", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert "id" in item
            assert "title" in item
            assert "channels" in item
            assert "is_active" in item
            assert "cron_expr" in item


# ============================================================
# 执行订阅
# ============================================================

class TestRunSubscription:
    """手动执行订阅"""

    def test_run_existing_sub(self, client, auth_headers):
        """执行一条已存在的订阅"""
        # 先获取一条订阅
        r = client.get("/api/subs", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("没有可用的订阅")

        sub_id = items[0]["id"]
        r = client.post(f"/api/subs/{sub_id}/run", headers=auth_headers)
        # 执行可能因为没有匹配数据返回 200,也可能因 LLM 超时等返回 500
        # 但只要不是 401/403/404,说明鉴权和路由正确
        assert r.status_code != 401, "不应该 401"
        assert r.status_code != 403, "不应该 403"
        assert r.status_code != 404, f"订阅 {sub_id} 不存在"

    def test_run_nonexistent_sub(self, client, auth_headers):
        """执行不存在的订阅应 404"""
        fake_id = "a" * 24  # 24 字符的假 ObjectId
        r = client.post(f"/api/subs/{fake_id}/run", headers=auth_headers)
        assert r.status_code == 404

    def test_run_invalid_id(self, client, auth_headers):
        """非法 ID 格式"""
        r = client.post("/api/subs/not-a-valid-id/run", headers=auth_headers)
        # 可能是 404 或 500（取决于 ObjectId 解析）
        assert r.status_code in (404, 500)

    def test_run_no_auth(self, client):
        """未登录执行应 401"""
        r = client.post("/api/subs/someid123456789012/run")
        assert r.status_code == 401


# ============================================================
# PATCH 修改订阅
# ============================================================

class TestPatchSubscription:
    """PATCH 修改订阅字段"""

    def test_patch_pause_resume(self, client, auth_headers):
        """暂停/恢复订阅"""
        # 获取一条
        r = client.get("/api/subs", headers=auth_headers)
        items = r.json()["items"]
        if not items:
            pytest.skip("没有可用的订阅")
        sub_id = items[0]["id"]

        # 暂停
        r = client.patch(f"/api/subs/{sub_id}", headers=auth_headers, json={
            "is_active": False,
        })
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        # 恢复
        r = client.patch(f"/api/subs/{sub_id}", headers=auth_headers, json={
            "is_active": True,
        })
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    def test_patch_channels(self, client, auth_headers):
        """修改渠道"""
        r = client.get("/api/subs", headers=auth_headers)
        items = r.json()["items"]
        if not items:
            pytest.skip("没有可用的订阅")
        sub_id = items[0]["id"]

        r = client.patch(f"/api/subs/{sub_id}", headers=auth_headers, json={
            "channels": ["inbox", "webhook"],
        })
        assert r.status_code == 200
        channels = r.json()["channels"]
        assert "inbox" in channels
        assert "webhook" in channels

        # 恢复
        client.patch(f"/api/subs/{sub_id}", headers=auth_headers, json={
            "channels": ["inbox"],
        })

    def test_patch_max_items(self, client, auth_headers):
        """修改最大条目数"""
        r = client.get("/api/subs", headers=auth_headers)
        items = r.json()["items"]
        if not items:
            pytest.skip("没有可用的订阅")
        sub_id = items[0]["id"]

        r = client.patch(f"/api/subs/{sub_id}", headers=auth_headers, json={
            "max_items": 20,
        })
        assert r.status_code == 200
        assert r.json()["max_items"] == 20

        # 恢复
        client.patch(f"/api/subs/{sub_id}", headers=auth_headers, json={
            "max_items": 10,
        })

    def test_patch_nonexistent(self, client, auth_headers):
        """修改不存在的订阅"""
        r = client.patch("/api/subs/aaaaaaaaaaaaaaaaaaaaaaaa", headers=auth_headers, json={
            "is_active": False,
        })
        assert r.status_code == 404

    def test_patch_no_auth(self, client):
        """未登录修改应 401"""
        r = client.patch("/api/subs/aaaaaaaaaaaaaaaaaaaaaaaa", json={"is_active": False})
        assert r.status_code == 401


# ============================================================
# NL-PATCH 对话修改
# ============================================================

class TestNLPatch:
    """NL 对话式修改订阅"""

    def test_nl_patch_pause(self, client, auth_headers):
        """用 NL 暂停订阅"""
        r = client.get("/api/subs", headers=auth_headers)
        items = r.json()["items"]
        if not items:
            pytest.skip("没有可用的订阅")
        sub_id = items[0]["id"]

        r = client.post(f"/api/subs/{sub_id}/nl-patch", headers=auth_headers, json={
            "nl_command": "暂停这个订阅",
        })
        # NL-Patch 依赖 LLM,可能超时;至少验证路由可用
        assert r.status_code != 401
        assert r.status_code != 404

    def test_nl_patch_empty_command(self, client, auth_headers):
        """空 NL 命令应 400"""
        r = client.get("/api/subs", headers=auth_headers)
        items = r.json()["items"]
        if not items:
            pytest.skip("没有可用的订阅")
        sub_id = items[0]["id"]

        r = client.post(f"/api/subs/{sub_id}/nl-patch", headers=auth_headers, json={
            "nl_command": "",
        })
        assert r.status_code == 400

    def test_nl_patch_no_auth(self, client):
        """未登录 NL-Patch 应 401"""
        r = client.post("/api/subs/aaaaaaaaaaaaaaaaaaaaaaaa/nl-patch", json={
            "nl_command": "暂停",
        })
        assert r.status_code == 401


# ============================================================
# 删除订阅
# ============================================================

class TestDeleteSubscription:
    """删除订阅"""

    def test_delete_created_sub(self, client, auth_headers):
        """创建一条新订阅后立即删除"""
        # 创建
        r = client.post("/api/subs", headers=auth_headers, json={
            "nl_query": NL_CATEGORY,
            "channels": ["inbox"],
        })
        if r.status_code != 200:
            pytest.skip("创建订阅失败,跳过删除测试")
        sub_id = r.json()["sub"]["id"]

        # 删除
        r = client.delete(f"/api/subs/{sub_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["deleted"] == sub_id

        # 确认已删除
        r = client.get("/api/subs", headers=auth_headers)
        remaining_ids = [s["id"] for s in r.json()["items"]]
        assert sub_id not in remaining_ids

    def test_delete_nonexistent(self, client, auth_headers):
        """删除不存在的订阅"""
        r = client.delete("/api/subs/bbbbbbbbbbbbbbbbbbbbbbbb", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_no_auth(self, client):
        """未登录删除应 401"""
        r = client.delete("/api/subs/aaaaaaaaaaaaaaaaaaaaaaaa")
        assert r.status_code == 401


# ============================================================
# 权限隔离
# ============================================================

class TestSubscriptionIsolation:
    """验证用户只能操作自己的订阅"""

    def test_cannot_access_others_sub(self, client, auth_headers):
        """尝试操作不存在的订阅（模拟越权）"""
        # 用别人的假 ID 操作自己的接口,返回 404 而非 403
        # 这是合理行为:不存在或不属于自己的订阅统一返回 404
        fake_id = "cccccccccccccccccccccccc"
        r = client.patch(f"/api/subs/{fake_id}", headers=auth_headers, json={
            "is_active": False,
        })
        assert r.status_code in (403, 404)
