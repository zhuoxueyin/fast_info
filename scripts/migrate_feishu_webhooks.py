"""fastInfo · 飞书群机器人配置迁移脚本(Day 12)

把 users 集合中旧的单字段 `feishu_webhook` 迁移为新的多群结构
`feishu_webhooks`: [{"name": "默认群", "webhook": "..."}]。

幂等:已存在 `feishu_webhooks` 的用户会跳过,不会重复迁移。
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.mongo_writer import get_sync_client, DEFAULT_DB


def migrate() -> int:
    db = get_sync_client()[DEFAULT_DB]
    users = db["users"]
    migrated = 0
    for u in users.find({"feishu_webhook": {"$exists": True, "$ne": ""}}):
        uid = u["_id"]
        # 已经存在新字段且非空 -> 跳过
        existing = u.get("feishu_webhooks")
        if isinstance(existing, list) and existing:
            continue
        old = u.get("feishu_webhook", "")
        if not old:
            continue
        users.update_one(
            {"_id": uid},
            {
                "$set": {
                    "feishu_webhooks": [{"name": "默认群", "webhook": old}],
                    "updated_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat(),
                }
            },
        )
        print(f"[migrate] {u.get('username', uid)} -> feishu_webhooks (1 hook)")
        migrated += 1
    return migrated


if __name__ == "__main__":
    n = migrate()
    print(f"[done] migrated {n} user(s)")
