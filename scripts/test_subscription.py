"""
W2-C 测试:NL 解析 + 订阅创建 + 立即执行
========================================
"""
import asyncio
import sys
import os
sys.path.insert(0, "src")

from subscription import (
    parse_nl_to_subscription,
    save_subscription,
    list_subscriptions,
    run_subscription,
    update_subscription_after_run,
)
from storage.mongo_writer import count_items


async def main():
    print("=" * 60)
    print("  [1/4] NL 解析订阅")
    print("=" * 60)
    nl_query = "帮我每天看 AI 推理模型相关论文,中文优先,每周一上午 9 点发邮件"
    sub = await parse_nl_to_subscription(nl_query)
    print(f"  ✓ 解析完成")
    print(f"    title:        {sub['title']}")
    print(f"    keywords:     {sub['keywords']}")
    print(f"    sources:      {sub['sources']}")
    print(f"    categories:   {sub['categories']}")
    print(f"    cron_expr:    {sub['cron_expr']}")
    print(f"    next_run_at:  {sub['next_run_at']}")
    print()

    print("=" * 60)
    print("  [2/4] 保存到 MongoDB")
    print("=" * 60)
    sub_id = save_subscription(sub)
    print(f"  ✓ MongoDB _id: {sub_id}")
    print()

    print("=" * 60)
    print("  [3/4] 列出所有 active 订阅")
    print("=" * 60)
    for s in list_subscriptions():
        print(f"  - {s.get('title','?')[:20]:<20} | {s.get('cron_expr','?'):<15} | next={s.get('next_run_at','?')[:16]}")
    print()

    print("=" * 60)
    print("  [4/4] 立即跑一次这个订阅")
    print("=" * 60)
    sub = list_subscriptions()[0]  # 取刚创建的
    print(f"  keywords: {sub['keywords']}")
    print(f"  sources: {sub['sources']}")
    result = await run_subscription(sub)
    print(f"  ✓ 结果: {result}")
    print()

    update_subscription_after_run(sub_id, success=True)
    print(f"  ✓ updated subscription status")
    print()

    print(f"  MongoDB items 总数: {count_items()}")


if __name__ == "__main__":
    asyncio.run(main())