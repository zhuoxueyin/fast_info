"""debug: 为什么 subs run scanned=0"""
import asyncio, sys
sys.path.insert(0, "src")
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    db = AsyncIOMotorClient("mongodb://127.0.0.1:27017")["fastinfo"]
    since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    print(f"since: {since}")
    print(f"now:   {datetime.now(timezone.utc).isoformat()}")
    print()

    # 1. 最近 48h 的 items 数量
    count = await db["items"].count_documents({"fetched_at": {"$gte": since}})
    print(f"[1] items in last 48h: {count}")

    # 2. 关键词 AI / 人工智能 / 机器学习 命中数
    for kw in ["AI", "人工智能", "机器学习"]:
        q = {"$or": [
            {"title": {"$regex": kw, "$options": "i"}},
            {"summary": {"$regex": kw, "$options": "i"}},
        ]}
        c = await db["items"].count_documents(q)
        print(f"[2] keyword '{kw}' matches: {c}")

    # 3. 查最新一条
    one = await db["items"].find_one(sort=[("fetched_at", -1)])
    if one:
        title = one.get("title", "")[:60]
        fa = one.get("fetched_at", "?")
        print(f"\n[3] latest item: '{title}' | fetched_at={fa}")

    # 4. 实测订阅查询的 query 形态
    keywords = ["人工智能", "AI", "机器学习"]
    lookback_hours = 48
    since_q = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    q = {"fetched_at": {"$gte": since_q}}
    print(f"\n[4] sub query: {q}")
    cnt = await db["items"].count_documents(q)
    print(f"    items that pass time filter: {cnt}")

    # 5. 实测 cursor 能不能 async for
    cursor = db["items"].find(q).sort("fetched_at", -1).limit(10 * 5)
    n = 0
    async for it in cursor:
        n += 1
    print(f"\n[5] cursor yielded {n} items")

asyncio.run(main())