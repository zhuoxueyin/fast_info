"""
fastInfo · 管理员路由
=====================
- 爬取任务时间线 / 明细
- 7 个 RSS 源 24h 状态
- LLM 模型组健康(熔断状态)
- 全部用户 / 全部订阅 / 全部推送(管理员视角)
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from pydantic import BaseModel

from api.deps_admin import require_admin
from storage.mongo_writer import (
    get_db,
    get_recent_task_runs,
    get_task_run,
    get_task_run_status,
    reap_stale_task_runs,
    get_source_status_24h,
    count_items,
    DEFAULT_DB,
)
from llm.model_registry import build_default_registry
from api.schemas import TaskRun, SourceStatus, LLMHealth

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tasks/runs", response_model=list[TaskRun])
def list_task_runs(
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """爬取任务时间线(最近 N 条)"""
    # 每次列表自动回收僵尸 running(进程崩溃/被 kill 后残留的记录)
    reaped = reap_stale_task_runs()
    if reaped > 0:
        print(f"[task_runs] reaped {reaped} stale running tasks", flush=True)
    return get_recent_task_runs(limit=limit)


@router.get("/tasks/runs/{run_id}", response_model=TaskRun)
def get_task_run_detail(
    run_id: str,
    admin: dict = Depends(require_admin),
):
    """单次抓取明细"""
    doc = get_task_run(run_id)
    if not doc:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"run_id={run_id} 不存在")
    return doc


@router.get("/tasks/runs/{run_id}/trace")
def get_task_run_trace(
    run_id: str,
    admin: dict = Depends(require_admin),
):
    """调用树跟踪:返回 task_run + 关联的所有 source_runs,用于构建执行全貌。

    返回结构:
        {
            "task_run": { ... },          # 顶层任务
            "source_runs": [ ... ],       # 每源执行明细(按时间排序)
            "summary": {                  # 聚合摘要
                "total_sources": int,
                "ok_sources": int,
                "fail_sources": int,
                "disabled_sources": int,
                "total_duration_ms": int,
            }
        }
    """
    from storage.source_runs import get_runs_by_task_run_id
    task = get_task_run(run_id)
    if not task:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"run_id={run_id} 不存在")
    source_runs = get_runs_by_task_run_id(run_id)

    # 补全"未爬取"的源:全量注册源 - 实际跑了的源
    ran_ids = {r.get("source_id") for r in source_runs}
    all_sources: dict[str, str] = {}  # source_id -> display_name
    try:
        from crawler.sources import RSS_SOURCES, KOL_SOURCES
        for sid, (name, _url) in RSS_SOURCES.items():
            all_sources[sid] = name
        for key, (name, _kind) in KOL_SOURCES.items():
            all_sources[key] = name
    except Exception:
        pass

    # 查 source_config 区分"禁用"vs"时间未到"
    active_set: set[str] = set()
    try:
        from storage.source_config import list_sources
        for sc in list_sources():
            if sc.get("is_active", True):
                active_set.add(sc.get("source_id"))
    except Exception:
        pass

    skipped_disabled: list[dict] = []
    skipped_not_due: list[dict] = []
    for sid, name in all_sources.items():
        if sid in ran_ids:
            continue
        if sid not in active_set:
            skipped_disabled.append({
                "source_id": sid,
                "status": "disabled",
                "display_name": name,
                "fetched_count": 0,
                "new_count": 0,
                "summarized_count": 0,
                "failed_count": 0,
                "duration_ms": 0,
                "error_code": "DISABLED",
                "error_msg": "源已禁用",
                "started_at": None,
                "ended_at": None,
            })
        else:
            skipped_not_due.append({
                "source_id": sid,
                "status": "not_due",
                "display_name": name,
                "fetched_count": 0,
                "new_count": 0,
                "summarized_count": 0,
                "failed_count": 0,
                "duration_ms": 0,
                "error_code": "NOT_DUE",
                "error_msg": "时间未到，本次任务未调度",
                "started_at": None,
                "ended_at": None,
            })

    ok = sum(1 for r in source_runs if r.get("status") == "ok")
    partial = sum(1 for r in source_runs if r.get("status") == "partial")
    fail = sum(1 for r in source_runs if r.get("status") == "fail")
    disabled = sum(1 for r in source_runs if r.get("status") == "disabled") + len(skipped_disabled)
    not_due = len(skipped_not_due)
    total_dur = sum(int(r.get("duration_ms", 0)) for r in source_runs)
    return {
        "task_run": task,
        "source_runs": source_runs + skipped_disabled + skipped_not_due,
        "summary": {
            "total_sources": len(source_runs) + len(skipped_disabled) + len(skipped_not_due),
            "ok_sources": ok,
            "partial_sources": partial,
            "fail_sources": fail,
            "disabled_sources": disabled,
            "not_due_sources": not_due,
            "total_duration_ms": total_dur,
        },
    }


@router.get("/tasks/source-status", response_model=list[SourceStatus])
def source_status(admin: dict = Depends(require_admin)):
    """7 个 RSS 源 24h 抓取状态"""
    raw = get_source_status_24h()
    out = []
    for d in raw:
        failed = d.get("failed_24h", 0) or 0
        fetched = d.get("fetched_24h", 0) or 0
        healthy = (fetched > 0 and failed / max(fetched, 1) < 0.5) or fetched == 0
        out.append({
            "source": d.get("_id", "?"),
            "fetched_24h": fetched,
            "failed_24h": failed,
            "last_run_at": (d.get("last_run_at").isoformat() if d.get("last_run_at") else None),
            "last_latency_ms": d.get("last_latency_ms", 0) or 0,
            "healthy": healthy,
        })
    return out


@router.get("/llm/health", response_model=LLMHealth)
def llm_health(admin: dict = Depends(require_admin)):
    """LLM 模型组 × provider 状态(优先级 / 权重)"""
    from llm.model_registry import DEFAULT_GROUPS_SPEC
    groups: dict = {}
    for spec in DEFAULT_GROUPS_SPEC:
        gname = spec["name"]
        groups[gname] = {}
        for p in spec["providers"]:
            groups[gname][p["id"]] = {
                "priority": p["priority"],
                "weight": p.get("weight", 1),
                "model": p.get("model"),
                "max_tokens": p.get("max_tokens"),
                "protocol": p.get("protocol", "openai"),
            }
    return {"groups": groups}


@router.get("/users")
def list_all_users(admin: dict = Depends(require_admin)):
    """管理员:全部用户"""
    from datetime import datetime
    def _iso(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)
    db = get_db()
    out = []
    for u in db["users"].find({}, {"password_hash": 0}):
        out.append({
            "id": str(u.get("_id")),
            "username": u.get("username"),
            "email": u.get("email"),
            "role": u.get("role", "user"),
            "plan": u.get("plan", "free"),
            "created_at": _iso(u.get("created_at")),
            "last_login_at": _iso(u.get("last_login_at")),
        })
    return {"total": len(out), "items": out}


@router.get("/subscriptions")
def list_all_subscriptions(admin: dict = Depends(require_admin)):
    """管理员:全部订阅(每用户)"""
    db = get_db()
    out = []
    for s in db["subscriptions"].find().sort("created_at", -1 if hasattr(db["subscriptions"], "created_at") else 1).limit(500):
        out.append({
            "id": str(s.get("_id")),
            "user_id": s.get("user_id"),
            "title": s.get("title"),
            "nl_query": s.get("nl_query"),
            "keywords": s.get("keywords", []),
            "categories": s.get("categories", []),
            "cron_expr": s.get("cron_expr"),
            "is_active": s.get("is_active", True),
            "run_count": s.get("run_count", 0),
            "error_count": s.get("error_count", 0),
        })
    return {"total": len(out), "items": out}


@router.get("/stats")
def admin_stats(admin: dict = Depends(require_admin)):
    """管理员:汇总统计(总 items / 总用户 / 总订阅 / 总推送 + 类目 / 源分布)"""
    db = get_db()
    return {
        "total_items": db["items"].count_documents({}),
        "total_users": db["users"].count_documents({}),
        "total_subscriptions": db["subscriptions"].count_documents({}),
        "total_delivered": db["subscriptions_delivered"].count_documents({}),
        "by_source": list(db["items"].aggregate([
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
        "by_category": list(db["items"].aggregate([
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
        "by_user": list(db["subscriptions"].aggregate([
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])),
    }


@router.post("/ingest/run")
async def admin_ingest_run(
    limit: int = Query(8, ge=1, le=30),
    background: BackgroundTasks = None,  # FastAPI 注入
    admin: dict = Depends(require_admin),
):
    """管理员:手动触发一次抓取(Day 5 改造为异步)。

    立刻返回 {run_id, status: "running", limit},run_once 在后台跑。
    前端用 GET /admin/ingest/task/{run_id} 轮询直到 status="done"。
    """
    import asyncio
    import uuid
    from scripts.ingest_daemon import run_once

    class _Args:
        pass
    args = _Args()
    args.limit = limit
    args.trigger = "manual"
    args.operator = admin.get("username") or str(admin.get("_id"))
    args.run_id = str(uuid.uuid4())  # Day 5:传给 run_once,保证 task_runs run_id 一致

    run_id = args.run_id

    async def _bg():
        try:
            await run_once(args)
        except Exception as e:
            from storage.mongo_writer import update_task_run_finished
            update_task_run_finished(run_id, {
                "finished_at": datetime.now(timezone.utc),
                "status": "failed",
                "warning": f"后台任务异常: {type(e).__name__}: {str(e)[:200]}",
            })
            print(f"[ingest_bg] run_id={run_id} crashed: {e}", flush=True)

    # 先写一条 running 占位记录(让前端立刻能查到)
    from storage.mongo_writer import create_task_run_pending
    create_task_run_pending({
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc),
        "trigger": "manual",
        "operator": args.operator,
        "limit": limit,
    })

    print(f"[ingest_run] scheduled run_id={run_id} operator={args.operator} limit={limit}", flush=True)

    # 用 FastAPI BackgroundTasks(确保 response 后任务真的跑)
    if background is not None:
        # BackgroundTasks 不支持 async coroutine,包成 sync wrapper
        def _bg_wrapper():
            asyncio.run(_bg())
        background.add_task(_bg_wrapper)
    else:
        # 兜底
        asyncio.create_task(_bg())

    return {
        "run_id": run_id,
        "status": "running",
        "trigger": "manual",
        "operator": args.operator,
        "limit": limit,
    }


@router.get("/ingest/task/{run_id}")
def admin_get_ingest_task(
    run_id: str,
    admin: dict = Depends(require_admin),
):
    """管理员:查一次手动 ingest 任务的状态(给前端轮询用)。

    返回:
      - status: "running" / "done" / "failed"
      - finished_at: None=还在跑
      - items_fetched / items_summarized / items_failed
      - warning: 失败原因
    """
    doc = get_task_run_status(run_id)
    if not doc:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"run_id={run_id} 不存在")
    return doc


# ============================================================
# Day 4:二级分类体系
# ============================================================
@router.get("/taxonomy")
def admin_get_taxonomy(admin: dict = Depends(require_admin)):
    """返回 L1 / L2 分类树(给前端订阅页用)"""
    from crawler.sources import CATEGORY_L1, CATEGORY_L2
    return {"l1": CATEGORY_L1, "l2": CATEGORY_L2}


# ============================================================
# Day 5+ :实时依赖监控
# ============================================================

@router.get("/monitoring")
def admin_monitoring(admin: dict = Depends(require_admin)):
    """管理员:聚合所有依赖的实时状态(Mongo/Redis/Daemon/LLM/Sources/Tasks)。

    给 MonitoringPage 用,前端可 5s 自动刷新。
    """
    from monitoring import collect_monitoring
    return collect_monitoring()


@router.post("/tasks/reap-stale")
def admin_reap_stale(admin: dict = Depends(require_admin)):
    """管理员:手动触发僵尸 task 回收(running > 30min → 标 failed)。"""
    from storage.mongo_writer import reap_stale_task_runs
    n = reap_stale_task_runs()
    return {"reaped": n}


@router.post("/source/{source_id}/enable")
def admin_enable_source(
    source_id: str,
    admin: dict = Depends(require_admin),
):
    """管理员:重启用某个 disabled 源(把 is_active=True,consecutive_fails=0)。"""
    from datetime import datetime, timezone
    from storage.source_config import get_source
    from storage.mongo_writer import get_db
    s = get_source(source_id)
    if not s:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"source_id={source_id} 不存在")
    db = get_db()
    db["source_config"].update_one(
        {"source_id": source_id},
        {"$set": {
            "is_active": True,
            "consecutive_fails": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"source_id": source_id, "is_active": True}


@router.post("/source/{source_id}/restart-daemon")
def admin_restart_ingest(admin: dict = Depends(require_admin)):
    """管理员:重启 ingest_daemon 进程(Windows)。

    实际是 kill PID + 启动新进程(在 daemon exit 后 start.ps1 应该有兜底,
    但这里给一个手动 emergency trigger)。
    """
    import json, subprocess
    # admin.py 在 src/api/routes/,回到项目根要 parents[3]
    root = Path(__file__).resolve().parents[3]
    pid_file = root / "data" / "running.pids"
    python_exe = root / ".venv" / "Scripts" / "python.exe"
    cmd = [str(python_exe), "scripts/ingest_daemon.py", "--interval", "1800"]
    if not python_exe.exists():
        return {"restarted": False, "reason": f"venv python not found: {python_exe}"}
    if pid_file.exists():
        try:
            data = json.loads(pid_file.read_text(encoding="utf-8"))
            arr = data if isinstance(data, list) else [data]
            for p in arr:
                if p.get("name") == "ingest":
                    pid = int(p.get("pid"))
                    try:
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command",
                             f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
                            capture_output=True, timeout=5,
                        )
                    except Exception:
                        pass
                    break
        except Exception:
            pass
    # 启动新 daemon(后台)
    try:
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            cmd, cwd=str(root),
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdout=open(root / "data" / "ingest.log", "ab"),
            stderr=open(root / "data" / "ingest.err.log", "ab"),
        )
        return {"restarted": True, "command": " ".join(cmd), "cwd": str(root)}
    except Exception as e:
        return {"restarted": False, "reason": f"{type(e).__name__}: {e}"}