"""
fastInfo · 测试框架核心
=======================
- 自动创建/清理测试用户和测试数据
- 每个测试用例的数据完全隔离（前缀 test_auto_）
- 提供 FastAPI TestClient + 真实 MongoDB
"""

from __future__ import annotations
import os
import sys
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

# 确保 src/ 可 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

# ---- 测试标记常量 ----
TEST_PREFIX = "test_auto_"
TEST_USERNAME = f"{TEST_PREFIX}user"
TEST_PASSWORD = "TestPass123!"
TEST_EMAIL = "test_auto@fastinfo.local"

# ---- MongoDB 连接 ----
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.environ.get("DB_NAME", "fastinfo")

# ---- 需要清理的集合 ----
CLEANUP_COLLECTIONS = [
    "users",
    "subscriptions",
    "subscriptions_delivered",
    "items",
    "temp_topics",
]


def _get_mongo():
    """获取同步 MongoDB 客户端"""
    return MongoClient(MONGO_URI)


def _cleanup_prefix(prefix: str = TEST_PREFIX):
    """删除所有 test_auto_ 前缀的测试数据"""
    try:
        client = _get_mongo()
        client.server_info()  # 验证连接
    except Exception:
        return {c: 0 for c in CLEANUP_COLLECTIONS}

    db = client[DB_NAME]
    deleted_counts = {}

    # 1) users: username 前缀
    r = db["users"].delete_many({"username": {"$regex": f"^{prefix}"}})
    deleted_counts["users"] = r.deleted_count

    # 2) subscriptions: user_id 通过 users 匹配（含 title 前缀）
    r = db["subscriptions"].delete_many({"title": {"$regex": f"^{prefix}"}})
    deleted_counts["subscriptions"] = r.deleted_count

    # 3) subscriptions_delivered: subscription_id 前缀
    r = db["subscriptions_delivered"].delete_many({"subscription_id": {"$regex": f"^{prefix}"}})
    deleted_counts["subscriptions_delivered"] = r.deleted_count

    # 4) items: source 或 title 前缀
    r = db["items"].delete_many({
        "$or": [
            {"source": {"$regex": f"^{prefix}"}},
            {"title": {"$regex": f"^{prefix}"}},
        ]
    })
    deleted_counts["items"] = r.deleted_count

    # 5) temp_topics: topic_id 前缀
    r = db["temp_topics"].delete_many({"topic_id": {"$regex": f"^{prefix}"}})
    deleted_counts["temp_topics"] = r.deleted_count

    client.close()
    return deleted_counts


def _ensure_test_user(client: TestClient) -> tuple[str, str]:
    """
    确保存在一个 test_auto_user,返回 (token, user_id)。
    如果已存在,先登录获取 token;否则注册。
    """
    # 先尝试登录
    r = client.post("/api/auth/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    })
    if r.status_code == 200:
        data = r.json()
        return data["token"], data["user"]["id"]

    # 注册
    r = client.post("/api/auth/register", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "email": TEST_EMAIL,
    })
    assert r.status_code == 200, f"注册测试用户失败: {r.text}"
    user_id = r.json()["id"]

    # 登录拿 token
    r = client.post("/api/auth/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200, f"测试用户登录失败: {r.text}"
    return r.json()["token"], user_id


def _seed_test_items(count: int = 5):
    """
    向 items 集合写入少量测试数据,用于 today/hot/search/inbox 测试。
    每条记录带 test_auto_ 前缀,方便清理。
    """
    client = _get_mongo()
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for i in range(count):
        docs.append({
            "source": f"{TEST_PREFIX}source_{i}",
            "url": f"https://fastinfo.local/{TEST_PREFIX}item_{i}",
            "title": f"{TEST_PREFIX}测试资讯标题 #{i}",
            "summary": f"这是第 {i} 条测试资讯的摘要内容,用于自动化测试。",
            "category": "tech",
            "category_l1": "科技",
            "category_l2": "人工智能",
            "relevance": 7.5 + i * 0.5,
            "published_at": now,
            "fetched_at": now,
            "author": f"{TEST_PREFIX}author_{i}",
            "tags": ["AI", "test"],
            "url_hash": f"{TEST_PREFIX}hash_{uuid.uuid4().hex[:12]}",
        })
    if docs:
        db["items"].insert_many(docs)
    client.close()


# ============================================================
# Pytest Fixtures
# ============================================================

@pytest.fixture(scope="session")
def mongo_client():
    """会话级 MongoDB 连接"""
    client = _get_mongo()
    yield client
    client.close()


@pytest.fixture(scope="session")
def app():
    """创建 FastAPI app 实例"""
    from api.app import create_app
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """FastAPI TestClient（会话级复用）"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client) -> str:
    """测试用户 JWT token（整个 session 共用）"""
    token, _ = _ensure_test_user(client)
    return token


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """带 Authorization header 的请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="session")
def test_user_id(client, auth_token) -> str:
    """获取测试用户 ID"""
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(autouse=True)
def seed_items():
    """每个测试函数前确保 items 有种子数据"""
    if _mongodb_available():
        try:
            _seed_test_items(count=3)
        except Exception:
            pass  # 种子数据失败不影响测试


# ============================================================
# 全局 setup / teardown
# ============================================================

def _mongodb_available() -> bool:
    """检查 MongoDB 是否可连接"""
    try:
        client = _get_mongo()
        client.server_info()
        client.close()
        return True
    except Exception:
        return False


def pytest_sessionstart(session):
    """测试套件启动时:清理旧数据 + 播种测试 items"""
    if not _mongodb_available():
        print("\n[fastInfo tests] [WARN] MongoDB not available, skip data prep")
        return
    print("\n[fastInfo tests] Cleaning old test data...")
    try:
        deleted = _cleanup_prefix()
        for coll, cnt in deleted.items():
            if cnt:
                print(f"  - {coll}: deleted {cnt}")
        print("[fastInfo tests] Seeding test items...")
        _seed_test_items(count=5)
        print("[fastInfo tests] Ready\n")
    except Exception as e:
        print(f"[fastInfo tests] [WARN] Data prep failed: {e}")


def pytest_sessionfinish(session, exitstatus):
    """测试套件结束后:彻底清理所有测试数据"""
    if not _mongodb_available():
        print("\n[fastInfo tests] [WARN] MongoDB not available, skip cleanup")
        return
    print("\n[fastInfo tests] Cleaning test data...")
    try:
        deleted = _cleanup_prefix()
        total = sum(deleted.values())
        print(f"  Total cleaned: {total}")
        for coll, cnt in deleted.items():
            if cnt:
                print(f"  - {coll}: {cnt}")
        print("[fastInfo tests] Cleanup done\n")
    except Exception as e:
        print(f"[fastInfo tests] [WARN] Cleanup failed: {e}")
