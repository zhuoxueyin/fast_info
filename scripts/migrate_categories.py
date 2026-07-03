"""Day 4 数据迁移:把老 items.category 映射到 category_l1 (L2 留空)"""
import sys
sys.path.insert(0, r"d:\WORK\trae\fast_info\src")

from storage.mongo_writer import get_db
from taxonomy import normalize_l1

db = get_db()
total = db["items"].count_documents({})
no_l1 = db["items"].count_documents({"$or": [{"category_l1": {"$exists": False}}, {"category_l1": None}]})
print(f"total items={total}, without category_l1={no_l1}")

updated = 0
for doc in db["items"].find({}, {"_id": 1, "category": 1}):
    l1 = normalize_l1(doc.get("category"))
    db["items"].update_one({"_id": doc["_id"]}, {"$set": {"category_l1": l1, "category_l2": None}})
    updated += 1

print(f"updated: {updated}")

# 统计 L1 分布
agg = list(db["items"].aggregate([{"$group": {"_id": "$category_l1", "count": {"$sum": 1}}}]))
print("L1 分布:")
for r in sorted(agg, key=lambda x: -x["count"]):
    print(f"  {r['_id']:8s}: {r['count']}")