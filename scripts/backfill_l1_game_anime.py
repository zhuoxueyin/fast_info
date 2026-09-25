"""
fastInfo · 回填:重跑 normalize_l1 重新归类 items.category_l1
=====================================================
背景:之前 ingest_daemon.py 的 LLM prompt 和白名单硬编码 7 个 L1
(科技/AI/体育/娱乐/财经/汽车/其他),「动漫」「游戏」被丢弃。
结果:新抓的娱乐/游戏内容被错分到「娱乐」「其他」「财经」。

修法:
1. ingest_daemon.py prompt + 白名单已加「动漫」「游戏」(同时 PR)
2. 已入库 items 用 normalize_l1 + LLM 重归类

此脚本只做轻量规则重归类(不调 LLM,避免几毛钱费用):
  - 优先按 L1 关键词匹配,score 最高胜出
  - 命中动漫/游戏关键词的 items 直接更新 category_l1
  - 不变更其他字段,纯字段迁移
"""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pymongo import MongoClient
from taxonomy import normalize_l1


def main():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))
    db = client[os.environ.get("MONGO_DB", "fastinfo_prod")]
    coll = db["items"]

    total = coll.count_documents({})
    updated = 0
    by_l1 = {"科技": 0, "AI": 0, "体育": 0, "娱乐": 0, "动漫": 0, "游戏": 0, "财经": 0, "汽车": 0, "其他": 0}

    cursor = coll.find({}, {"title": 1, "summary": 1, "category": 1, "category_l1": 1, "tags": 1})
    bulk = []
    for doc in cursor:
        text = f"{doc.get('title', '')} {doc.get('summary', '')}"
        new_l1 = normalize_l1(doc.get("category"), text)
        old_l1 = doc.get("category_l1", "")
        if new_l1 != old_l1 and new_l1 in by_l1:
            bulk.append({"_id": doc["_id"], "new": new_l1})
            updated += 1
            by_l1[new_l1] += 1

    # 批量更新(分批 500 条)
    BATCH = 500
    for i in range(0, len(bulk), BATCH):
        for j, item in enumerate(bulk[i:i+BATCH]):
            coll.update_one({"_id": item["_id"]}, {"$set": {"category_l1": item["new"]}})

    print(f"扫描:{total} | 改写:{updated}")
    print("改写后分布(新增归到):")
    for k, v in by_l1.items():
        if v > 0:
            print(f"  {k}: +{v}")


if __name__ == "__main__":
    main()