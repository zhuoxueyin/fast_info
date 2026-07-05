"""今日热点榜(Day 9 升级)

GET /api/hot
  - 总榜(默认):每个 L1 最多 max_per_category 条,跨类目热度均衡
  - 模式 mode=category + category=X:返回该 L1 的完整榜单(不限条数)
  - **Day 10 新增 mode=feed**(全部 tab):不分类目,登录态按订阅偏好加权,
    匿名态用稳定 hash 打散,仍可手切 hot/time

GET /api/hot/categories
  - 一次返回所有 7 个 L1 类目各自的 TOP N 榜单,前端用于"分榜汇总"页

排序口径(沿用 v2):
  1. **类目内百分位**:relevance 在同 L1 内的排名 → cat_percentile (0~1)
  2. **时间衰减**:cat_percentile / (age_hours + 4) ^ 1.2
  3. **类目均衡**:总榜模式下,每类最多 max_per_category 条,避免单类霸榜
  4. **Day 10 偏好加权**(仅 mode=feed + 登录):用户订阅聚合的 keywords/
     categories_l1/l2 命中越多,_feed_score 越高;无订阅则按 item._id 稳定
     伪随机打散,保证页面稳定但每条都有机会被看到。

脏数据兼容:relevance 0-100 自动 /10、string 强转 double、缺时间 fallback fetched_at。
"""
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List

from storage.mongo_writer import get_sync_client, get_db, DEFAULT_DB
from ..schemas import HotResponse, ItemView
from ..deps import get_current_user_optional
from taxonomy import CATEGORY_L1

router = APIRouter(tags=["hot"])

DEFAULT_MAX_PER_CATEGORY = 3   # 总榜每个 L1 最多条数
CATEGORY_BATCH_LIMIT = 10      # /hot/categories 单类返回条数


# =================================================================
# 公共 pipeline 片段
# =================================================================

def _rel_norm_expr() -> dict:
    """relevance → 0-10 归一化(容忍 0-1/0-10/string)"""
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
    rel_norm = {
        "$cond": [
            {"$gt": [rel_as_num, 10]},
            {"$divide": [rel_as_num, 10.0]},
            rel_as_num,
        ]
    }
    return {"$min": [{"$max": [rel_norm, 0.0]}, 10.0]}


def _age_hours_expr(now_ts_ms: int) -> dict:
    """age_hours 计算"""
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
    return {
        "$divide": [
            {"$subtract": [now_ts_ms, {"$ifNull": [ts_expr, now_ts_ms]}]},
            3600000.0,
        ]
    }


def _build_hot_pipeline(
    *,
    since_iso: str,
    rel_threshold: float,
    now_ts_ms: int,
    category_l1: Optional[str] = None,
    min_relevance: float = 0.0,
) -> list:
    """构造完整的 hot 排序 pipeline。

    字段说明(供 _to_view 后续读取):
      _rel_norm: 归一化 0-10
      _age_h: 年龄(小时)
      _cat_rank: 类目内 1-based 排名
      _cat_total: 类目总数
      _cat_pct: 0~1 类目内百分位
      _hot_score: 综合打分
    """
    match: dict = {"fetched_at": {"$gte": since_iso}}
    if category_l1 and category_l1 in CATEGORY_L1:
        match["category_l1"] = category_l1

    rel_clamped = _rel_norm_expr()
    age_h = _age_hours_expr(now_ts_ms)

    pipeline = [
        {"$match": match},
        {
            "$addFields": {
                "_rel_norm": rel_clamped,
                "_age_h": {"$max": [age_h, 0.0]},
            }
        },
        {"$match": {"_rel_norm": {"$gte": rel_threshold}}},
        {
            "$setWindowFields": {
                "partitionBy": "$category_l1",
                "sortBy": {"_rel_norm": -1},
                "output": {
                    "_cat_rank": {"$rank": {}},
                    "_cat_total": {"$count": {}},
                },
            }
        },
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
        {"$match": {"_rel_norm": {"$gte": min_relevance}}},
        {"$sort": {"_hot_score": -1, "fetched_at": -1}},
    ]
    return pipeline


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


# =================================================================
# Day 10:mode=feed 全部 tab 排序逻辑
# =================================================================

def _collect_user_preferences(user_id: str) -> dict:
    """从用户所有 active subscriptions 聚合偏好,供 feed 排序用。

    返回结构:
      keywords_lower:        list[str]   小写去重
      categories_l1:         list[str]   原样
      categories_l2:         list[str]   原样
      has_preference:        bool        至少有一项才视为有偏好
    """
    try:
        cursor = get_db()["subscriptions"].find(
            {"user_id": user_id, "is_active": True},
            {"keywords": 1, "categories_l1": 1, "categories_l2": 1, "_id": 0},
        )
        kw: set[str] = set()
        c1: set[str] = set()
        c2: set[str] = set()
        for d in cursor:
            for k in (d.get("keywords") or []):
                k = (k or "").strip().lower()
                if k:
                    kw.add(k)
            for c in (d.get("categories_l1") or []):
                c = (c or "").strip()
                if c:
                    c1.add(c)
            for c in (d.get("categories_l2") or []):
                c = (c or "").strip()
                if c:
                    c2.add(c)
    except Exception:
        kw, c1, c2 = set(), set(), set()
    return {
        "keywords_lower": list(kw),
        "categories_l1": list(c1),
        "categories_l2": list(c2),
        "has_preference": bool(kw or c1 or c2),
    }


