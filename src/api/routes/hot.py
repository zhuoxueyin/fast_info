"""GET /api/hot?limit=10&hours=24&threshold=0.7&category=...

排序策略（v2）：
1. **热度统一口径**：每篇文章的 relevance 转换为同类目内的百分位排名（0~1），
   消除不同 LLM 对不同类目打分口径不一致的问题。
2. **时间衰减**：cat_percentile / (age_hours + 4) ^ 1.2，温和衰减，以百分位为主。
3. **类目均衡**：排序后每类目最多 3 条，避免单类目霸榜。

脏数据兼容：relevance 0-100 量纲自动 /10，string 类型强转 double。
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from storage.mongo_writer import get_sync_client, DEFAULT_DB
from ..schemas import HotResponse, ItemView
from taxonomy import CATEGORY_L1

router = APIRouter(tags=["hot"])

MAX_PER_CATEGORY = 3  # 每个 L1 类目在"全部"tab 中最多出现几条


@router.get("/hot", response_model=HotResponse)
async def hot_endpoint(
    limit: int = Query(10, ge=1, le=50),
    hours: int = Query(24, ge=1, le=168, description="最近 N 小时"),
    threshold: float = Query(0.7, ge=0.0, le=10.0, description="相关度阈值(0-1 或 0-10)"),
    category: Optional[str] = None,
):
    db = get_sync_client()[DEFAULT_DB]
    now = datetime.now(timezone.utc)
    since_iso = (now - timedelta(hours=hours)).isoformat()
    now_ts_ms = int(now.timestamp() * 1000)

    # threshold 自适应：>1 视为 0-10 量纲，<=1 视为 0-1（×10）
    rel_threshold = threshold if threshold > 1.0 else threshold * 10.0

    # ============================================================
    # 1. 归一化 relevance 到 0-10
    # ============================================================
    rel_as_num = {
        "$cond": [
            {"$isNumber": "$relevance"},
            "$relevance",
            {
                "$convert": {
                    "input": "$relevance",
                    "to": "double",
                    "onError": 5.0,
                    "onNull": 5.0,
                }
            },
        ]
    }
    rel_norm_expr = {
        "$cond": [
            {"$gt": [rel_as_num, 10]},
            {"$divide": [rel_as_num, 10.0]},
            rel_as_num,
        ]
    }
    rel_clamped_expr = {"$min": [{"$max": [rel_norm_expr, 0.0]}, 10.0]}

    # ============================================================
    # 2. age_hours 计算
    # ============================================================
    ts_expr = {
        "$toLong": {
            "$convert": {
                "input": {"$ifNull": ["$published_at", "$fetched_at"]},
                "to": "date",
                "onError": {"$literal": None},
                "onNull": {"$literal": None},
            }
        }
    }
    age_hours_expr = {
        "$divide": [
            {"$subtract": [now_ts_ms, {"$ifNull": [ts_expr, now_ts_ms]}]},
            3600000.0,
        ]
    }
    age_clamped_expr = {"$max": [age_hours_expr, 0.0]}

    # ============================================================
    # 3. 类目内百分位排名（$setWindowFields）
    # ============================================================
    match: dict = {"fetched_at": {"$gte": since_iso}}
    if category:
        if category in CATEGORY_L1:
            match["category_l1"] = category
        else:
            match["category"] = category

    pipeline = [
        {"$match": match},
        # 先算好 rel 和 age
        {
            "$addFields": {
                "_rel_norm": rel_clamped_expr,
                "_age_h": age_clamped_expr,
            }
        },
        {"$match": {"_rel_norm": {"$gte": rel_threshold}}},
        # 类目内排序，算 rank（1-based，按 rel 降序）
        {
            "$setWindowFields": {
                "partitionBy": "$category_l1",
                "sortBy": {"_rel_norm": -1},
                "output": {
                    "_cat_rank": {"$rank": {}},        # 1-based
                    "_cat_total": {"$count": {}},      # 同类目总数
                },
            }
        },
        # cat_percentile = 1 - (rank-1)/total  → 越高越热，0~1
        {
            "$addFields": {
                "_cat_pct": {
                    "$subtract": [
                        1.0,
                        {"$divide": [{"$subtract": ["$_cat_rank", 1]}, "$_cat_total"]},
                    ]
                }
            }
        },
        # hot_score = cat_pct / (age + 4) ^ 1.2
        {
            "$addFields": {
                "_hot_score": {
                    "$divide": [
                        "$_cat_pct",
                        {"$pow": [{"$add": ["$_age_h", 4.0]}, 1.2]},
                    ]
                }
            }
        },
        {"$sort": {"_hot_score": -1, "fetched_at": -1}},
    ]

    # ============================================================
    # 4. 类目均衡截断：每类目最多 MAX_PER_CATEGORY 条
    # ============================================================
    cat_counts: dict[str, int] = {}
    items: list[ItemView] = []

    for d in db["items"].aggregate(pipeline):
        l1 = d.get("category_l1") or "其他"
        current = cat_counts.get(l1, 0)
        if current >= MAX_PER_CATEGORY:
            continue  # 该类目已满，跳过
        cat_counts[l1] = current + 1
        items.append(_to_view(d))
        if len(items) >= limit:
            break

    return HotResponse(hours=hours, threshold=threshold, total=len(items), items=items)


def _to_view(d: dict) -> ItemView:
    return ItemView(
        id=str(d.get("_id", "")),
        source=d.get("source", ""),
        url=d.get("url", ""),
        title=d.get("title", ""),
        summary=d.get("summary", ""),
        category=d.get("category"),
        category_l1=d.get("category_l1"),
        relevance=d.get("_rel_norm") or d.get("relevance"),
        published_at=d.get("published_at"),
        fetched_at=d.get("fetched_at"),
        author=d.get("author"),
        tags=d.get("tags", []) or [],
    )
