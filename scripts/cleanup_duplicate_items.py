#!/usr/bin/env python3
"""清理因 URL 追踪参数 / title_hash 去重失效产生的重复 items。

策略(P1 修数据不修兼容):
  1. 按 title_hash 分组,每组保留 fetched_at 最早的 1 条
  2. 其余从 items 删除,并同步清 subscriptions_delivered 孤儿引用
  3. 可选:把保留条的 url 规范化成 canonicalize_url 结果

用法:
  MONGO_URL=mongodb://127.0.0.1:27018 MONGO_DB=fastinfo_prod \\
    python scripts/cleanup_duplicate_items.py --dry-run
  MONGO_URL=... MONGO_DB=... python scripts/cleanup_duplicate_items.py --apply
"""
from __future__ import annotations
import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from storage.mongo_writer import get_sync_client, DEFAULT_DB  # noqa: E402
from crawler.rss_collector import canonicalize_url  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正删除;默认 dry-run")
    ap.add_argument("--db", default=os.environ.get("MONGO_DB") or DEFAULT_DB)
    args = ap.parse_args()
    dry = not args.apply

    client = get_sync_client()
    db = client[args.db]
    print(f"[cleanup] db={args.db} dry_run={dry}")

    # 1) title_hash 分组
    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in db["items"].find(
        {"title_hash": {"$exists": True, "$ne": ""}},
        {"_id": 1, "title_hash": 1, "title": 1, "url": 1, "url_hash": 1,
         "fetched_at": 1, "source": 1},
    ):
        groups[doc["title_hash"]].append(doc)

    multi = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"[cleanup] title_hash groups with dups: {len(multi)}")

    delete_ids = []
    keep_updates = []  # (id, {url, ...})
    for th, docs in multi.items():
        docs_sorted = sorted(docs, key=lambda d: d.get("fetched_at") or "")
        keep = docs_sorted[0]
        drop = docs_sorted[1:]
        delete_ids.extend([d["_id"] for d in drop])
        # 规范化保留条 URL
        canon = canonicalize_url(keep.get("url") or "")
        if canon and canon != keep.get("url"):
            keep_updates.append((keep["_id"], {"url": canon}))
        print(
            f"  keep={keep.get('title', '')[:40]!r} "
            f"drop={len(drop)} source={keep.get('source')} th={th}"
        )

    print(f"[cleanup] would delete {len(delete_ids)} items, update url on {len(keep_updates)}")

    if dry:
        print("[cleanup] dry-run done. pass --apply to execute.")
        return 0

    if delete_ids:
        # 清 delivered 孤儿
        id_strs = [str(i) for i in delete_ids]
        r_del = db["subscriptions_delivered"].delete_many({"item_id": {"$in": id_strs}})
        print(f"[cleanup] subscriptions_delivered removed: {r_del.deleted_count}")
        r_items = db["items"].delete_many({"_id": {"$in": delete_ids}})
        print(f"[cleanup] items deleted: {r_items.deleted_count}")

    for oid, fields in keep_updates:
        db["items"].update_one({"_id": oid}, {"$set": fields})
    print(f"[cleanup] urls canonicalized: {len(keep_updates)}")
    print("[cleanup] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
