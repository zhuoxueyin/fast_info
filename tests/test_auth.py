"""
fastInfo · 用户认证回归测试
===========================
覆盖: 注册 / 登录 / Token 验证 / 获取当前用户 / 更新用户信息 / 错误场景
"""

from __future__ import annotations
import uuid
import pytest


# ============================================================
# 注册
# ============================================================

class TestRegister:
    """用户注册全场景"""

    def test_register_success(self, client):
        """正常注册"""
        uname = f"test_auto_reg_{uuid.uuid4().hex[:8]}"
        r = client.post("/api/auth/register", json={
            "username": uname,
            "password": "Abcd1234!",
            "email": f"{uname}@fastinfo.local",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["username"] == uname
        assert data["role"] == "user"
        assert "id" in data

    def test_register_duplicate_username(self, client, auth_token):
        """重复用户名注册应返回 400"""
        # 用已存在的 test_auto_user
        r = client.post("/api/auth/register", json={
            "username": "test_auto_user",
            "password": "Abcd1234!",
        })
        assert r.status_code == 400

    def test_register_short_username(self, client):
        """用户名过短"""
        r = client.post("/api/auth/register", json={
            "username": "ab",
            "password": "Abcd1234!",
        })
        assert r.status_code == 422  # Pydantic validation error

    def test_register_weak_password(self, client):
        """密码过短"""
        r = client.post("/api/auth/register", json={
            "username": f"test_auto_pw_{uuid.uuid4().hex[:6]}",
            "password": "12345",
        })
        assert r.status_code == 422

    def test_register_invalid_username_chars(self, client):
        """用户名含特殊字符"""
        r = client.post("/api/auth/register", json={
            "username": "test@user!",
            "password": "Abcd1234!",
        })
        assert r.status_code == 422


# ============================================================
# 登录
# ============================================================

class TestLogin:
    """用户登录全场景"""

    def test_login_success(self, client):
        """正常登录"""
        r = client.post("/api/auth/login", json={
            "username": "test_auto_user",
            "password": "TestPass123!",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data
        assert len(data["token"]) > 10
        assert data["user"]["username"] == "test_auto_user"

    def test_login_wrong_password(self, client):
        """密码错误"""
        r = client.post("/api/auth/login", json={
            "username": "test_auto_user",
            "password": "WrongPass999!",
        })
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        """不存在的用户"""
        r = client.post("/api/auth/login", json={
            "username": f"test_auto_nobody_{uuid.uuid4().hex[:8]}",
            "password": "Abcd1234!",
        })
        assert r.status_code == 401

    def test_login_missing_fields(self, client):
        """缺少必填字段"""
        r = client.post("/api/auth/login", json={"username": "someone"})
        assert r.status_code == 422


# ============================================================
# Me (获取/更新当前用户)
# ============================================================

class TestMe:
    """获取/更新当前用户信息"""

    def test_me_authenticated(self, client, auth_headers):
        """已登录获取 me"""
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "test_auto_user"
        assert data["role"] in ("user", "admin")

    def test_me_no_token(self, client):
        """未登录获取 me 应 401"""
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_bad_token(self, client):
        """伪造 token"""
        r = client.get("/api/auth/me", headers={
            "Authorization": "Bearer this.is.not.a.valid.token.xyz"
        })
        assert r.status_code == 401

    def test_update_me_email(self, client, auth_headers):
        """更新用户邮箱"""
        new_email = f"updated_{uuid.uuid4().hex[:6]}@fastinfo.local"
        r = client.patch("/api/auth/me", headers=auth_headers, json={
            "email": new_email,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == new_email

        # 回滚
        client.patch("/api/auth/me", headers=auth_headers, json={
            "email": "test_auto@fastinfo.local",
        })


# ============================================================
# Token 健壮性
# ============================================================

class TestTokenRobustness:
    """JWT Token 健壮性测试"""

    def test_empty_authorization(self, client):
        """空 Authorization header"""
        r = client.get("/api/auth/me", headers={"Authorization": ""})
        assert r.status_code == 401

    def test_malformed_header(self, client):
        """畸形 Authorization header"""
        r = client.get("/api/auth/me", headers={
            "Authorization": "NotBearer xyz"
        })
        assert r.status_code == 401

    def test_expired_or_invalid_token(self, client):
        """过期或无效 token"""
        r = client.get("/api/auth/me", headers={
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        })
        assert r.status_code == 401
