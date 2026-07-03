"""fastInfo · source_config CRUD (Day 5 多文档版)

旧版:`source_config` 单文档 `{"_id":"global", "enabled":[...]}`
新版:每源一条文档,字段齐全可管理 + 可监控。

向后兼容:旧 global 文档存在时,从它重建多文档(由 scripts/migrate_source_config.py)。
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from storage.mongo_writer import get_db
from crawler.sources import (
    RSS_SOURCES, KOL_SOURCES, CATEGORY_L1, DEFAULT_CRON,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_source_id_for_rss(rss_id: str) -> str:
    return rss_id


def _new_source_id_for_kol(key: str) -> str:
    return key


def _default_for_rss(rss_id: str, name: str, url: str) -> dict:
    return {
        "source_id": rss_id,
        "kind": "rss",
        "display_name": name,
        "url": url,
        "urls": [url],
        "l1": "",
        "tags": [],
        "cron_interval_seconds": DEFAULT_CRON.get("rss", 1800),
        "is_active": True,
        "weight": 100,
        "limit_per_run": 15,
        "dedup_window_days": 7,
        "auto_disable_threshold": 5,
        "consecutive_fails": 0,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _default_for_kol(key: str, name: str, kind: str) -> dict:
    if kind == "weibo_user":
        platform_config = {"mode": "scraper", "openapi_token": "", "cookie": ""}
    elif kind == "x_user":
        platform_config = {"mode": "nitter", "api_v2_key": ""}
    elif kind == "xhs_note":
        platform_config = {"mode": "stub", "third_party_key": ""}
    else:
        platform_config = {}
    return {
        "source_id": key,
        "kind": kind,
        "display_name": name,
        "url": "",
        "urls": [],
        "l1": "",
        "tags": [],
        "cron_interval_seconds": DEFAULT_CRON.get("kol", 3600),
        "is_active": True,
        "weight": 80,
        "limit_per_run": 5,
        "dedup_window_days": 7,
        "auto_disable_threshold": 5,
        "consecutive_fails": 0,
        "platform_config": platform_config,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


# ============================================================
# CRUD
# ============================================================

def list_sources(*, l1: Optional[str] = None, active_only: bool = False) -> list[dict]:
    db = get_db()
    q = {}
    if l1:
        q["l1"] = l1
    if active_only:
        q["is_active"] = True
    out = list(db["source_config"].find(q).sort("source_id", 1))
    for s in out:
        s["_id"] = str(s["_id"])
    return out


def get_source(source_id: str) -> Optional[dict]:
    db = get_db()
    s = db["source_config"].find_one({"source_id": source_id})
    if s:
        s["_id"] = str(s["_id"])
    return s


def upsert_source(doc: dict) -> str:
    """新增或更新一条,返回 source_id"""
    db = get_db()
    if "source_id" not in doc or not doc["source_id"]:
        raise ValueError("source_id required")
    sid = doc["source_id"]
    doc["updated_at"] = now_iso()
    if "created_at" not in doc:
        doc["created_at"] = now_iso()
    db["source_config"].update_one(
        {"source_id": sid},
        {"$set": doc},
        upsert=True,
    )
    return sid


def delete_source(source_id: str, hard: bool = False) -> bool:
    db = get_db()
    if hard:
        r = db["source_config"].delete_one({"source_id": source_id})
        return r.deleted_count > 0
    r = db["source_config"].update_one(
        {"source_id": source_id},
        {"$set": {"is_active": False, "deleted_at": now_iso(), "updated_at": now_iso()}},
    )
    return r.modified_count > 0


def toggle_source(source_id: str) -> Optional[bool]:
    """toggle is_active,返回最新 is_active"""
    db = get_db()
    s = db["source_config"].find_one({"source_id": source_id})
    if not s:
        return None
    new_state = not bool(s.get("is_active", True))
    db["source_config"].update_one(
        {"source_id": source_id},
        {"$set": {
            "is_active": new_state,
            "consecutive_fails": 0 if new_state else s.get("consecutive_fails", 0),
            "updated_at": now_iso(),
        }},
    )
    return new_state


def load_enabled_sources() -> Optional[set[str]]:
    """向后兼容:返回启用的 source_id 集合。None 表示全部"""
    db = get_db()
    cursor = db["source_config"].find({"is_active": True})
    enabled = [s["source_id"] for s in cursor]
    if not enabled:
        return None
    return set(enabled)


def seed_from_registry() -> int:
    """把代码里的 RSS_SOURCES / KOL_SOURCES 同步到 source_config。
    已存在的 source_id 不会覆盖。返回新建条数。"""
    db = get_db()
    created = 0
    for rss_id, (name, url) in RSS_SOURCES.items():
        if db["source_config"].find_one({"source_id": rss_id}):
            continue
        doc = _default_for_rss(rss_id, name, url)
        db["source_config"].insert_one(doc)
        created += 1
    for key, (name, kind) in KOL_SOURCES.items():
        if db["source_config"].find_one({"source_id": key}):
            continue
        doc = _default_for_kol(key, name, kind)
        db["source_config"].insert_one(doc)
        created += 1
    return created


def ensure_indexes():
    db = get_db()
    db["source_config"].create_index("source_id", unique=True)
    db["source_config"].create_index([("kind", 1), ("is_active", 1)])
    db["source_config"].create_index([("l1", 1), ("is_active", 1)])
