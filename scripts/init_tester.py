"""一次性初始化测试账号 tester。用 admin 同样的密码格式方便记忆。"""
import sys
sys.path.insert(0, r"D:\WORK\trae\fast_info\src")
from storage.mongo_writer import get_sync_client
from auth import register, hash_password

db = get_sync_client()["fastinfo"]

TEST_USER = "tester"
TEST_PASS = "Tester@2026"

existing = db["users"].find_one({"username": TEST_USER})
if existing:
    print(f"测试账号 {TEST_USER!r} 已存在,不再创建. _id={existing['_id']}")
    print(f"  role={existing.get('role')} plan={existing.get('plan')}")
else:
    u = register(TEST_USER, TEST_PASS, email=f"{TEST_USER}@local")
    print(f"✅ 测试账号已创建:")
    print(f"   username = {u['username']}")
    print(f"   email    = {u.get('email')}")
    print(f"   _id      = {u['_id']}")
    print(f"   password = {TEST_PASS}    # Tester@2026")
