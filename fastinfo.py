"""
fastInfo · 统一 CLI
====================

用法:
    python -m fastinfo search <query> [--limit 10] [--source ifanr]
    python -m fastinfo today [--limit 20] [--category AI]
    python -m fastinfo subscribe "<NL 描述>"
    python -m fastinfo subs list
    python -m fastinfo subs run <id>
    python -m fastinfo subs delete <id>
    python -m fastinfo stats
    python -m fastinfo ingest [--limit 8] [--all]   # 跑一次抓取+摘要

Examples:
    $ python -m fastinfo search "AI 推理"
    $ python -m fastinfo today --category AI --limit 5
    $ python -m fastinfo subscribe "帮我每天看 AI 推理模型相关论文,中文优先"
    $ python -m fastinfo subs list
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from storage.mongo_writer import (
    get_sync_client, ensure_indexes, count_items, stats,
    upsert_item_async, get_done_urls,
)
from retrieval import search, hybrid_search
from subscription import (
    parse_nl_to_subscription, save_subscription,
    list_subscriptions, get_subscription, run_subscription,
    update_subscription_after_run,
)
from crawler.rss_collector import fetch_all
from llm.model_registry import build_default_registry
from auth import current_user


def _fmt_item(item: dict, show_score: bool = False) -> str:
    score = item.get("score", 0)
    score_part = f" [{score:.1f}]" if show_score and score else ""
    title = (item.get("title") or "")[:60]
    summary = item.get("summary") or ""
    cat = item.get("category") or "其他"
    # published_at / fetched_at 都可能 None,三层 fallback
    pub_at = item.get("published_at") or item.get("fetched_at") or ""
    pub = pub_at[:10] or "????-??-??"
    if not summary:
        return f"  {score_part} {title}\n     [{cat}] {pub}"
    return (
        f"  {score_part} {title}\n"
        f"     [{cat}] {pub} | {summary[:120]}{'...' if len(summary) > 120 else ''}"
    )


# ============================================================
# 子命令
# ============================================================

def cmd_search(args):
    results = hybrid_search(args.query, limit=args.limit, source=args.source, category=args.category)
    if not results:
        print(f"  (无结果) 关键词: '{args.query}'")
        return
    print(f"  找到 {len(results)} 条:")
    for r in results:
        print(_fmt_item(r, show_score=True))


def cmd_today(args):
    db = get_sync_client()["fastinfo"]
    from storage.mongo_writer import get_sync_client as g
    q: dict = {}
    if args.category:
        q["category"] = args.category
    if args.source:
        q["source"] = args.source
    cursor = db["items"].find(q).sort("fetched_at", -1).limit(args.limit)
    items = list(cursor)
    if not items:
        print("  (今日无内容,可先跑: python -m fastinfo ingest)")
        return
    print(f"  最近 {len(items)} 条:")
    for it in items:
        print(_fmt_item(it))


def cmd_hot(args):
    """今日热点:最近 N 小时 + relevance ≥ threshold 的内容"""
    from datetime import datetime, timezone, timedelta
    db = get_sync_client()["fastinfo"]
    threshold = args.threshold
    since = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).isoformat()
    q: dict = {
        "fetched_at": {"$gte": since},
        "relevance": {"$gte": threshold},
    }
    if args.category:
        q["category"] = args.category
    cursor = db["items"].find(q).sort([("relevance", -1), ("fetched_at", -1)]).limit(args.limit)
    items = list(cursor)
    if not items:
        print(f"  (近 {args.hours}h 无相关度 ≥ {threshold} 的热点)")
        return
    print(f"  今日热点(近 {args.hours}h,relevance ≥ {threshold}):")
    for i, it in enumerate(items, 1):
        rel = it.get("relevance", 0)
        cat = it.get("category", "其他")
        src = it.get("source", "?")
        title = it.get("title", "")[:50]
        summary = it.get("summary", "")[:80]
        pub_at = it.get("published_at") or it.get("fetched_at") or ""
        pub = pub_at[:10] or "????-??-??"
        print(f"  #{i:<3} [{rel:.2f}|{cat}|{src}|{pub}] {title}")
        if summary:
            print(f"        {summary}{'...' if len(it.get('summary',''))>80 else ''}")
        print()


def cmd_subscribe(args):
    nl = args.nl
    print(f"  解析 NL: {nl}")
    sub = asyncio.run(parse_nl_to_subscription(nl))
    print(f"  ✓ 解析完成: title='{sub['title']}' cron={sub['cron_expr']}")
    sub_id = save_subscription(sub)
    print(f"  ✓ 创建订阅 id={sub_id}")


def cmd_subs_list(args):
    subs = list_subscriptions()
    if not subs:
        print("  (无订阅)")
        return
    for s in subs:
        sid = str(s.get("_id", ""))
        title = s.get("title", "?")[:20]
        cron = s.get("cron_expr", "?")
        next_run = (s.get("next_run_at") or "")[:16]
        runs = s.get("run_count", 0)
        errs = s.get("error_count", 0)
        active = "✓" if s.get("is_active") else "✗"
        print(f"  {active} {sid:<26} | {title:<20} | {cron:<15} | run={runs} err={errs} | next={next_run}")


def cmd_subs_run(args):
    from subscription import run_subscription_sync
    sub = get_subscription(args.id)
    if not sub:
        print(f"  ✗ 订阅 {args.id} 不存在")
        return
    print(f"  跑订阅: {sub.get('title')} (keywords={sub.get('keywords')[:3]}...)")
    result = run_subscription_sync(sub)
    print(f"  ✓ 结果: {result}")
    update_subscription_after_run(args.id, success=True)

    if args.verbose and result.get("delivered"):
        # 显示推送的 item 标题(从 subscriptions_delivered 查)
        from storage.mongo_writer import get_sync_client
        from storage.mongo_writer import DEFAULT_DB as _DB
        delivered = list(get_sync_client()[_DB]["subscriptions_delivered"].find(
            {"subscription_id": str(sub["_id"])}
        ).sort("delivered_at", -1).limit(result["delivered"]))
        print(f"  推送:")
        for d in delivered:
            print(f"    - item_id={d['item_id']} @ {d['delivered_at'][:19]}")


def cmd_subs_delete(args):
    from bson import ObjectId
    db = get_sync_client()["fastinfo"]
    res = db["subscriptions"].delete_one({"_id": ObjectId(args.id)})
    print(f"  ✓ 删除 {res.deleted_count} 条订阅")


def cmd_stats(args):
    s = stats()
    print(f"  Items 总数: {s['total']}")
    print(f"  按源:")
    for src in s["by_source"]:
        print(f"    {src['_id']:<20} {src['count']:>4}")
    print(f"  按分类:")
    for c in s["by_category"]:
        print(f"    {c['_id']:<20} {c['count']:>4}")


def cmd_register(args):
    from auth import register, clear_session
    clear_session()
    print(f"  注册用户: {args.username}")
    try:
        u = register(args.username, args.password, args.email or "")
        print(f"  ✓ 注册成功: {u['username']} (plan={u['plan']}, role={u['role']})")
        # 自动登录
        from auth import login, save_session
        token, view = login(args.username, args.password)
        save_session(token, view)
        print(f"  ✓ 自动登录,会话已保存到 data/.session.json")
    except ValueError as e:
        print(f"  ✗ {e}")


def cmd_login(args):
    from auth import login, save_session
    try:
        token, view = login(args.username, args.password)
        save_session(token, view)
        print(f"  ✓ 登录成功: {view['username']} (plan={view['plan']})")
        print(f"  会话文件: data/.session.json")
    except ValueError as e:
        print(f"  ✗ {e}")


def cmd_logout(args):
    from auth import clear_session
    clear_session()
    print("  ✓ 已登出")


def cmd_whoami(args):
    from auth import current_user, load_session
    u = current_user()
    sess = load_session()
    if not u:
        print("  (未登录)")
        return
    print(f"  当前用户: {u['username']}")
    print(f"  user_id:  {u['id']}")
    print(f"  plan:     {u['plan']}")
    print(f"  role:     {u['role']}")
    if sess and sess.get("payload", {}).get("exp"):
        exp = sess["payload"]["exp"]
        from datetime import datetime, timezone
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        print(f"  会话到期: {exp_dt.isoformat()}")


def cmd_ingest(args):
    """抓取 + 摘要 + 入库(端到端)"""
    print("  确保索引...")
    ensure_indexes()
    print(f"  现有 {count_items()} 条")
    print(f"  抓 RSS(每源 {args.limit} 条)...")

    items = asyncio.run(fetch_all(limit_per_source=args.limit))
    print(f"  共抓 {len(items)} 条")
    if args.all:
        from storage.mongo_writer import get_sync_client as g
        get_sync_client()["fastinfo"]["items"].delete_many({})
        print("  ✓ 已清空 items(--all)")
    done = get_done_urls()
    new_items = [it for it in items if it.id not in done]
    print(f"  新增 {len(new_items)} 条")

    if not new_items:
        print("  ✓ 无新内容")
        return
    if not __import__("os").environ.get("MMX_API_KEY"):
        print("  ✗ MMX_API_KEY 未设置")
        return

    # 把整个异步流程塞进一个 asyncio.run(不能嵌套)
    asyncio.run(_run_ingest_async(new_items))


async def _run_ingest_async(new_items: list):
    registry = build_default_registry()
    sem = asyncio.Semaphore(3)
    completed = 0
    failed = 0

    import re as _re
    import json as _json
    async def one(item):
        nonlocal completed, failed
        async with sem:
            messages = [
                {"role": "system", "content": "中文资讯编辑。生成 120-180 字摘要 + 2-4 要点 + 分类 + 相关度。严格 JSON 输出,无 markdown 包裹。"},
                {"role": "user", "content": f"标题: {item.title}\n来源描述: {item.summary_html[:300]}"},
            ]
            try:
                result = await registry.get("short_summary").chat(messages, max_tokens=600, temperature=0.3)
                content = result["choices"][0]["message"]["content"].strip()
                cleaned = _re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>", "", content, flags=_re.DOTALL).strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
                parsed = _json.loads(cleaned) if cleaned.startswith("{") else {"summary": cleaned, "key_points": [], "category": "其他", "relevance": 0.5}
            except Exception as e:
                failed += 1
                print(f"  ✗ LLM error: {e}")
                return

            doc = {
                "url_hash": item.id, "id": item.id,
                "source": item.source, "source_url": item.source_url, "url": item.url,
                "title": item.title, "published_at": item.published_at, "fetched_at": item.fetched_at,
                "author": item.author, "tags": item.tags, "language": item.language,
                "summary": parsed.get("summary", ""), "key_points": parsed.get("key_points", []),
                "category": parsed.get("category", "其他"), "relevance": parsed.get("relevance", 0.5),
                "summary_model": result.get("model", "?"),
                "summary_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await upsert_item_async(doc)
                completed += 1
                print(f"  ✓ [{result.get('model','?')[:14]:<14}] {item.title[:50]} ({parsed.get('category','其他')})")
            except Exception as e:
                failed += 1
                print(f"  ✗ mongo: {e}")

    await asyncio.gather(*[one(it) for it in new_items])
    await registry.aclose()
    print(f"  ✓ 完成 {completed}/{len(new_items)} 条,fail {failed}")


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(prog="fastinfo", description="fastInfo · AI 情报中枢 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # search
    p = sub.add_parser("search", help="搜索资讯")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--source")
    p.add_argument("--category")
    p.set_defaults(func=cmd_search)

    # today
    p = sub.add_parser("today", help="最近资讯")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--category")
    p.add_argument("--source")
    p.set_defaults(func=cmd_today)

    # hot
    p = sub.add_parser("hot", help="今日热点(relevance 排序)")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--hours", type=int, default=24, help="最近 N 小时")
    p.add_argument("--threshold", type=float, default=0.7, help="相关度阈值 0-1")
    p.add_argument("--category")
    p.set_defaults(func=cmd_hot)

    # subscribe
    p = sub.add_parser("subscribe", help="用自然语言创建订阅")
    p.add_argument("nl", help="自然语言描述,如 '帮我每天看 AI 推理论文'")
    p.set_defaults(func=cmd_subscribe)

    # subs
    p = sub.add_parser("subs", help="订阅管理")
    subs = p.add_subparsers(dest="subs_cmd", required=True)

    p2 = subs.add_parser("list", help="列出所有订阅")
    p2.set_defaults(func=cmd_subs_list)

    p2 = subs.add_parser("run", help="立即跑一次订阅")
    p2.add_argument("id")
    p2.add_argument("-v", "--verbose", action="store_true", help="打印推送 item 详情")
    p2.set_defaults(func=cmd_subs_run)

    p2 = subs.add_parser("delete", help="删除订阅")
    p2.add_argument("id")
    p2.set_defaults(func=cmd_subs_delete)

    # stats
    p = sub.add_parser("stats", help="查看入库统计")
    p.set_defaults(func=cmd_stats)

    # 注册 / 登录 / 登出 / 当前用户
    p = sub.add_parser("register", help="注册新用户")
    p.add_argument("username")
    p.add_argument("password")
    p.add_argument("--email", default="")
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("login", help="登录")
    p.add_argument("username")
    p.add_argument("password")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="登出")
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser("whoami", help="查看当前登录用户")
    p.set_defaults(func=cmd_whoami)

    # ingest
    p = sub.add_parser("ingest", help="抓 RSS + 摘要 + 入库(端到端)")
    p.add_argument("--limit", type=int, default=8, help="每源抓多少条")
    p.add_argument("--all", action="store_true", help="清空后重抓")
    p.set_defaults(func=cmd_ingest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()