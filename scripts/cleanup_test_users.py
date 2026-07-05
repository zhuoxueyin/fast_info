"""
fastInfo · 清理测试用户(保留 admin)
====================================

背景:
    项目 0→1 阶段,只有 admin 是真实用户(原则 P3)。
    examples/api_e2e_smoke.py 每次跑都注册 smoke_{random} 用户,从不清理,
    tests/conftest.py 的 test_auto_user 在 sessionfinish 失败时也会残留,
    加上 Day 1/2 手测的 alice/bob/demo/testuser,users 集合积累了 14 个垃圾账号。

用法:
    python scripts/cleanup_test_users.py           # 预览(dry-run)
    python scripts/cleanup_test_users.py --apply   # 真删

清理范围:
    - users: 删除所有非 admin 用户
    - subscriptions: 删除这些用户关联的订阅
    - subscriptions_delivered: 删除这些用户关联的推送记录
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storage.mongo_writer import get_db


KEEP_ROLES = {"admin"}  # 只保留 role=admin 的用户


def main():
    parser = argparse.ArgumentParser(description="清理测试用户,保留 admin")
    parser.add_argument("--apply", action="store_true", help="真正执行删除(默认 dry-run)")
    args = parser.parse_args()

    db = get_db()

    # 1) 找出要删的用户
    all_users = list(db["users"].find({}, {"username": 1, "role": 1, "email": 1}))
    to_delete = [u for u in all_users if u.get("role") not in KEEP_ROLES]
    keep = [u for u in all_users if u.get("role") in KEEP_ROLES]

    print(f"Total users: {len(all_users)}")
    print(f"  保留 (role in {KEEP_ROLES}): {len(keep)}")
    for u in keep:
        print(f"    - {u.get('username')} (role={u.get('role')})")
    print(f"  删除: {len(to_delete)}")
    for u in to_delete:
        print(f"    - {u.get('username', '(无)')} (role={u.get('role')}, email={u.get('email')})")

    if not to_delete:
        print("\n没有需要清理的用户。")
        return

    # 2) 收集要删的 user_id
    delete_ids = [u["_id"] for u in to_delete]
    delete_id_strs = [str(i) for i in delete_ids]

    # 3) 统计连带数据
    subs_count = db["subscriptions"].count_documents({"user_id": {"$in": delete_id_strs + delete_ids}})
    delivered_count = db["subscriptions_delivered"].count_documents({"user_id": {"$in": delete_id_strs + delete_ids}})

    print(f"\n连带数据:")
    print(f"  subscriptions:           {subs_count} 条")
    print(f"  subscriptions_delivered: {delivered_count} 条")

    if not args.apply:
        print("\n[dry-run] 未加 --apply,不执行删除。")
        print("要真删: python scripts/cleanup_test_users.py --apply")
        return

    # 4) 执行删除
    print("\n[apply] 开始删除...")
    r1 = db["subscriptions_delivered"].delete_many({"user_id": {"$in": delete_id_strs + delete_ids}})
    print(f"  subscriptions_delivered: 删除 {r1.deleted_count}")
    r2 = db["subscriptions"].delete_many({"user_id": {"$in": delete_id_strs + delete_ids}})
    print(f"  subscriptions:           删除 {r2.deleted_count}")
    r3 = db["users"].delete_many({"_id": {"$in": delete_ids}})
    print(f"  users:                   删除 {r3.deleted_count}")

    # 5) 验证
    remaining = db["users"].count_documents({})
    print(f"\n[done] 剩余用户: {remaining}")
    for u in db["users"].find({}, {"username": 1, "role": 1}):
        print(f"  - {u.get('username')} (role={u.get('role')})")


if __name__ == "__main__":
    main()
