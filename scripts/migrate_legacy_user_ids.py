"""
fastInfo · 一次性历史 user_id 迁移脚本(Day 5 P3 修正)

背景:
- Day 1~4 期间 init_admin.py 给 admin 用户用字符串 _id="u_admin"(P3 违规:admin 必须是真实 ObjectId)
- Day 5 升级 init_admin.py 后,admin 用 ObjectId 字符串
- 但历史 subscriptions / subscriptions_delivered 里还残留 user_id="u_admin"
- 这些订阅匹配 candidates 时不影响(只查 items),
  但推送阶段 _find_user_doc(db, "u_admin") 查不到用户 → 渠道 webhook 全部失败

用法:
    # 1) 本地
    python scripts/migrate_legacy_user_ids.py

    # 2) Docker 预发布(进容器跑)
    docker exec -i fast_info-api-1 python -c "import sys; sys.path.insert(0,'/app/src'); exec(open('/app/scripts/migrate_legacy_user_ids.py').read())"

输出:
    [migrate] looking for admin user...
    [migrate] admin._id = 6a492e68211a19d3485db8b9
    [migrate] subscriptions with user_id=u_admin: 1
    [migrate]   - sub._id=6a49044042e1134279dca8fc title=AI资讯日报
    [migrate] subscriptions updated: 1
    [migrate] subscriptions_delivered updated: 4
    [migrate] DONE
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.mongo_writer import get_sync_client, DEFAULT_DB


def main():
    db = get_sync_client()[DEFAULT_DB]
    admin = db["users"].find_one({"username": "admin"})
    if not admin:
        print("[migrate] ❌ admin user not found, abort")
        return
    admin_id = str(admin["_id"])
    print(f"[migrate] admin._id = {admin_id}")

    # 找到所有 user_id = "u_admin" 的订阅
    bad = list(db["subscriptions"].find({"user_id": "u_admin"}))
    print(f"[migrate] subscriptions with user_id=u_admin: {len(bad)}")
    for s in bad:
        print(f"  - sub._id={s['_id']} title={s.get('title')} user_id={s.get('user_id')}")

    if not bad:
        print("[migrate] nothing to migrate, done")
        return

    # 替换 subscriptions
    r1 = db["subscriptions"].update_many(
        {"user_id": "u_admin"},
        {"$set": {"user_id": admin_id}},
    )
    print(f"[migrate] subscriptions updated: matched={r1.matched_count} modified={r1.modified_count}")

    # 替换 subscriptions_delivered
    r2 = db["subscriptions_delivered"].update_many(
        {"user_id": "u_admin"},
        {"$set": {"user_id": admin_id}},
    )
    print(f"[migrate] subscriptions_delivered updated: matched={r2.matched_count} modified={r2.modified_count}")

    print("[migrate] DONE")


if __name__ == "__main__":
    main()