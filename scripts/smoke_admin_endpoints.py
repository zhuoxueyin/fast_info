"""smoke monitoring endpoint through API"""
import sys
sys.path.insert(0, "src")
import httpx
from pathlib import Path

auth = httpx.post("http://127.0.0.1:8000/api/auth/login",
                  json={"username": "admin", "password": "Admin@2026!"},
                  timeout=10)
print("LOGIN:", auth.status_code, "tok len=", len(auth.json().get("token") or ""))
token = auth.json()["token"]
Path("data/.session.json").write_text(token, encoding="utf-8")

mon = httpx.get("http://127.0.0.1:8000/api/admin/monitoring",
                headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"MON status={mon.status_code}")
if mon.status_code == 200:
    j = mon.json()
    print("overall:", j.get("overall"))
    for k, v in j.get("components", {}).items():
        status = v.get("status")
        detail = v.get("detail", "")[:80]
        print(f"  [{k:18}] {status:6} {detail}")

# 现在 restart daemon
r = httpx.post("http://127.0.0.1:8000/api/admin/source/restart-daemon",
               headers={"Authorization": f"Bearer {token}"}, timeout=15)
print(f"\nRESTART status={r.status_code}")
print("body:", r.text)
