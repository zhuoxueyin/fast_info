"""
fastInfo · 订阅调度守护进程 (Day 4)

职责:
- 每分钟扫一次 subscriptions 集合
- 对到期的 sub(interval_min 到期或 cron 命中)自动调用 run_subscription
- 同时支持 sources 启用开关

与 ingest_daemon 不同:
- ingest_daemon:抓数据 + 摘要 (对所有用户共享的 items)
- subs_scheduler:读 items → 推送 (对每个用户做匹配 + 推送)

跑法:
    python scripts/subs_scheduler.py                 # 默认每 60s 检查一次
    python scripts/subs_scheduler.py --interval 30  # 30s 检查一次
"""
from __future__ import annotations
import argparse
import asyncio
import io
import os
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Day 10 fix:Windows 默认 GBK stdout,任何 print 含 ✗/✓ 必炸。
# 强制切到 UTF-8 防止 scheduler 子进程死循环(同 api_server.py 同样模式)。
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env(本地开发 + Docker volume 挂 /app/.env 都覆盖)
from _env import load_env
load_env()

DEFAULT_LOG = "data/subs-scheduler.log"


def log(msg: str, log_path: Path):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line)
    log_path.parent.mkdir(exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _due_at(sub: dict) -> datetime | None:
    """推导该订阅应触发的时间点。

    优先使用数据库里持久化的 `next_run_at`。
    老数据缺字段时,再退化到 `last_run_at/created_at + cron|interval` 推导。
    """
    next_dt = _parse_iso_dt(sub.get("next_run_at"))
    if next_dt is not None:
        return next_dt
    base_dt = _parse_iso_dt(sub.get("last_run_at")) or _parse_iso_dt(sub.get("created_at"))
    if base_dt is None:
        return None
    try:
        from subscription import compute_next_run_at
        return compute_next_run_at(sub, base_dt)
    except Exception:
        return None


def should_run_now(sub: dict, now: datetime) -> bool:
    """判断一个 sub 当前是否应该被触发"""
    if not sub.get("is_active", True):
        return False
    # Day 9:短期订阅 expires_at 过期 → 自动停(写库一次性)
    expires_at = sub.get("expires_at")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if now >= exp_dt:
                # 过期了 → 同步标记 is_active=False,scheduler 下次 tick 跳过
                try:
                    from storage.mongo_writer import get_sync_client, DEFAULT_DB
                    from bson import ObjectId
                    get_sync_client()[DEFAULT_DB]["subscriptions"].update_one(
                        {"_id": ObjectId(str(sub["_id"]))},
                        {"$set": {"is_active": False, "expired_at": now.isoformat()}},
                    )
                    print(f"  ⏰ [{sub.get('title','?')[:20]}] 短期订阅已过期,自动停")
                except Exception:
                    pass
                return False
        except Exception:
            pass
    due_at = _due_at(sub)
    if due_at is None:
        return False
    return now >= due_at


async def tick():
    """一次 tick:扫描所有订阅,触发到期的"""
    from storage.mongo_writer import get_async_client, DEFAULT_DB
    from subscription import run_subscription, update_subscription_after_run
    from bson import ObjectId

    db = get_async_client()[DEFAULT_DB]
    now = datetime.now(timezone.utc)
    triggered = 0
    skipped = 0
    failed = 0
    async for sub in db["subscriptions"].find({"is_active": True}):
        if not should_run_now(sub, now):
            skipped += 1
            continue
        try:
            # Day 9:scheduler 触发 = trigger='schedule',operator='auto'
            r = await run_subscription(sub, trigger="schedule", operator="auto")
            triggered += 1
            sid = str(sub["_id"])
            update_subscription_after_run(sid, success=True)
            print(f"  ✓ [{sub.get('title','?')[:20]}] scan={r.get('scanned')} matched={r.get('matched')} delivered={r.get('delivered')}")
        except Exception as e:
            failed += 1
            traceback.print_exc()
            try:
                update_subscription_after_run(str(sub["_id"]), success=False, error=str(e)[:100])
            except Exception:
                pass

    print(f"  -> triggered={triggered} skipped={skipped} failed={failed}")


async def main_loop(args, log_path: Path):
    log(f"subs_scheduler start (interval={args.interval}s)", log_path)
    while True:
        try:
            await tick()
        except Exception as e:
            log(f"tick err: {e}", log_path)
            traceback.print_exc()
        await asyncio.sleep(args.interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60, help="检查间隔秒")
    parser.add_argument("--once", action="store_true", help="只跑一次就退出")
    parser.add_argument("--log", default=DEFAULT_LOG)
    args = parser.parse_args()
    log_path = Path(args.log)

    if args.once:
        asyncio.run(tick())
        return

    try:
        asyncio.run(main_loop(args, log_path))
    except KeyboardInterrupt:
        log("subs_scheduler stopped by user", log_path)


if __name__ == "__main__":
    main()
