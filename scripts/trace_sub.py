"""trace run_subscription 到 MongoDB 层"""
import sys
sys.path.insert(0, "src")
from subscription import list_subscriptions

subs = list_subscriptions(user_id=None)
s = subs[1]

# 手动复刻 run_subscription 第一阶段
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

import asyncio

async def debug():
    db = AsyncIOMotorClient("mongodb://127.0.0.1:27017")["fastinfo"]
    keywords = s.get("keywords", [])
    sources = s.get("sources", ["all"])
    categories = s.get("categories", [])
    max_items = int(s.get("max_items", 10))
    lookback_hours = 48

    since = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    q = {"fetched_at": {"$gte": since}}
    if "all" not in sources:
        q["source"] = {"$in": sources}
    print(f"DB query: {q}")
    print(f"Keywords: {keywords}")
    print(f"Categories: {categories}")

    # 不带 categories 直接查
    items = []
    async for it in db["items"].find(q).sort("fetched_at", -1).limit(100):
        items.append(it)
    print(f"\n[阶段 1] DB query 返回 {len(items)} 条")

    # 关键词过滤
    kws_lower = [k.lower() for k in keywords]
    filtered = []
    for it in items:
        text = f"{it.get('title','')} {it.get('summary','')}".lower()
        if any(k in text for k in kws_lower):
            filtered.append(it)
    print(f"[阶段 2] 关键词过滤后 {len(filtered)} 条")
    for it in filtered[:5]:
        print(f"  - {it.get('title','')[:60]} [{it.get('source')} | {it.get('category')}]")

    # categories 过滤
    if categories:
        cat_filtered = []
        for it in filtered:
            cat = it.get("category", "")
            if any(c in cat for c in categories):
                cat_filtered.append(it)
        print(f"[阶段 3] categories 过滤后 {len(cat_filtered)} 条")
        for it in cat_filtered[:5]:
            print(f"  - [{it.get('category')}] {it.get('title','')[:60]}")

asyncio.run(debug())