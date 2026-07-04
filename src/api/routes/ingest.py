"""POST /api/ingest/run · 触发一次抓取+摘要"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from typing import Optional

from auth import require_user as _require  # 重命名避免冲突
from ..deps import require_user
from ..schemas import IngestResponse

router = APIRouter(tags=["ingest"])


@router.post("/ingest/run", response_model=IngestResponse)
async def run_ingest_endpoint(
    limit: int = Query(8, ge=1, le=20, description="每源抓多少条"),
    user: dict = Depends(require_user),
):
    """跑一次 ingest(RSS 抓取 + LLM 摘要 + 入库)。

    注意:会调用 LLM,会消耗 API 额度(限频时用 limit=2-4)。
    """
    from scripts.ingest_daemon import run_once

    class _Args:
        pass
    args = _Args()
    args.limit = limit
    r = await run_once(args)
    return IngestResponse(
        fetched=r["fetched"],
        new=r["new"],
        summarized=r["summarized"],
        failed=r["failed"],
        errors=[r["warning"]] if r.get("warning") else [],
        warning=r.get("warning", ""),
    )
