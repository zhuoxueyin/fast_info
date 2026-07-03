"""清 subscriptions_delivered"""
import sys
sys.path.insert(0, "src")
from storage.mongo_writer import get_sync_client

db = get_sync_client()["fastinfo"]
res = db["subscriptions_delivered"].delete_many({"subscription_id": "6a43dca58d9ebd69e9eb6dce"})
print(f"清理 {res.deleted_count} 条推送记录")