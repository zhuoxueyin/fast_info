"""GET /api/stats · MongoDB 状态/索引"""
from fastapi import APIRouter

from storage.mongo_writer import get_sync_client, DEFAULT_DB, stats as mongo_stats
from ..schemas import StatsResponse

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def stats_endpoint():
    db = get_sync_client()[DEFAULT_DB]
    s = mongo_stats()
    indexes: list[str] = []
    for coll in ("items", "subscriptions", "subscriptions_delivered", "users"):
        try:
            for ix in db[coll].list_indexes():
                indexes.append(f"{coll}.{ix['name']}")
        except Exception:
            pass
    return StatsResponse(
        total_items=s.get("total", 0),
        by_source={x["_id"]: x["count"] for x in s.get("by_source", []) if x.get("_id")},
        by_category={x["_id"]: x["count"] for x in s.get("by_category", []) if x.get("_id")},
        indexes=indexes,
    )
