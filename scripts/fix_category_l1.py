import sys, os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from pymongo import MongoClient
from taxonomy import normalize_l1

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
client = MongoClient(MONGO_URL)
db = client["fastinfo"]

fixed = 0
bad = []
for doc in db["items"].find({}, {"_id": 1, "category": 1, "category_l1": 1, "title": 1}):
    correct = normalize_l1(doc.get("category"))
    current = doc.get("category_l1")
    if current != correct or (current and "/" in current):
        db["items"].update_one({"_id": doc["_id"]}, {"$set": {"category_l1": correct}})
        fixed += 1
        if "/" in str(current):
            bad.append((current, correct, doc.get("title", "")[:40]))

print(f"修复了 {fixed} 条记录")
print("带斜杠的错误记录示例:")
for b in bad[:10]:
    print(f"  {b[0]} → {b[1]}: {b[2]}")

from collections import Counter
cnt = Counter()
for doc in db["items"].find({}, {"category_l1": 1}):
    cnt[doc.get("category_l1", "其他")] += 1
print("\n修复后L1分类统计:")
for k, v in cnt.most_common():
    print(f"  {k}: {v}")
