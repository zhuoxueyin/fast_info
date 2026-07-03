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
import os
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DEFAULT_LOG = "data/subs-scheduler.log"


def log(msg: str, log_path: Path):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line)
    log_path.parent.mkdir(exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def should_run_now(sub: dict, now: datetime) -> bool:
    """判断一个 sub 当前是否应该被触发"""
    if not sub.get("is_active", True):
        return False
    # 自定义间隔(分钟)
    interval_min = int(sub.get("interval_min", 0) or 0)
    last_run = sub.get("last_run_at")
    if interval_min > 0:
        if not last_run:
            return True
        try:
            last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            return now - last_dt >= timedelta(minutes=interval_min)
        except Exception:
            return True
    # cron 模式
    if not last_run:
        return True  # 从没跑过 → 跑一次
    try:
        last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
    except Exception:
        return False
    # 简单判断:last_run 距 now 超过 30 分钟才再跑(避免 cron 解析复杂度)
    return now - last_dt >= timedelta(minutes=30)


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
            r = await run_subscription(sub)
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