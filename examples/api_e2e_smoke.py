"""
fastInfo · API 端到端 smoke 测试
=================================

用 fastapi TestClient 跑全链路:
    1. healthz / 根信息 / stats
    2. 注册 / 登录 / me (鉴权流)
    3. 公开读:search / today / hot
    4. 鉴权写:建订阅 / 跑订阅 / 删除订阅
    5. 鉴权写:ingest/run (实际触发抓取+摘要,会写 LLM,建议带 MMX_API_KEY)

适合:
    - 部署后健康自检
    - PR 回归
    - 新人 5 分钟验证 API 真能跑

跑法:
    python examples/api_e2e_smoke.py              # 默认 127.0.0.1:8000
    python examples/api_e2e_smoke.py --port 8080  # 自定义
    python examples/api_e2e_smoke.py --no-ingest  # 跳过真实抓取

注:本机如果有 Clash / v2rayN 之类代理,会被 httpx 自动读 HTTP_PROXY
    把 127.0.0.1 流量劫到 7892 返 502。本脚本启动时会自动清掉代理。
"""
import argparse
import os
import sys
from pathlib import Path

# 清代理,避免 httpx 把 127.0.0.1 流量劫到 Clash 返 502
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)


def _check():
    """内部检查:必须先 ensure_indexes + 有 Mongo 连通"""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    try:
        from storage.mongo_writer import get_sync_client
        get_sync_client().admin.command("ping")
    except Exception as e:
        print(f"  ✗ MongoDB 不可达: {e}")
        print("  提示: 确认本机 MongoDB 已启动(默认 27017)")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    # 优先 CLI --port;其次 env(FASTINFO_API_PORT);最后本地默认 8000
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("FASTINFO_API_PORT", "8000")),
    )
    parser.add_argument("--no-ingest", action="store_true", help="跳过 ingest 真实抓取(避免烧 LLM 额度)")
    args = parser.parse_args()

    _check()

    from fastapi.testclient import TestClient
    from api.app import create_app

    app = create_app()
    client = TestClient(app)

    print("=" * 60)
    print(f" fastInfo · API 端到端 smoke  (port={args.port})")
    print("=" * 60)

    passed = 0
    failed = 0

    def step(name, ok, detail=""):
        nonlocal passed, failed
        mark = "✓" if ok else "✗"
        print(f"  {mark} {name:35s} {detail}")
        if ok:
            passed += 1
        else:
            failed += 1

    # ---- 1. 健康检查 ----
    print("\n[1] 健康检查")
    r = client.get("/healthz")
    step("/healthz", r.status_code == 200, f"status={r.status_code} body={r.text[:60]}")

    r = client.get("/")
    step("/", r.status_code == 200, f"status={r.status_code}")

    r = client.get("/api/stats")
    step("/api/stats", r.status_code == 200, f"items={r.json().get('total_items')}")

    # ---- 2. 公开读 ----
    print("\n[2] 公开读")
    r = client.get("/api/search?q=AI", timeout=15)
    step("/api/search?q=AI", r.status_code == 200, f"hits={r.json().get('total')}")

    r = client.get("/api/today?limit=3", timeout=15)
    step("/api/today?limit=3", r.status_code == 200, f"items={len(r.json().get('items', []))}")

    r = client.get("/api/hot?limit=3", timeout=15)
    step("/api/hot?limit=3", r.status_code == 200, f"items={len(r.json().get('items', []))}")

    r = client.get("/api/items?ids=", timeout=15)
    step("/api/items?ids= (空 -> 200 空列表)", r.status_code == 200, f"status={r.status_code} items={len(r.json())}")

    # 批量查真实 id(取 today 前 1 条)
    r = client.get("/api/today?limit=1", timeout=15)
    if r.status_code == 200 and r.json().get("items"):
        iid = r.json()["items"][0]["id"]
        r = client.get(f"/api/items?ids={iid}", timeout=15)
        step(f"/api/items?ids={iid[:8]}...", r.status_code == 200, f"items={len(r.json())}")
    else:
        step("/api/items 批量", False, "no items")

    # ---- 3. 鉴权流(注册 → 登录 → me)----
    # 固定用户名,跑完在 finally 里清理,避免积累 smoke_* 孤儿账号
    print("\n[3] 鉴权流 (register → login → me)")
    username = "smoke_e2e"

    r = client.post("/api/auth/register", json={"username": username, "password": "sm0ke-pass"})
    step(f"register({username})", r.status_code in (200, 201, 400), f"status={r.status_code}")
    if r.status_code == 400 and "已存在" in r.text:
        print(f"     (用户已存在,继续登录)")

    r = client.post("/api/auth/login", json={"username": username, "password": "sm0ke-pass"})
    step("login", r.status_code == 200, f"status={r.status_code}")
    if r.status_code != 200:
        print(f"  ✗ 登录失败,中止后续步骤: {r.text[:200]}")
        print(f"\n[结果] passed={passed} failed={failed}")
        sys.exit(1)
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/auth/me", headers=headers)
    step("/api/auth/me", r.status_code == 200, f"user={r.json().get('username')}")

    # ---- 4. 鉴权写:订阅 ----
    print("\n[4] 鉴权写 (subscribe / run / list / delete)")
    nl = "每天 9 点看 AI 资讯"
    r = client.post(
        "/api/subs",
        headers=headers,
        json={"title": f"smoke-test-{suffix}", "nl_query": nl, "max_items": 3},
        timeout=30,
    )
    step("POST /api/subs (NL)", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:200]}")
    if r.status_code in (200, 201):
        sub_id = r.json().get("id") or r.json().get("subscription", {}).get("id")
    else:
        sub_id = None

    r = client.get("/api/subs", headers=headers)
    step("GET /api/subs", r.status_code == 200, f"total={r.json().get('total')}")

    if sub_id:
        r = client.post(f"/api/subs/{sub_id}/run", headers=headers, timeout=30)
        step("POST /api/subs/{id}/run", r.status_code == 200, f"body={r.text[:200]}")

        r = client.delete(f"/api/subs/{sub_id}", headers=headers)
        step("DELETE /api/subs/{id}", r.status_code in (200, 204), f"status={r.status_code}")

    # ---- 5. ingest(可选,会真调 LLM)----
    if args.no_ingest:
        print("\n[5] ingest (skipped, --no-ingest)")
    else:
        print("\n[5] ingest (会真调 LLM,几秒到几十秒)")
        r = client.post("/api/ingest/run?limit=2", headers=headers, timeout=120)
        step("POST /api/ingest/run", r.status_code == 200, f"body={r.text[:200]}")

    # ---- 总结 ----
    print("\n" + "=" * 60)
    print(f" [结果] passed={passed}  failed={failed}")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)


def _cleanup_smoke_user():
    """跑完清理 smoke_e2e 用户及其订阅/推送记录,避免积累垃圾账号"""
    try:
        from storage.mongo_writer import get_db
        db = get_db()
        u = db["users"].find_one({"username": "smoke_e2e"})
        if not u:
            return
        uid = u["_id"]
        uid_variants = [str(uid), uid]
        db["subscriptions_delivered"].delete_many({"user_id": {"$in": uid_variants}})
        db["subscriptions"].delete_many({"user_id": {"$in": uid_variants}})
        db["users"].delete_one({"_id": uid})
        print("\n[cleanup] 已清理 smoke_e2e 测试用户")
    except Exception as e:
        print(f"\n[cleanup] 清理 smoke_e2e 失败(不影响结果): {e}")


if __name__ == "__main__":
    try:
        main()
    finally:
        _cleanup_smoke_user()
