"""Day 7 · 一次性回填脚本

回填规则:
  1) channels = [] / ['inbox'] 这种老默认 → 用 user.default_channels 替换
  2) channels 里含有不可用渠道(如 SMTP 没配时的 'email') → 过滤掉
  3) channels 空数组(fallback 后) → 至少填 ['inbox']

P1 原则:数据不规范直接修数据,不修代码去兜。

用法:
  python scripts/migrate_subscriptions_channels.py           # 干跑 (只显示)
  python scripts/migrate_subscriptions_channels.py --apply  # 真正写库
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# 让 src/ 在 path 上
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from storage.mongo_writer import get_sync_client  # noqa: E402
from notifier import get_feishu_webhooks  # noqa: E402

DEFAULT_DB = "fastinfo"


def _available_channels(user: dict) -> set[str]:
    """跟 settings._available_channels 同语义,防止循环 import。"""
    out = {"inbox"}
    if get_feishu_webhooks(user):
        out.add("feishu")
    if user.get("wechat_webhook"):
        out.add("wechat")
    if user.get("webhook_url"):
        out.add("webhook")
    if user.get("email") and user.get("smtp_user"):
        out.add("email")
    return out


def _normalize_channels(ch: list | None, user: dict) -> tuple[list, str]:
    """返回 (归一化后的 channels, 原因标签)。"""
    avail = _available_channels(user)
    defaults = user.get("default_channels") or ["inbox"]
    raw = list(ch or [])
    if not raw:
        # 空 / None / [] → 全用 user.default
        new = [c for c in defaults if c in avail] or ["inbox"]
        return new, "empty→defaults"
    if raw == ["inbox"]:
        # 老默认只剩 inbox → 用 user.default(用户已经在 settings 加了 feishu)
        new = [c for c in defaults if c in avail] or ["inbox"]
        if new == raw:
            return raw, "no-change"
        return new, "stale['inbox']→defaults"
    # 含不可用 → 过滤
    bad = [c for c in raw if c not in avail]
    if bad:
        new = [c for c in raw if c in avail]
        if not new:
            new = [c for c in defaults if c in avail] or ["inbox"]
            return new, f"all-bad→defaults({bad})"
        return new, f"filtered({bad})"
    return raw, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="默认干跑(只显示),传 --apply 才写库")
    ap.add_argument("--user", default="admin", help="只处理指定用户(默认 admin)")
    args = ap.parse_args()

    db = get_sync_client()[DEFAULT_DB]
    user = db["users"].find_one({"username": args.user})
    if not user:
        print(f"用户 {args.user} 不存在, 退出")
        return

    avail = _available_channels(user)
    defaults = user.get("default_channels") or ["inbox"]
    print(f"用户 {args.user}:")
    print(f"  default_channels = {defaults}")
    print(f"  available(根据 settings 实际可用) = {sorted(avail)}")
    print()

    # 限定只回填该用户的
    subs = list(db["subscriptions"].find({"user_id": str(user["_id"])}))
    print(f"扫到 {len(subs)} 条该用户订阅")
    print()

    changes: list[dict] = []
    no_change = 0
    for s in subs:
        old = s.get("channels")
        new, reason = _normalize_channels(old, user)
        if reason == "no-change" or new == old:
            no_change += 1
            continue
        changes.append({
            "id": str(s["_id"]),
            "title": s.get("title", ""),
            "before": old,
            "after": new,
            "reason": reason,
        })

    if not changes:
        print("✅ 所有订阅 channels 都是干净状态, 无需回填")
        return

    print(f"待回填 {len(changes)} 条 (无变化 {no_change} 条):")
    print("-" * 80)
    for c in changes:
        print(f"  [{c['id'][:8]}] {c['title'][:30]:30s}")
        print(f"      before: {c['before']}")
        print(f"      after : {c['after']}")
        print(f"      reason: {c['reason']}")
    print("-" * 80)

    if not args.apply:
        print()
        print("⚠️  默认干跑, 传 --apply 才会真正写库")
        return

    # 写库
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for c in changes:
        res = db["subscriptions"].update_one(
            {"_id": _oid(c["id"])},
            {"$set": {"channels": c["after"], "updated_at": now,
                      "_migrated_day7": True}},
        )
        if res.modified_count:
            updated += 1
    print()
    print(f"✅ 写库完成:更新 {updated} 条")


def _oid(s: str):
    from bson import ObjectId
    return ObjectId(s)


if __name__ == "__main__":
    main()
