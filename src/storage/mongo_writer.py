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
from datetime import datetime, timezone, timedelta
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

    # Day 9 新增:push_history 推送历史(用户视角)
    history = db["push_history"]
    history.create_index([("user_id", ASCENDING), ("sent_at", DESCENDING)], name="ix_user_sent")
    history.create_index([("trigger", ASCENDING), ("sent_at", DESCENDING)], name="ix_trigger_sent")

    # ---- Day 5 additions ----
    try:
        from storage.source_runs import ensure_indexes as _sr_idx
        _sr_idx()
    except Exception as _e:
        print(f"  ✗ source_runs index init failed: {_e}")
    try:
        from storage.source_config import ensure_indexes as _sc_idx
        _sc_idx()
    except Exception as _e:
        print(f"  ✗ source_config index init failed: {_e}")

    print(f"  ✓ indexes created on db={DEFAULT_DB}")


# ============================================================
# 写入 / 读取
# ============================================================

def _ensure_category_l1(item: dict) -> None:
    """确保 item 有 category_l1 字段;如果没有,从 category + 标题/摘要归一化"""
    if not item.get("category_l1"):
        try:
            from taxonomy import normalize_l1
            text = f"{item.get('title', '')} {item.get('summary', '')}"
            item["category_l1"] = normalize_l1(item.get("category"), text)
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
            # pymongo insert_one 失败时会 mutate item dict 自动加 _id 字段,
            # update_one $set 时不能动 _id(MongoDB immutable),先 pop 掉
            update_doc = {k: v for k, v in item.items() if k != "_id"}
            await coll.update_one({"url_hash": item["url_hash"]}, {"$set": update_doc})
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

    注意:热搜源(weibo:hot)的 published_at 常为 null,必须用 fetched_at 兜底,
    否则 title_hash 去重对热搜完全失效 → 同一话题被推 N 次。
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    db = get_db()
    return {
        d["title_hash"]
        for d in db["items"].find(
            {
                "title_hash": {"$exists": True, "$ne": ""},
                "$or": [
                    {"published_at": {"$gte": cutoff_iso}},
                    {"fetched_at": {"$gte": cutoff_iso}},
                ],
            },
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
    """获取 banner 配置,不存在则预置默认(幂等:支持并发首次启动)"""
    db = get_db()
    doc = db["banner_config"].find_one({"_id": "default"})
    if not doc:
        doc = dict(DEFAULT_BANNER)
        doc["updated_at"] = datetime.now(timezone.utc)
        # 并发启动时多个容器可能同时到这里:
        # 用 update_one(upsert=True) 替代 insert_one,
        # 避免 E11000 duplicate key error 导致 entrypoint 异常退出。
        try:
            db["banner_config"].update_one(
                {"_id": "default"},
                {"$setOnInsert": doc},
                upsert=True,
            )
        except Exception:
            # 兜底:即便 upsert 失败,也让函数返回现存文档,不阻断 bootstrap
            doc = db["banner_config"].find_one({"_id": "default"}) or doc
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


def create_task_run_pending(run: dict) -> None:
    """Day 5 升级:任务启动时立刻写一条 status=running 的占位记录,
    让前端 /admin/ingest/task/{run_id} 轮询时能立刻查到。
    run 至少含 run_id / started_at / trigger / operator。
    """
    db = get_db()
    doc = dict(run)
    doc.setdefault("status", "running")
    doc.setdefault("finished_at", None)
    doc.setdefault("items_fetched", 0)
    doc.setdefault("items_summarized", 0)
    doc.setdefault("items_failed", 0)
    doc.setdefault("per_source", {})
    doc.setdefault("llm_breakdown", {})
    db["task_runs"].insert_one(doc)


def update_task_run_finished(run_id: str, patch: dict) -> bool:
    """Day 5 升级:任务结束(或失败)时更新原 running 记录。
    patch 一般含 finished_at / status / items_* / warning / per_source。
    返回 True 表示更新成功(记录存在),False 表示没找到。
    """
    db = get_db()
    if not patch.get("status"):
        patch["status"] = "done"
    res = db["task_runs"].update_one({"run_id": run_id}, {"$set": patch})
    return res.matched_count > 0


def get_task_run_status(run_id: str) -> dict | None:
    """Day 5 升级:取一条 task_run 的精简状态(给轮询用)。"""
    db = get_db()
    doc = db["task_runs"].find_one(
        {"run_id": run_id},
        {"run_id": 1, "status": 1, "started_at": 1, "finished_at": 1,
         "trigger": 1, "operator": 1, "items_fetched": 1,
         "items_summarized": 1, "items_failed": 1, "warning": 1,
         "per_source": 1, "llm_breakdown": 1},
    )
    return _serialize_datetimes(_strip_oid(_normalize_task_run_status(doc))) if doc else None


STALE_RUNNING_THRESHOLD_SEC = 1800  # 30 分钟未结束的 running 视为僵尸


def _normalize_task_run_status(doc: dict) -> dict:
    """统一 task_run 状态语义(从执行中/成功/失败真实视角)。

    落库的原始 status 只有 running/done/failed 三种,且 done 不区分全失败/部分失败。
    这里在读取时归一化为:
      - running  → running (未超时) 或 stale (超时 30min 未结束)
      - done     → done (全成功) / partial (部分失败) / failed (全失败)
      - failed   → failed
      - 缺失/老数据 → failed (无 status 字段的视为失败)
    """
    if doc is None:
        return doc
    raw = doc.get("status")
    finished = doc.get("finished_at")
    started = doc.get("started_at")

    if raw == "running":
        # 判断是否僵尸:started_at 超过阈值且未结束
        if started is not None and finished is None:
            try:
                if isinstance(started, str):
                    started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                else:
                    started_dt = started
                if isinstance(started_dt, datetime):
                    elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds()
                    if elapsed > STALE_RUNNING_THRESHOLD_SEC:
                        doc["status"] = "stale"
                        doc["status_reason"] = f"running 超过 {int(elapsed)}s 未结束,视为僵尸"
            except Exception:
                pass
        return doc

    if raw == "done":
        summ = int(doc.get("items_summarized") or 0)
        failed = int(doc.get("items_failed") or 0)
        if summ == 0 and failed > 0:
            # 全失败却标 done —— 真实视角是失败
            doc["status"] = "failed"
            doc["status_reason"] = "items_summarized=0 且 items_failed>0,判定为失败"
        elif summ > 0 and failed > 0:
            doc["status"] = "partial"
            doc["status_reason"] = f"部分失败:成功 {summ} / 失败 {failed}"
        # else 保持 done
        return doc

    if raw == "failed":
        return doc

    # 老数据无 status 字段(Day 5 之前) —— 视为失败(无法判断真实状态)
    if raw is None:
        doc["status"] = "failed"
        doc["status_reason"] = "无 status 字段(老数据),无法判定真实状态"
    return doc


def get_recent_task_runs(limit: int = 20) -> list[dict]:
    db = get_db()
    cursor = db["task_runs"].find().sort("started_at", DESCENDING).limit(limit)
    runs = [_serialize_datetimes(_strip_oid(_normalize_task_run_status(d))) for d in cursor]
    # 批量聚合每条 task 的源级统计(避免 N+1)
    run_ids = [r["run_id"] for r in runs if r.get("run_id")]
    if run_ids:
        pipeline = [
            {"$match": {"task_run_id": {"$in": run_ids}}},
            {"$group": {
                "_id": {"run_id": "$task_run_id", "status": "$status"},
                "count": {"$sum": 1},
            }},
        ]
        agg: dict[str, dict[str, int]] = {}
        for d in db["source_runs"].aggregate(pipeline):
            rid = d["_id"]["run_id"]
            st = d["_id"]["status"]
            agg.setdefault(rid, {})[st] = d["count"]
        for r in runs:
            rid = r.get("run_id")
            if rid and rid in agg:
                stats = agg[rid]
                r["source_stats"] = {
                    "ok": stats.get("ok", 0),
                    "fail": stats.get("fail", 0),
                    "partial": stats.get("partial", 0),
                    "disabled": stats.get("disabled", 0),
                }
            else:
                r["source_stats"] = {"ok": 0, "fail": 0, "partial": 0, "disabled": 0}
    return runs


def get_task_run(run_id: str) -> dict | None:
    db = get_db()
    doc = db["task_runs"].find_one({"run_id": run_id})
    return _serialize_datetimes(_strip_oid(_normalize_task_run_status(doc))) if doc else None


def reap_stale_task_runs(threshold_sec: int = STALE_RUNNING_THRESHOLD_SEC) -> int:
    """回收僵尸 running 任务:把超过 threshold_sec 未结束的 running 标记为 failed。

    返回回收条数。进程崩溃/被 kill 后,running 记录会永久残留,此函数用于清理。
    """
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_sec)
    res = db["task_runs"].update_many(
        {
            "status": "running",
            "started_at": {"$lt": cutoff},
        },
        {
            "$set": {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc),
                "warning": f"僵尸任务回收:running 超过 {threshold_sec}s 未结束(进程可能崩溃/被 kill)",
                "status_reason": "reaped by reap_stale_task_runs",
            }
        },
    )
    return res.modified_count


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