def _stable_seed(text: str) -> float:
    """用 md5(item.id + 日期) 生成 0~1 的稳定伪随机,日期粒度保证 24h 内稳定。

    用于"没订阅时随机打散":同一条 item 同一日内永远拿到同一个 rank,
    跨日才换,避免每次刷新跳位。
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    h = hashlib.md5(f"{text}|{today}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


# =================================================================
# 1. 总榜 / 单类目完整榜 / Day 10 全部 tab
# =================================================================

@router.get("/hot", response_model=HotResponse)
async def hot_endpoint(
    limit: int = Query(10, ge=1, le=50),
    hours: int = Query(24, ge=1, le=168, description="最近 N 小时"),
    threshold: float = Query(0.7, ge=0.0, le=10.0, description="相关度阈值(0-1 或 0-10)"),
    category: Optional[str] = Query(None, description="L1 类目筛选"),
    mode: str = Query(
        "overall",
        pattern="^(overall|category|feed)$",
        description="overall=总榜(跨类均衡) category=单类目完整榜 feed=全部 tab(不分类,按订阅偏好加权)",
    ),
    max_per_category: int = Query(
        DEFAULT_MAX_PER_CATEGORY,
        ge=1,
        le=20,
        description="每类目最多条数(仅 overall 模式生效)",
    ),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    db = get_sync_client()[DEFAULT_DB]
    now = datetime.now(timezone.utc)
    since_iso = (now - timedelta(hours=hours)).isoformat()
    now_ts_ms = int(now.timestamp() * 1000)

    rel_threshold = threshold if threshold > 1.0 else threshold * 10.0

    # ---- mode=feed:全部 tab ----
    if mode == "feed":
        pref = _collect_user_preferences(user["id"]) if user else {
            "keywords_lower": [], "categories_l1": [], "categories_l2": [], "has_preference": False
        }
        # 没用户 / 没订阅 → 走稳定随机打散(按 item._id + 当日 hash)
        use_personalized = bool(user) and pref["has_preference"]

        match: dict = {"fetched_at": {"$gte": since_iso}}
        rel_clamped = _rel_norm_expr()
        age_h = _age_hours_expr(now_ts_ms)

        feed_pipeline: list = [
            {"$match": match},
            {
                "$addFields": {
                    "_rel_norm": rel_clamped,
                    "_age_h": {"$max": [age_h, 0.0]},
                }
            },
            {"$match": {"_rel_norm": {"$gte": rel_threshold}}},
            # 热度分(同 v2,无类目内百分位 → 跨类全量)
            {
                "$addFields": {
                    "_hot_score": {
                        "$divide": [
                            {"$divide": ["$_rel_norm", 10.0]},
                            {"$pow": [{"$add": ["$_age_h", 4.0]}, 1.2]},
                        ]
                    }
                }
            },
        ]

        if use_personalized:
            kw_lc = [k.lower() for k in pref["keywords_lower"]]
            c1_set = list(pref["categories_l1"])
            c2_set = list(pref["categories_l2"])

            feed_pipeline.extend([
                {
                    "$addFields": {
                        # keyword 命中计数(最多算 3 个,免得刷屏关键词爆分)
                        "_kw_hit": {
                            "$min": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": kw_lc,
                                            "as": "kw",
                                            "cond": {
                                                "$or": [
                                                    {"$regexMatch": {"input": {"$toLower": {"$ifNull": ["$title", ""]}}, "regex": "$$kw", "options": "i"}},
                                                    {"$regexMatch": {"input": {"$toLower": {"$ifNull": ["$summary", ""]}}, "regex": "$$kw", "options": "i"}},
                                                ]
                                            },
                                        }
                                    }
                                },
                                3.0,
                            ]
                        },
                        "_c1_hit": ({"$cond": [{"$in": ["$category_l1", c1_set]}, 1.0, 0.0]} if c1_set else {"$literal": 0.0}),
                        "_c2_hit": ({"$cond": [{"$in": ["$category", c2_set]}, 1.0, 0.0]} if c2_set else {"$literal": 0.0}),
                    }
                },
                {
                    "$addFields": {
                        # 偏好得分(0~1):keyword 命中率 0.4 + L1 命中 0.3 + L2 命中 0.3
                        "_interest_score": {
                            "$min": [
                                1.0,
                                {
                                    "$add": [
                                        {"$divide": ["$_kw_hit", 3.0]},  # 0~1
                                        {"$multiply": ["$_c1_hit", 0.3]},
                                        {"$multiply": ["$_c2_hit", 0.3]},
                                    ]
                                },
                            ]
                        },
                        # 综合分 = 热度分 × 0.6 + 偏好分 × 0.4
                        "_feed_score": {
                            "$add": [
                                {"$multiply": ["$_hot_score", 0.6]},
                                {"$multiply": ["$_interest_score", 0.4]},
                            ]
                        },
                    }
                },
                {"$sort": {"_feed_score": -1, "_hot_score": -1, "fetched_at": -1}},
                {"$limit": limit},
            ])
        else:
            # 匿名 / 无订阅:拉 limit × 4 池子 → Python 端按 id+日期 stable shuffle → 取前 limit
            pool_size = min(limit * 4, 200)
            feed_pipeline.extend([
                {"$sort": {"_hot_score": -1, "fetched_at": -1}},
                {"$limit": pool_size},
            ])

        raw_docs = list(db["items"].aggregate(feed_pipeline))

        items: List[ItemView] = []
        if use_personalized:
            for d in raw_docs:
                items.append(_to_view(d))
        else:
            # stable shuffle:md5(id + 当日) → 0~1 排序;同日稳定,跨日才换
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            raw_docs.sort(key=lambda d: _stable_seed(f"{d.get('_id','')}|{today}"))
            for d in raw_docs[:limit]:
                items.append(_to_view(d))

        return HotResponse(
            hours=hours,
            threshold=threshold,
            total=len(items),
            items=items,
            personalized=use_personalized,
            interest_keys=(
                len(pref["keywords_lower"]) + len(pref["categories_l1"]) + len(pref["categories_l2"])
                if use_personalized else 0
            ),
        )

    # ---- mode=overall / category:沿用旧逻辑 ----
    cat_filter = category if (mode == "category" and category in CATEGORY_L1) else None
    pipeline = _build_hot_pipeline(
        since_iso=since_iso,
        rel_threshold=rel_threshold,
        now_ts_ms=now_ts_ms,
        category_l1=cat_filter,
    )

    items: List[ItemView] = []

    if mode == "category":
        # 单类目:按 hot_score 排序,直接截 limit 条(不限 max_per_category)
        for d in db["items"].aggregate(pipeline):
            items.append(_to_view(d))
            if len(items) >= limit:
                break
    else:
        # 总榜:每 L1 最多 max_per_category 条,实现跨类目均衡
        cat_counts: dict[str, int] = {}
        for d in db["items"].aggregate(pipeline):
            l1 = d.get("category_l1") or "其他"
            cur = cat_counts.get(l1, 0)
            if cur >= max_per_category:
                continue
            cat_counts[l1] = cur + 1
            items.append(_to_view(d))
            if len(items) >= limit:
                break

    return HotResponse(hours=hours, threshold=threshold, total=len(items), items=items, personalized=False)


# =================================================================
# 2. 分榜汇总:一次拿 7 个 L1 的 TOP N
# =================================================================

class CategoryLeaderboard(BaseModel):
    category: str
    icon: str
    total_in_window: int = 0
    items: List[ItemView] = []


class HotCategoriesResponse(BaseModel):
    hours: int
    threshold: float
    limit_per_category: int
    categories: List[CategoryLeaderboard]


# 类目 emoji(前端 / 后端共用,只做兜底,前端可覆盖)
L1_ICON: Dict[str, str] = {
    "科技": "🔬", "AI": "🤖", "体育": "⚽", "娱乐": "🎬",
    "财经": "💰", "汽车": "🚗", "其他": "📂",
}


@router.get("/hot/categories", response_model=HotCategoriesResponse)
async def hot_categories_endpoint(
    limit: int = Query(CATEGORY_BATCH_LIMIT, ge=3, le=20, description="每个 L1 最多返回条数"),
    hours: int = Query(24, ge=1, le=168),
    threshold: float = Query(0.7, ge=0.0, le=10.0),
):
    db = get_sync_client()[DEFAULT_DB]
    now = datetime.now(timezone.utc)
    since_iso = (now - timedelta(hours=hours)).isoformat()
    now_ts_ms = int(now.timestamp() * 1000)

    rel_threshold = threshold if threshold > 1.0 else threshold * 10.0

    result: List[CategoryLeaderboard] = []
    for l1 in CATEGORY_L1:
        pipeline = _build_hot_pipeline(
            since_iso=since_iso,
            rel_threshold=rel_threshold,
            now_ts_ms=now_ts_ms,
            category_l1=l1,
        )
        items: List[ItemView] = []
        for d in db["items"].aggregate(pipeline):
            items.append(_to_view(d))
            if len(items) >= limit:
                break
        result.append(CategoryLeaderboard(
            category=l1,
            icon=L1_ICON.get(l1, "📂"),
            total_in_window=len(items),
            items=items,
        ))

    return HotCategoriesResponse(
        hours=hours,
        threshold=threshold,
        limit_per_category=limit,
        categories=result,
    )