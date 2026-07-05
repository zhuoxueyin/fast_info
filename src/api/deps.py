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
from bson import ObjectId
from bson.errors import InvalidId

from auth import verify_token, load_session
from storage.mongo_writer import get_db


def _enrich_user(payload: dict) -> dict:
    """从 Mongo 读最新用户信息,作为后续 handlers 唯一的事实来源。

    失败语义(任一条都抛 401,不再放行半残 dict):
      - JWT sub 缺失或不是合法 24-hex ObjectId (例如老 token 的 'u_admin')
      - Mongo 找不到对应 _id (例如用户被删 / 库切换)
    """
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="token 无效")
    try:
        oid = ObjectId(sub)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=401,
            detail="token 格式无效(请重新登录)",
        )
    db = get_db()
    u = db["users"].find_one({"_id": oid})
    if not u:
        raise HTTPException(status_code=401, detail="用户不存在,请重新登录")
    return {
        "id":                      str(u["_id"]),
        "username":                u.get("username", ""),
        "role":                    u.get("role", "user"),
        "plan":                    u.get("plan", "free"),
        "email":                   u.get("email", "") or "",
        "default_channels":        u.get("default_channels", []) or [],
        "feishu_webhook":          u.get("feishu_webhook", "") or "",
        "feishu_open_id":          u.get("feishu_open_id", "") or "",
        "wechat_webhook":          u.get("wechat_webhook", "") or "",
        "webhook_url":             u.get("webhook_url", "") or "",
        "smtp_host":               u.get("smtp_host", "smtp.qq.com"),
        "smtp_port":               u.get("smtp_port", 465),
        "smtp_user":               u.get("smtp_user", "") or "",
        "smtp_pass":               u.get("smtp_pass", "") or "",
    }


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
