"""
fastInfo · 初始化管理员账号
===========================

跑法(只需要跑一次):
    python scripts/init_admin.py           # 默认 username=admin, 随机密码
    python scripts/init_admin.py --username admin --password 'MyStrongP@ssw0rd'
    python scripts/init_admin.py --reset   # 重置已存在的 admin 密码

⚠️ 第一次登录后请改密码
"""
from __future__ import annotations
import argparse
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from datetime import datetime, timezone

from auth import hash_password, verify_password
from storage.mongo_writer import ensure_indexes, get_db, DEFAULT_DB


def random_password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_+="
    return "".join(secrets.choice(alphabet) for _ in range(n))


def init_admin(username: str, password: str | None, reset: bool):
    db = get_db()
    users = db["users"]

    existing = users.find_one({"username": username})
    if existing and not reset:
        print(f"  admin 用户 '{username}' 已存在(role={existing.get('role')})")
        if existing.get("role") == "admin":
            print("  不需要重新创建。")
            return
        else:
            print(f"  ⚠ 角色是 {existing.get('role')},升级为 admin")
            users.update_one({"_id": existing["_id"]}, {"$set": {"role": "admin"}})
            return

    pw = password or random_password()
    pw_hash = hash_password(pw)

    if existing and reset:
        # --reset 真的删旧重建:处理 legacy 字符串 _id 残留(P-MIGRATE)
        old_id = existing["_id"]
        users.delete_one({"_id": old_id})
        print(f"  --reset: 已删除旧 admin(_id={old_id}, type={type(old_id).__name__})")

    doc = {
        "username": username,
        "password_hash": pw_hash,
        "email": "",
        "plan": "admin",
        "role": "admin",
        "api_keys": [],
        "created_at": datetime.now(timezone.utc),
        "last_login_at": None,
    }
    # _id 由 MongoDB 自动生成 ObjectId，与 register 流程一致
    result = users.insert_one(doc)
    print(f"  _id: {result.inserted_id}")

    print()
    print("=" * 60)
    print(f" ✓ 管理员账号已创建 / 重置")
    print(f"   username: {username}")
    print(f"   password: {pw}")
    print("=" * 60)
    print()
    print("  第一次登录后请立刻改密码!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default=None, help="不传则随机生成")
    parser.add_argument("--reset", action="store_true", help="强制重置已有 admin 密码")
    args = parser.parse_args()

    ensure_indexes()
    init_admin(args.username, args.password, args.reset)


if __name__ == "__main__":
    main()