import sys, os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
client = MongoClient(MONGO_URL)
db = client["fastinfo"]

print("=== admin 用户 ===")
admin = db["users"].find_one({"username": "admin"})
print(f"  _id: {admin.get('_id')!r} (type={type(admin.get('_id')).__name__})")
print(f"  role: {admin.get('role')}")

print("\n=== 所有订阅 ===")
for s in db["subscriptions"].find().sort("created_at", -1):
    print(f"  _id={s.get('_id')} user_id={s.get('user_id')!r} title={s.get('title')!r} active={s.get('is_active')}")

print("\n=== admin 的推送记录 ===")
count = db["subscriptions_delivered"].count_documents({"user_id": "u_admin"})
print(f"  user_id='u_admin': {count}")
count2 = db["subscriptions_delivered"].count_documents({"user_id": str(admin.get("_id"))})
print(f"  user_id=str(_id): {count2}")

print("\n=== 推送记录采样 ===")
for d in db["subscriptions_delivered"].find().limit(5):
    print(f"  user_id={d.get('user_id')!r} sub_id={d.get('subscription_id')} item_id={d.get('item_id')}")

print("\n=== inbox 查询测试 ===")
# 模拟 inbox 查询
admin_subs = list(db["subscriptions"].find({"user_id": "u_admin"}))
print(f"  admin subscriptions (user_id=u_admin): {len(admin_subs)}")
admin_subs2 = list(db["subscriptions"].find({"user_id": str(admin.get("_id"))}))
print(f"  admin subscriptions (user_id=str(_id)): {len(admin_subs2)}")
