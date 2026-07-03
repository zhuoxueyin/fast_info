"""
fastInfo · MongoDB 存储层
=========================
- 连接管理(单例,异步 motor + 同步 pymongo 备用)
- upsert(基于 url_hash 唯一键)
- 简单查询 + 统计

跑前请确保 MongoDB 已起:
    mongosh mongodb://127.0.0.1:27017
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional
from dataclasses import asdict

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

DEFAULT_URL = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
DEFAULT_DB = os.environ.get("MONGO_DB", "fastinfo")

# 全局连接句柄(惰性初始化)
_async_client: Optional[AsyncIOMotorClient] = None
_sync_client: Optional[MongoClient] = None


def get_async_client() -> AsyncIOMotorClient:
    global _async_client
    if _async_client is None:
        _async_client = AsyncIOMotorClient(DEFAULT_URL, serverSelectionTimeoutMS=5000)
    return _async_client


def get_sync_client() -> MongoClient:
    global _sync_client
    if _sync_client is None:
        _sync_client = MongoClient(DEFAULT_URL, serverSelectionTimeoutMS=5000)
    return _sync_client


def get_db():
    return get_sync_client()[DEFAULT_DB]


def ensure_indexes():
    """确保索引(同步)"""
    db = get_db()
    items = db["items"]
    items.create_index([("url_hash", ASCENDING)], unique=True, name="ux_url_hash")
    items.create_index([("source", ASCENDING), ("published_at", DESCENDING)], name="ix_source_pub")
    items.create_index([("category", ASCENDING), ("published_at", DESCENDING)], name="ix_cat_pub")
    items.create_index([("category_l1", ASCENDING), ("published_at", DESCENDING)], name="ix_cat_l1_pub")
    items.create_index([("fetched_at", DESCENDING)], name="ix_fetched")
    # 跨源标题去重索引:title_hash + published_at 用于 7 天内查重
    items.create_index([("title_hash", ASCENDING), ("published_at", DESCENDING)], name="ix_title_hash_pub", sparse=True)

    # 全文检索索引(title + summary + key_points)
    try:
        items.create_index(
            [("title", "text"), ("summary", "text"), ("key_points", "text")],
            name="tx_fulltext",
            weights={"title": 10, "summary": 5, "key_points": 3},
            default_language="english",   # MongoDB 不支持中文 language,统一用 english
            language_override="doc_lang",  # 避开默认的 "language" 字段,避免 "zh" override 报错
        )
    except Exception as e:
        # 同一 collection 只能有一个 text index,如果已存在会抛错,忽略
        if "text index" not in str(e).lower() and "already exists" not in str(e).lower():
            raise

    subs = db["subscriptions"]
    subs.create_index([("user_id", ASCENDING), ("is_active", ASCENDING)], name="ix_user_active")
    subs.create_index([("next_run_at", ASCENDING)], name="ix_next_run")

    users = db["users"]
    users.create_index([("username", ASCENDING)], unique=True, name="ux_username")
    users.create_index([("email", ASCENDING)], unique=False, name="ix_email")

    # v2 架构:订阅推送记录(去重 + 推送历史)
    delivered = db["subscriptions_delivered"]
    delivered.create_index([("subscription_id", ASCENDING), ("item_id", ASCENDING)], unique=True, name="ux_sub_item")
    delivered.create_index([("user_id", ASCENDING), ("delivered_at", DESCENDING)], name="ix_user_delivered")

    # Day 3 新增:banner_config 单例
    banner = db["banner_config"]
    banner.create_index([("_id", ASCENDING)], name="ux_id")

    # Day 3 新增:task_runs 抓取任务时间线
    runs = db["task_runs"]
    runs.create_index([("started_at", DESCENDING)], name="ix_started_at")
    runs.create_index([("trigger", ASCENDING), ("started_at", DESCENDING)], name="ix_trigger_started")
    runs.create_index([("operator", ASCENDING), ("started_at", DESCENDING)], name="ix_operator_started")

    print(f"  ✓ indexes created on db={DEFAULT_DB}")


# ============================================================
# 写入 / 读取
# ============================================================

def _ensure_category_l1(item: dict) -> None:
    """确保 item 有 category_l1 字段;如果没有,从 category 归一化"""
    if not item.get("category_l1"):
        try:
            from taxonomy import normalize_l1
            item["category_l1"] = normalize_l1(item.get("category"))
        except Exception:
            item["category_l1"] = "其他"


def upsert_item(item: dict) -> bool:
    """
    根据 url_hash upsert 到 items 集合
    返回: True=新增, False=已存在
    """
    _ensure_category_l1(item)
    db = get_db()
    coll = db["items"]
    try:
        coll.insert_one(item)
        return True
    except DuplicateKeyError:
        coll.update_one({"url_hash": item["url_hash"]}, {"$set": item})
        return False


async def upsert_item_async(item: dict) -> bool:
    _ensure_category_l1(item)
    db = get_async_client()[DEFAULT_DB]
    coll = db["items"]
    try:
        await coll.insert_one(item)
        return True
    except Exception as e:  # DuplicateKeyError 在异步侧是普通 Exception
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            await coll.update_one({"url_hash": item["url_hash"]}, {"$set": item})
            return False
        raise


def get_recent(limit: int = 20, source: Optional[str] = None, category: Optional[str] = None):
    """最近拉取的内容,按 published_at 倒序"""
    db = get_db()
    q: dict = {}
    if source:
        q["source"] = source
    if category:
        q["category"] = category
    cursor = db["items"].find(q).sort("published_at", DESCENDING).limit(limit)
    return list(cursor)


def count_items() -> int:
    return get_db()["items"].count_documents({})


def get_done_urls() -> set[str]:
    """返回已入库 url_hash 集合(增量抓取用)"""
    return {d["url_hash"] for d in get_db()["items"].find({}, {"url_hash": 1, "_id": 0})}


def get_recent_title_hashes(days: int = 7) -> set[str]:
    """返回 N 天内已入库的 title_hash 集合(跨源标题去重用)。
    用于:同一事件被多源报道,只保留最早抓取的那条。
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = get_db()
    return {
        d["title_hash"]
        for d in db["items"].find(
            {"title_hash": {"$exists": True, "$ne": ""}, "published_at": {"$gte": cutoff.isoformat()}},
            {"title_hash": 1, "_id": 0},
        )
    }


