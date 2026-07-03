"""验证 admin login 是否真返 role=admin"""
import httpx, json

r = httpx.post("http://127.0.0.1:8000/api/auth/login", json={"username": "admin", "password": "admin@2026"}, timeout=5)
print(f"login: {r.status_code}")
d = r.json()
print(f"  user = {json.dumps(d.get('user'), ensure_ascii=False)}")

print()
# 用 token 查 me
token = d.get("token")
h = {"Authorization": f"Bearer {token}"}
r = httpx.get("http://127.0.0.1:8000/api/auth/me", headers=h, timeout=5)
print(f"GET /api/auth/me: {r.status_code}")
print(f"  body = {json.dumps(r.json(), ensure_ascii=False)}")

print()
r = httpx.get("http://127.0.0.1:8000/api/admin/stats", headers=h, timeout=5)
print(f"GET /api/admin/stats: {r.status_code}")
if r.status_code != 200:
    print(f"  body = {r.text[:200]}")

# 直接查 mongo 里 admin 的 role
import sys
sys.path.insert(0, r"d:\WORK\trae\fast_info\src")
from storage.mongo_writer import get_db
db = get_db()
admin = db["users"].find_one({"username": "admin"})
print()
print(f"Mongo admin doc: _id={admin.get('_id')} role={admin.get('role')!r} username={admin.get('username')!r}")