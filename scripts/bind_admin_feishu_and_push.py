"""Day 7 v0.4.1 · admin 飞书渠道一键测试脚本

你跑这个就行,做 3 件事:
1. 找 admin 用户
2. 给 admin 配飞书渠道(feishu_open_id = 你当前跟 OpenClaw 聊天的 open_id)
3. 触发所有 admin 的订阅推送

跑法:
    $env:LARK_APP_ID="cli_xxx"; $env:LARK_APP_SECRET="***"
    python scripts/bind_admin_feishu_and_push.py

输出:
    [1] MongoDB 通了 ...
    [2] Admin 用户: username=admin, _id=...
    [3] ✓ admin 配 feishu
    [4] active 订阅: N 条
    [5] 推送触发结果: {...}

预期效果:你飞书 DM 收到 N 张推送卡片(每条订阅一张)。
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.mongo_writer import get_sync_client
from subscription import run_subscription_sync

DB = "fastinfo"

# 你的飞书 open_id(metadata 里来的)
ADMIN_DM_OPEN_ID = "ou_6fbcd70ebe9c84b418e0f1fd4408ca23"


def main():
    # === 0. LARK env 检查 ===
    if not os.environ.get("LARK_APP_ID") or not os.environ.get("LARK_APP_SECRET"):
        print("[0] ❌ LARK_APP_ID / LARK_APP_SECRET 未配置")
        print("    先 PowerShell 设:")
        print('      $env:LARK_APP_ID="cli_xxx"; $env:LARK_APP_SECRET="***"')
        sys.exit(1)

    # === 1. 连 Mongo ===
    try:
        db = get_sync_client()[DB]
        info = db.command("ping")
        print(f"[1] ✓ MongoDB (ping={info.get('ok')})")
    except Exception as e:
        print(f"[1] ❌ MongoDB 不通: {type(e).__name__}: {e}")
        sys.exit(1)

    # === 2. 找 admin 用户 ===
    admins = list(db.users.find({"role": "admin"}))
    if not admins:
        admins = list(db.users.find().limit(5))
        print(f"[2] ⚠️ 没找到 role=admin,取前 {len(admins)} 个用户中第 1 个:")
        for a in admins:
            print(f"    - {a.get('username')} role={a.get('role')}")
        if not admins:
            sys.exit(2)
    admin = admins[0]
    admin_id = admin["_id"]
    admin_in_db = admin if isinstance(admin_id, str) else admin  # ObjectId
    print(f"[2] ✓ Admin: username={admin.get('username')}, _id={admin_id}")

    # === 3. 给 admin 配飞书 ===
    db.users.update_one(
        {"_id": admin["_id"]},
        {"$set": {
            "feishu_open_id": ADMIN_DM_OPEN_ID,
            "feishu_union_id": ADMIN_DM_OPEN_ID,
            "feishu_name": "用户763485",
            "feishu_email": admin.get("email", ""),
            "feishu_bind_at": datetime.now(timezone.utc).isoformat(),
            "default_channels": ["inbox", "feishu_dm"],
        }},
    )
    print(f"[3] ✓ admin 配 feishu: open_id={ADMIN_DM_OPEN_ID}, default_channels=[inbox, feishu_dm]")

    # === 4. 列 admin 的订阅 ===
    subs = list(db.subscriptions.find({"user_id": str(admin_id) if not isinstance(admin_id, str) else admin_id, "is_active": True}))
    # fastInfo subscriptions.user_id 可能是 str 也可能是其他 ID — 用宽松查询
    if not subs:
        subs = list(db.subscriptions.find({"is_active": True}).limit(20))
    print(f"[4] active 订阅: {len(subs)} 条")
    for s in subs[:5]:
        print(f"    - {str(s.get('_id')):<26} {s.get('title')[:18]:<18} channels={s.get('channels')}")

    # === 5. 触发每个订阅 ===
    print(f"\n[5] 触发推送 ...")
    results = []
    for s in subs:
        # 修 channels:确保含 feishu_dm
        chs = list(dict.fromkeys(list(s.get("channels") or []) + ["feishu_dm"]))
        db.subscriptions.update_one(
            {"_id": s["_id"]},
            {"$set": {"channels": chs, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        s["channels"] = chs
        # 跑订阅
        try:
            r = run_subscription_sync(s)
            results.append({"sub_id": str(s["_id"]), "title": s.get("title"), **r})
            mark = "✓" if r.get("delivered", 0) > 0 else "·"
            print(f"    {mark} {s.get('title'):<20} scanned={r.get('scanned')} matched={r.get('matched')} delivered={r.get('delivered')}")
        except Exception as e:
            results.append({"sub_id": str(s["_id"]), "title": s.get("title"), "error": str(e)})
            print(f"    ✗ {s.get('title'):<20} err={type(e).__name__}: {e}")

    # === 6. 总结 ===
    delivered_total = sum(r.get("delivered", 0) for r in results if "delivered" in r)
    print(f"\n[6] 总推送: {delivered_total} 条")
    print(f"    请检查飞书 DM(用户763485),应该收到 {delivered_total} 张绿色卡片")
    print(f"    如果收到 = 链路通 ✅")
    print(f"    如果没收到:看上方 [5] 是否有 [feishu_dm] → ou_xxx... ✓ 输出")


if __name__ == "__main__":
    main()
