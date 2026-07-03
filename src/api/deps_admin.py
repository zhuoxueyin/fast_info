"""
fastInfo · 管理员鉴权依赖
========================

`require_admin` 在 `require_user` 基础上多查一次 users.role。
"""
from fastapi import Depends, HTTPException, status

from api.deps import require_user
from storage.mongo_writer import get_sync_client, DEFAULT_DB


def _load_role(user_id: str) -> str:
    db = get_sync_client()[DEFAULT_DB]
    user = db["users"].find_one({"_id": user_id}, {"role": 1})
    return (user or {}).get("role", "user")


async def require_admin(user: dict = Depends(require_user)) -> dict:
    role = _load_role(user["id"])
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return {**user, "role": role}