"""fastInfo · Day 6.5 一次性回填 source_config.l1

Day 5 seed 时 _default_for_rss/_default_for_kol 把 l1 写死成 ""，
导致 SourcesPage 的 L1 类目筛选永远 0 命中(总源数 16,体育筛出 0)。

这个脚本:
  1. 按 SOURCE_L1_DEFAULT 把 l1 字段回填到 source_config
  2. 不在字典里的源兜底 "其他" 并打印警告,方便人工补登记

幂等:可重复跑,只会更新 l1 仍为空的源(已有 L1 的不动)。
"""
from __future__ import annotations
import sys

sys.path.insert(0, "src")

from storage.mongo_writer import get_db
from crawler.sources import SOURCE_L1_DEFAULT, CATEGORY_L1


def main() -> int:
    db = get_db()
    coll = db["source_config"]

    targets = list(coll.find({"$or": [{"l1": ""}, {"l1": None}, {"l1": {"$exists": False}}]}))
    print(f"待回填 {len(targets)} 条")

    updated = 0
    warned: list[str] = []
    for s in targets:
        sid = s["source_id"]
        l1 = SOURCE_L1_DEFAULT.get(sid, "其他")
        if l1 not in CATEGORY_L1:
            print(f"  ! 非法 L1 {l1!r} for {sid}, 改写为 其他")
            l1 = "其他"
        coll.update_one({"source_id": sid}, {"$set": {"l1": l1}})
        updated += 1
        if sid not in SOURCE_L1_DEFAULT:
            warned.append(sid)
        print(f"  {sid:30s} -> {l1}")

    print()
    print(f"已更新 {updated} 条")
    if warned:
        print(f"未在 SOURCE_L1_DEFAULT 登记,已兜底为'其他'(请人工补登记): {warned}")

    # 校验
    print("\n--- 按 L1 聚合 ---")
    for d in coll.aggregate([{"$group": {"_id": "$l1", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]):
        print(f"  {d['_id']:6s} {d['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
