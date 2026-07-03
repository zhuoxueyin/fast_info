"""
fastInfo · API 鉴权依赖
======================

- Header 期望:`Authorization: Bearer <jwt>`
- 复用 src/auth 的 JWT(PBKDF2 + HS256,跟 CLI 同一套)
- get_current_user_optional:未登录返回 None(用于公开接口)
- require_user:未登录抛 401
"""
from __future__ import annotations
from typing import Optional

from fastapi import Header, HTTPException, status

from auth import verify_token, load_session
from storage.mongo_writer import get_db


def _enrich_user(payload: dict) -> dict:
    """从 Mongo 读最新 role / plan / email,避免 JWT 过期前角色变更不生效。"""
    out = {
        "id": payload.get("sub"),
        "username": payload.get("username"),
    }
    try:
        db = get_db()
        u = db["users"].find_one({"_id": out["id"]}, {"role": 1, "plan": 1, "email": 1})
        if u:
            out["role"] = u.get("role", "user")
            out["plan"] = u.get("plan", "free")
            out["email"] = u.get("email") or None
    except Exception:
        out.setdefault("role", "user")
        out.setdefault("plan", "free")
    return out


async def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """从 Authorization header 解 JWT,未登录/失效返回 None。"""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    payload = verify_token(token)
    if not payload:
        return None
    return _enrich_user(payload)


async def require_user(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """强制鉴权,未登录抛 401。"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录,header 需要: Authorization: Bearer <token>",
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 格式: Bearer <token>")
    token = parts[1].strip()
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return _enrich_user(payload)