def stats() -> dict:
    db = get_db()
    return {
        "total": db["items"].count_documents({}),
        "by_source": list(db["items"].aggregate([
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
        "by_category": list(db["items"].aggregate([
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
    }


# ============================================================
# Day 3 新增:banner_config / task_runs / categories / inbox
# ============================================================

DEFAULT_BANNER = {
    "_id": "default",
    "categories": ["科技", "AI", "财经"],
    "max_per_category": 3,
    "updated_at": None,
    "updated_by": None,
}


def get_banner() -> dict:
    """获取 banner 配置,不存在则预置默认"""
    db = get_db()
    doc = db["banner_config"].find_one({"_id": "default"})
    if not doc:
        doc = dict(DEFAULT_BANNER)
        doc["updated_at"] = datetime.now(timezone.utc)
        db["banner_config"].insert_one(doc)
    return _serialize_datetimes(_strip_oid(doc))


def set_banner(categories: list, max_per_category: int, updated_by: str | None) -> dict:
    db = get_db()
    doc = {
        "_id": "default",
        "categories": categories,
        "max_per_category": max_per_category,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": updated_by,
    }
    db["banner_config"].replace_one({"_id": "default"}, doc, upsert=True)
    return _serialize_datetimes(_strip_oid(doc))


def list_categories() -> list[str]:
    """items.category 的 distinct(去掉空字符串)"""
    db = get_db()
    cats = db["items"].distinct("category")
    return sorted({c for c in cats if c})


def record_task_run(run: dict) -> None:
    """写入一次抓取事件。run 含 run_id, started_at, finished_at, trigger, operator, items_*, per_source, llm_breakdown。"""
    db = get_db()
    db["task_runs"].insert_one(dict(run))


def get_recent_task_runs(limit: int = 20) -> list[dict]:
    db = get_db()
    cursor = db["task_runs"].find().sort("started_at", DESCENDING).limit(limit)
    return [_serialize_datetimes(_strip_oid(d)) for d in cursor]


def get_task_run(run_id: str) -> dict | None:
    db = get_db()
    doc = db["task_runs"].find_one({"run_id": run_id})
    return _serialize_datetimes(_strip_oid(doc)) if doc else None


def get_source_status_24h() -> list[dict]:
    """每个源 24h 内抓取 / 失败数 + 最近一次成功时间"""
    from datetime import timedelta
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    pipeline = [
        {"$match": {"started_at": {"$gte": cutoff}}},
        {"$project": {"sources": {"$objectToArray": "$per_source"}}},
        {"$unwind": "$sources"},
        {"$group": {
            "_id": "$sources.k",
            "fetched_24h": {"$sum": "$sources.v.fetched"},
            "failed_24h":  {"$sum": "$sources.v.errors"},
            "last_run_at": {"$max": "$started_at"},
            "last_latency_ms": {"$max": "$sources.v.latency_ms"},
        }},
        {"$sort": {"_id": 1}},
    ]
    return list(db["task_runs"].aggregate(pipeline))


def get_user_inbox(
    user_id: str,
    sort: str = "relevance",
    subscription_id: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """聚合 subscriptions_delivered + items,带订阅名/类目/发布时间"""
    db = get_db()
    match: dict = {"user_id": user_id}
    if subscription_id:
        match["subscription_id"] = subscription_id

    pipeline: list[dict] = [
        {"$match": match},
        # item_id 是 string,items._id 是 ObjectId,需要转换才能 join
        {"$lookup": {
            "from": "items",
            "let": {"iid": "$item_id"},
            "pipeline": [
                {"$match": {"$expr": {"$or": [
                    {"$eq": ["$_id", {"$toObjectId": "$$iid"}]},
                    {"$eq": [{"$toString": "$_id"}, "$$iid"]},
                    {"$eq": ["$id", "$$iid"]},
                    {"$eq": ["$url_hash", "$$iid"]},
                ]}}}
            ],
            "as": "item",
        }},
        {"$unwind": {"path": "$item", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {
            "from": "subscriptions",
            "let": {"sid": "$subscription_id"},
            "pipeline": [
                {"$match": {"$expr": {"$or": [
                    {"$eq": ["$_id", {"$toObjectId": "$$sid"}]},
                    {"$eq": [{"$toString": "$_id"}, "$$sid"]},
                ]}}}
            ],
            "as": "sub",
        }},
        {"$unwind": {"path": "$sub", "preserveNullAndEmptyArrays": True}},
    ]

    if category:
        pipeline.append({"$match": {"item.category": category}})

    if sort == "relevance":
        pipeline.append({"$sort": {"item.relevance": DESCENDING, "delivered_at": DESCENDING}})
    elif sort == "time":
        pipeline.append({"$sort": {"delivered_at": DESCENDING}})
    else:
        pipeline.append({"$sort": {"delivered_at": DESCENDING}})

    total_pipeline = pipeline + [{"$count": "n"}]
    total = 0
    total_docs = list(db["subscriptions_delivered"].aggregate(total_pipeline))
    if total_docs:
        total = total_docs[0].get("n", 0)

    skip = (page - 1) * page_size
    pipeline.append({"$skip": skip})
    pipeline.append({"$limit": page_size})

    items = []
    for doc in db["subscriptions_delivered"].aggregate(pipeline):
        item = doc.get("item") or {}
        sub = doc.get("sub") or {}
        items.append({
            "delivered_at": doc.get("delivered_at"),
            "subscription_id": str(doc.get("subscription_id")),
            "subscription_title": sub.get("title"),
            "item": {
                "id": str(item.get("_id")),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "key_points": item.get("key_points") or [],
                "category": item.get("category"),
                "source": item.get("source"),
                "url": item.get("url"),
                "relevance": item.get("relevance"),
                "published_at": item.get("published_at"),
                "tags": item.get("tags") or [],
            },
        })
    return _serialize_datetimes({"items": items, "total": total, "page": page, "page_size": page_size})


def _strip_oid(doc: dict) -> dict:
    """去掉 _id / 内部 ObjectId 字段(导出给 API 时)"""
    if doc is None:
        return doc
    out = dict(doc)
    if "_id" in out:
        del out["_id"]
    return out


def _serialize_datetimes(doc: dict) -> dict:
    """递归把 datetime 转 ISO string,避免 Pydantic 报 string_type 错误"""
    if doc is None:
        return doc
    if isinstance(doc, dict):
        return {k: _serialize_datetimes(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_serialize_datetimes(v) for v in doc]
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


def search_text(
    query: str,
    limit: int = 10,
    source: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """
    MongoDB 原生全文检索(Mongo text index,基于 score 排序)

    特点:
    - 不支持中文分词(用整词 / phrase 匹配)
    - title 权重 10,summary 权重 5,key_points 权重 3
    - 适合关键词明确查询,语义查询后续可加 BGE-M3 升级

    用法:
        results = search_text("AI 推理模型", limit=10)
    """
    db = get_db()
    must: dict = {"$text": {"$search": query}}
    if source:
        must["source"] = source
    if category:
        must["category"] = category
    cursor = (
        db["items"]
        .find(must, {"score": {"$meta": "textScore"}})
        .sort([("score", {"$meta": "textScore"})])
        .limit(limit)
    )
    return list(cursor)


if __name__ == "__main__":
    print(f"Connecting to {DEFAULT_URL} ...")
    info = get_sync_client().server_info()
    print(f"  ✓ MongoDB version: {info['version']}")
    print(f"  ✓ Database: {DEFAULT_DB}")
    ensure_indexes()
    print(f"  ✓ Items count: {count_items()}")