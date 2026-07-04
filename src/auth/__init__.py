"""
fastInfo · 用户系统
====================

- 注册:用户名 + 密码 → bcrypt hash → MongoDB.users
- 登录:校验密码 → 颁发 JWT(本地无状态,key 用 SECRET env)
- 会话:CLI 把 JWT 存到 `data/.session.json`,后续命令读这里
- 关联:subscriptions / items / keyword_monitors 都带 user_id

数据模型:
{
    _id, username(unique), email,
    password_hash(bcrypt),
    plan: 'free' / 'pro' / 'team',
    role: 'user' / 'admin',
    api_keys: [{name, hash, prefix, scopes, created_at, last_used_at}],
    created_at, updated_at, last_login_at
}
"""
from __future__ import annotations
import json
import os
import secrets
import hashlib
import hmac
import base64
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from storage.mongo_writer import DEFAULT_DB, get_sync_client


SESSION_FILE = Path(__file__).parent.parent / "data" / ".session.json"
SECRET = os.environ.get("FASTINFO_SECRET", "dev-only-not-secure-change-in-prod")


# ============================================================
# 密码 hash(bcrypt 替代:避免引入 bcrypt 依赖,用 hashlib + salt)
# ============================================================

def hash_password(password: str) -> str:
    """PBKDF2 密码 hash(避免引入 bcrypt 依赖)"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ============================================================
# JWT(简化版,本地 CLI 用,不带刷新机制)
# ============================================================

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)


def make_token(user_id: str, username: str, ttl_seconds: int = 30 * 24 * 3600) -> str:
    """生成 JWT(token = header.payload.signature)"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    sig = hmac.new(SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def verify_token(token: str) -> Optional[dict]:
    try:
        h, p, s = token.split(".")
        signing_input = f"{h}.{p}".encode()
        expected_sig = hmac.new(SECRET.encode(), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(s)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(p))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# ============================================================
# 会话(本地 CLI 用,持久化 JWT 到文件)
# ============================================================

def save_session(token: str, user: dict):
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "token": token,
        "user": user,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2))
    try:
        os.chmod(SESSION_FILE, 0o600)
    except Exception:
        pass


def load_session() -> Optional[dict]:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text())
        token = data.get("token")
        payload = verify_token(token)
        if not payload:
            return None
        return {"token": token, "user": data.get("user"), "payload": payload}
    except Exception:
        return None


def clear_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def current_user() -> Optional[dict]:
    """当前 CLI 登录的用户,未登录返回 None"""
    sess = load_session()
    return sess["user"] if sess else None


def require_user() -> dict:
    """未登录抛错"""
    u = current_user()
    if not u:
        raise PermissionError("未登录,先跑: python fastinfo.py login")
    return u


# ============================================================
# 用户 CRUD
# ============================================================

def register(username: str, password: str, email: str = "") -> dict:
    """注册用户,返回 user dict"""
    if not re.match(r"^[a-zA-Z0-9_-]{3,32}$", username):
        raise ValueError("用户名需 3-32 位,字母数字下划线连字符")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")

    db = get_sync_client()[DEFAULT_DB]
    if db["users"].find_one({"username": username}):
        raise ValueError(f"用户名 '{username}' 已存在")

    now = datetime.now(timezone.utc)
    user = {
        "username": username,
        "email": email or f"{username}@local",
        "password_hash": hash_password(password),
        "plan": "free",
        "role": "user",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "last_login_at": None,
    }
    res = db["users"].insert_one(user)
    user["_id"] = res.inserted_id
    return user


def login(username: str, password: str) -> tuple[str, dict]:
    """登录,返回 (token, user)"""
    db = get_sync_client()[DEFAULT_DB]
    user = db["users"].find_one({"username": username})
    if not user:
        raise ValueError("用户不存在")
    if not verify_password(password, user["password_hash"]):
        raise ValueError("密码错误")

    now = datetime.now(timezone.utc)
    db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": now.isoformat(), "updated_at": now.isoformat()}},
    )

    token = make_token(str(user["_id"]), user["username"])
    user_view = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user.get("email"),
        "plan": user.get("plan", "free"),
        "role": user.get("role", "user"),
    }
    return token, user_view


def delete_user(username: str) -> int:
    db = get_sync_client()[DEFAULT_DB]
    return db["users"].delete_one({"username": username}).deleted_count


def list_users() -> list[dict]:
    db = get_sync_client()[DEFAULT_DB]
    return list(db["users"].find({}, {"password_hash": 0}).sort("created_at", -1))


def get_user_collection():
    """返回 users collection 句柄(API 层用)"""
    db = get_sync_client()[DEFAULT_DB]
    return db["users"]
