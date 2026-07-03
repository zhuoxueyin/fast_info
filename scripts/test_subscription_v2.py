"""
W2-C 测试 v2:用宽关键词触发实际匹配
"""
import asyncio
import sys
sys.path.insert(0, "src")

from subscription import save_subscription, list_subscriptions, run_subscription, update_subscription_after_run
from storage.mongo_writer import count_items
from datetime import datetime, timezone


async def main():
    # 直接构造一个宽关键词订阅,验证执行链路
    now = datetime.now(timezone.utc)
    sub = {
        "user_id": "local",
        "title": "AI 资讯每日速递",
        "nl_query": "帮我每天看 AI 相关资讯",
        "keywords": ["AI", "模型", "智能", "OpenAI", "GPT", "Google", "Anthropic", "DeepSeek", "Claude", "芯片"],
        "sources": ["all"],
        "categories": ["AI", "科技"],
        "languages": ["zh", "en"],
        "cron_expr": "0 9 * * *",
        "timezone": "Asia/Shanghai",
        "delivery": "in_app",
        "summary_style": "short",
        "max_items": 10,
        "is_active": True,
        "last_run_at": None,
        "next_run_at": now.isoformat(),
        "run_count": 0,
        "error_count": 0,
        "last_error": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    sub_id = save_subscription(sub)
    print(f"✓ 创建订阅: {sub['title']}, id={sub_id}")

    # 先清空 items 让 run 能匹配到
    from storage.mongo_writer import get_sync_client
    db = get_sync_client()["fastinfo"]
    deleted = db["items"].delete_many({}).deleted_count
    print(f"✓ 清空 items ({deleted} 条)")

    # 跑这个订阅
    result = await run_subscription(sub)
    print(f"✓ 执行结果: {result}")
    print(f"✓ MongoDB items 总数: {count_items()}")

    update_subscription_after_run(sub_id, success=True)
    print(f"✓ 已更新订阅状态")

    # 显示最新的 3 条
    print()
    print("=" * 60)
    print("  最新入库 3 条:")
    print("=" * 60)
    for r in db["items"].find().sort("fetched_at", -1).limit(3):
        print(f"  - [{r.get('category', '?')}] {r.get('title', '')[:60]}")
        print(f"    摘要: {r.get('summary', '')[:80]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())