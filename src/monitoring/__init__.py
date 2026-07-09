"""fastInfo · 实时依赖监控聚合(Mongo / Redis / Daemon / LLM / Sources / Tasks)

所有数据来源都走现成 helpers:
- MongoDB : get_sync_client().admin.command('ping')
- Redis   : redis.Redis(REDIS_URL).ping()
- LLM     : registry._providers 巡检 enabled / circuit_open / consecutive_fails
- Daemon  : data/running.pids + PS process list
- Sources : source_config.find() 聚合 is_active + consecutive_fails
- Tasks   : reap_stale_task_runs() + 最近一轮 task 状态

返回结构统一格式(给前端卡片用):
    {
        "status": "ok"|"warn"|"fail"|"unknown",
        "detail": "人类可读的一句话",
        "latency_ms": int,
        "extra": {...}  # 可选
    }
"""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# 项目根
ROOT = Path(__file__).resolve().parents[2]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(detail="OK", latency=0, **extra) -> dict:
    return {"status": "ok", "detail": detail, "latency_ms": latency, "extra": extra}


def _warn(detail: str, latency=0, **extra) -> dict:
    return {"status": "warn", "detail": detail, "latency_ms": latency, "extra": extra}


def _fail(detail: str, latency=0, **extra) -> dict:
    return {"status": "fail", "detail": detail, "latency_ms": latency, "extra": extra}


# ============================================================
# 各组件健康检查
# ============================================================

def check_mongo() -> dict:
    t0 = time.monotonic()
    try:
        from storage.mongo_writer import get_sync_client
        client = get_sync_client()
        client.admin.command("ping")
        info = client.server_info()
        latency = int((time.monotonic() - t0) * 1000)
        return _ok(
            detail=f"MongoDB {info.get('version', '?')} 正常",
            latency=latency,
            version=info.get("version"),
            db_name=os.environ.get("MONGO_DB", "fastinfo"),
        )
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _fail(detail=f"{type(e).__name__}: {str(e)[:120]}", latency=latency)


def check_redis() -> dict:
    """Redis(如有)健康检查。失败 = warn 不是 fail,因为业务暂不强依赖。

    Day 7 优化:timeout 0.3s(原来 2s),Redis 不通要快速失败别阻塞 monitoring。
    """
    t0 = time.monotonic()
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
    try:
        import redis  # 可选依赖,不存在不报错
        r = redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
        pong = r.ping()
        latency = int((time.monotonic() - t0) * 1000)
        if pong:
            info = r.info("server") or {}
            return _ok(
                detail=f"Redis {info.get('redis_version', '?')} 正常 ({url})",
                latency=latency,
                url=url,
                version=info.get("redis_version"),
            )
        return _warn("PING 返回空", latency=latency, url=url)
    except ImportError:
        return _warn("redis 库未安装(业务暂不依赖)", latency=0, url=url)
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _warn(detail=f"{type(e).__name__}: {str(e)[:80]}(业务暂不依赖)",
                     latency=latency, url=url)


def _check_process(name: str) -> dict:
    """从 data/running.pids + ps 列表中检查 fastInfo 子进程是否还活着。

    通过 PID file 拿上次启动的 PID,然后 Get-Process 看是否还在。
    """
    started_pid, started_at = _read_pid_file(name)
    alive, pids_alive = _ps_alive([started_pid] if started_pid else [])

    extra: dict[str, Any] = {
        "started_pid": started_pid,
        "log_path": started_at,
    }
    if alive:
        return _ok(detail=f"PID {started_pid} 存活", latency=0, **extra)
    script_name = "ingest_daemon.py" if name == "ingest" else "subs_scheduler.py"
    return _fail(detail=f"PID {started_pid or '?'} 已退出(daemon 未在跑)",
                 latency=0, **extra,
                 hint=f"启动: python scripts/{script_name}",
                 )


def _read_pid_file(name: str) -> tuple[int | None, str | None]:
    """从 data/running.pids 读某个 name 的 (pid, log_path)"""
    pid_file = ROOT / "data" / "running.pids"
    if not pid_file.exists():
        return None, None
    try:
        import json
        data = json.loads(pid_file.read_text(encoding="utf-8"))
        arr = data if isinstance(data, list) else [data]
        for p in arr:
            if p.get("name") == name:
                return int(p.get("pid")), p.get("log")
    except Exception:
        pass
    return None, None


# 进程 alive 状态缓存:避免每个 daemon check 单独 powershell 调用(Day 7 优化:从 2 次 → 1 次)
_PROC_CACHE: dict[str, bool] = {}
_PROC_CACHE_TS: float = 0.0
_PROC_CACHE_TTL = 2.0  # 秒


def _ps_alive(pids: list[int | None]) -> tuple[bool, set[int]]:
    """一次 powershell 调用查多个 PID 是否活着,带 2s 缓存。

    Returns:
        (any_alive, alive_pids_set)
        - any_alive: 至少一个 PID 活着
        - alive_pids_set: 活着的 PID 集合(便于批量判断)
    """
    global _PROC_CACHE, _PROC_CACHE_TS
    now = time.monotonic()
    if now - _PROC_CACHE_TS < _PROC_CACHE_TTL and _PROC_CACHE:
        return any(_PROC_CACHE.values()), {int(k) for k, v in _PROC_CACHE.items() if v}

    # 过滤掉 None 和无效值
    valid_pids = [int(p) for p in pids if p is not None]
    if not valid_pids:
        return False, set()

    try:
        pid_csv = ",".join(str(p) for p in valid_pids)
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Process -Id {pid_csv} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, timeout=3,
        )
        alive_pids = {int(line.strip()) for line in out.stdout.splitlines() if line.strip().isdigit()}
        _PROC_CACHE = {str(p): (p in alive_pids) for p in valid_pids}
        _PROC_CACHE_TS = now
        return bool(alive_pids), alive_pids
    except Exception:
        return False, set()


def _check_processes_multi(names: list[str]) -> dict[str, dict]:
    """一次 powershell 调用查多个 daemon 进程,返回每个 name 的状态 dict。

    用于 ingest_daemon + subs_scheduler 合并检查(从 3s → 1.5s)
    """
    # 1) 读所有 pid
    pid_map: dict[str, tuple[int | None, str | None]] = {n: _read_pid_file(n) for n in names}
    valid_pids = [pid for pid, _ in pid_map.values() if pid is not None]
    # 2) 一次 ps 查询
    _, alive_set = _ps_alive(valid_pids)
    # 3) 每个 name 生成结果
    out: dict[str, dict] = {}
    for name in names:
        pid, log_path = pid_map[name]
        alive = pid in alive_set if pid is not None else False
        extra: dict[str, Any] = {"started_pid": pid, "log_path": log_path}
        if alive:
            out[name] = _ok(detail=f"PID {pid} 存活", latency=0, **extra)
        else:
            script_name = "ingest_daemon.py" if name == "ingest" else "subs_scheduler.py"
            out[name] = _fail(
                detail=f"PID {pid or '?'} 已退出(daemon 未在跑)",
                latency=0, **extra,
                hint=f"启动: python scripts/{script_name}",
            )
    return out


def check_ingest_daemon() -> dict:
    return _check_process("ingest")


def check_subs_scheduler() -> dict:
    return _check_process("scheduler")


def check_api_server() -> dict:
    """API server 自检,因为它自己也跑在这个进程里。"""
    t0 = time.monotonic()
    try:
        import httpx
        host = os.environ.get("FASTINFO_BIND_HOST", "127.0.0.1")
        port = os.environ.get("FASTINFO_PORT", "8000")
        url = f"http://{host}:{port}/healthz"
        r = httpx.get(url, timeout=3.0)
        latency = int((time.monotonic() - t0) * 1000)
        if r.status_code == 200:
            j = r.json()
            return _ok(
                detail=f"API 200 (PID {os.getpid()})",
                latency=latency,
                mongo_version=j.get("mongo_version"),
                api_pid=os.getpid(),
            )
        return _warn(f"API {r.status_code}", latency=latency)
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _fail(detail=f"{type(e).__name__}: {str(e)[:120]}", latency=latency)


def _check_http_endpoint(url: str, label: str, timeout: float = 0.5) -> dict:
    """通用 HTTP 端点检查(给 web / docs 用,失败 = warn 因为不一定是 fail)

    Day 7 优化:timeout 0.5s(web/docs 不是强依赖,不可达要快速失败)
    """
    t0 = time.monotonic()
    try:
        import httpx
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        latency = int((time.monotonic() - t0) * 1000)
        if 200 <= r.status_code < 400:
            return _ok(detail=f"{label} HTTP {r.status_code}", latency=latency, url=url)
        return _warn(detail=f"{label} HTTP {r.status_code}", latency=latency, url=url)
    except ImportError:
        return _warn(detail=f"{label}: httpx 未安装", latency=0, url=url)
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _warn(detail=f"{label} {type(e).__name__}: {str(e)[:80]}", latency=latency, url=url)


def check_web() -> dict:
    """前端 Vue Web 健康检查。

    优先级:FASTINFO_WEB_URL > FASTINFO_WEB_PORT > 本地 vite dev (5173) > docker nginx (18080/28080)。
    失败 = warn:web 不是强依赖,本地纯 CLI / API 也能跑。
    """
    explicit = os.environ.get("FASTINFO_WEB_URL")
    candidates = []
    if explicit:
        candidates.append(explicit)
    host = os.environ.get("FASTINFO_BIND_HOST", "127.0.0.1")
    web_port = os.environ.get("FASTINFO_WEB_PORT")
    if web_port:
        candidates.append(f"http://{host}:{web_port}/")
    # vite dev (5173) / docker nginx 预发(18080) / docker nginx 测试(28080) / 自定义端口
    candidates.extend([
        f"http://{host}:5173/",
        f"http://{host}:18080/",
        f"http://{host}:28080/",
        f"http://{host}:8080/",
    ])
    # Docker 容器内部通过 compose service 名访问 web 容器
    if os.environ.get("APP_ENV") == "docker":
        candidates.insert(0, "http://web/")
    last_err = None
    for url in candidates:
        result = _check_http_endpoint(url, "Web", timeout=2.0)
        if result["status"] == "ok":
            return result
        last_err = result
    # 都没 ok → 把最后一个 warn 结果返出去,detail 加个 hint
    if last_err:
        last_err["hint"] = "如不需要 Web 可忽略;启动方式:cd frontend && npm run dev"
    return last_err or _warn("Web: 未尝试任何 endpoint")


def check_docs() -> dict:
    """文档站 VitePress 健康检查。

    优先级:FASTINFO_DOCS_URL > FASTINFO_WEB_PORT/docs/ > 本地 vitepress dev (5174) > docker nginx (18080/docs/ / 28080/docs/)。
    失败 = warn:docs 不影响主功能。
    """
    explicit = os.environ.get("FASTINFO_DOCS_URL")
    candidates = []
    if explicit:
        candidates.append(explicit)
    host = os.environ.get("FASTINFO_BIND_HOST", "127.0.0.1")
    web_port = os.environ.get("FASTINFO_WEB_PORT")
    if web_port:
        candidates.append(f"http://{host}:{web_port}/docs/")
    candidates.extend([
        f"http://{host}:5174/",
        f"http://{host}:18080/docs/",
        f"http://{host}:28080/docs/",
    ])
    # Docker 容器内部通过 compose service 名访问 web 容器
    if os.environ.get("APP_ENV") == "docker":
        candidates.insert(0, "http://web/docs/")
    last_err = None
    for url in candidates:
        result = _check_http_endpoint(url, "Docs", timeout=2.0)
        if result["status"] == "ok":
            return result
        last_err = result
    if last_err:
        last_err["hint"] = "启动方式:cd docs-site && npm run dev"
    return last_err or _warn("Docs: 未尝试任何 endpoint")


def _check_daemon_docker() -> dict:
    """Docker 模式下 daemon 是独立容器,无法通过宿主机 PID 检查。

    改通过 task_runs 最近运行时间来判断 daemon 是否真正在工作:
      - 2h 内有运行          → ok
      - 2h~24h 内有运行      → warn
      - 超过 24h 无运行 / 无记录 → fail
    """
    t0 = time.monotonic()
    try:
        from storage.mongo_writer import get_db
        db = get_db()
        now_utc = datetime.now(timezone.utc)
        recent = db["task_runs"].find_one(sort=[("started_at", -1)])
        latency = int((time.monotonic() - t0) * 1000)
        extra = {
            "mode": "docker",
            "ingest": _ok("Docker 模式:通过 task_runs 判断", mode="docker"),
            "subs_scheduler": _ok("Docker 模式:通过 task_runs 判断", mode="docker"),
        }
        if not recent:
            return _warn(
                detail="Docker 模式:未找到 task_runs 记录(daemon 可能尚未跑过任务)",
                latency=latency,
                hint="请检查 docker compose ps 中 ingest_daemon / subs_scheduler 是否 healthy",
                **extra,
            )
        started = _to_aware(recent.get("started_at"))
        age_hr = (now_utc - started).total_seconds() / 3600.0 if started else None
        extra["recent_run"] = recent.get("run_id")
        extra["recent_run_started_at"] = started.isoformat() if started else None
        extra["recent_run_age_hr"] = round(age_hr, 2) if age_hr is not None else None

        if age_hr is None or age_hr > 24:
            return _fail(
                detail=f"Docker 模式:超过 24h 无任务运行(最近 {age_hr:.1f}h 前)",
                latency=latency,
                hint="请检查 ingest_daemon 容器日志: docker compose logs -f ingest_daemon",
                **extra,
            )
        if age_hr > 2:
            return _warn(
                detail=f"Docker 模式:最近任务 {age_hr:.1f}h 前运行",
                latency=latency,
                hint="daemon 可能仍在启动中或调度间隔较长",
                **extra,
            )
        return _ok(
            detail=f"Docker 模式:daemon 健康,最近任务 {age_hr:.1f}h 前运行",
            latency=latency,
            **extra,
        )
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _fail(
            detail=f"Docker 模式:检查失败 {type(e).__name__}: {str(e)[:120]}",
            latency=latency,
            mode="docker",
        )


def check_daemon() -> dict:
    """聚合 ingest_daemon + subs_scheduler 的健康状态(Day 7 改:用户期望 daemon 一个卡片)

    Day 7 优化:用 _check_processes_multi 一次 ps 调用查两个进程(原 3s → 1.5s)
    Docker 模式下改用 task_runs 时间判断,因为跨容器无法查 PID。
    """
    if os.environ.get("APP_ENV") == "docker":
        return _check_daemon_docker()

    t0 = time.monotonic()
    results = _check_processes_multi(["ingest", "scheduler"])
    ingest = results.get("ingest") or _fail("ingest check failed", latency=0)
    scheduler = results.get("scheduler") or _fail("scheduler check failed", latency=0)
    extra = {"ingest": ingest, "subs_scheduler": scheduler}
    statuses = [ingest["status"], scheduler["status"]]
    latency = int((time.monotonic() - t0) * 1000)
    if "fail" in statuses:
        return _fail(detail=f"daemon 有进程挂掉 (ingest={ingest['status']}, sched={scheduler['status']})",
                     latency=latency, **extra)
    if "warn" in statuses:
        return _warn(detail=f"daemon 部分告警", latency=latency, **extra)
    return _ok(detail=f"ingest + scheduler 双进程都存活", latency=latency, **extra)


def check_sources() -> dict:
    """source_config 总览 + disabled 列表"""
    t0 = time.monotonic()
    try:
        from storage.source_config import list_sources
        from storage.mongo_writer import get_db
        # 主动 reap 一遍僵尸 task(让监控顺手清理)
        try:
            from storage.mongo_writer import reap_stale_task_runs
            reaped = reap_stale_task_runs()
        except Exception:
            reaped = 0

        all_sources = list_sources()
        active = [s for s in all_sources if s.get("is_active")]
        disabled = [s for s in all_sources if not s.get("is_active")]

        # 找出每个 disabled 的最近一次失败原因(从 source_runs)
        db = get_db()
        def _iso(v):
            if v is None:
                return None
            if hasattr(v, "isoformat"):
                return v.isoformat()
            return str(v)

        def _to_aware(dt_like):
            """Mongo 里的 datetime 可能是 tz-aware 也可能 naive,统一 tz-aware"""
            if dt_like is None:
                return None
            if isinstance(dt_like, str):
                try:
                    dt_like = datetime.fromisoformat(dt_like.replace("Z", "+00:00"))
                except Exception:
                    return None
            if isinstance(dt_like, datetime):
                if dt_like.tzinfo is None:
                    dt_like = dt_like.replace(tzinfo=timezone.utc)
                return dt_like
            return None

        disabled_with_reasons: list[dict] = []
        for s in disabled:
            sid = s.get("source_id")
            last = db["source_runs"].find_one(
                {"source_id": sid}, sort=[("started_at", -1)]
            )
            disabled_with_reasons.append({
                "source_id": sid,
                "display_name": s.get("display_name", sid),
                "consecutive_fails": s.get("consecutive_fails", 0),
                "last_error": (last or {}).get("error_msg", "?")[:100],
                "last_error_code": (last or {}).get("error_code"),
                "last_run_at": _iso((last or {}).get("started_at")),
            })

        # 最近一轮 task_run 是否有新数据(近 2h)
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(hours=2)
        recent_run = db["task_runs"].find_one(
            {"started_at": {"$gte": cutoff}},
            sort=[("started_at", -1)],
        )
        staleness_hr: float | None = None
        if recent_run:
            started = _to_aware(recent_run.get("started_at"))
            if started is not None:
                staleness_hr = round((now_utc - started).total_seconds() / 3600.0, 2)

        latency = int((time.monotonic() - t0) * 1000)
        overall: dict
        if len(disabled) >= 5:
            overall = _warn(
                detail=f"{len(active)} 启用 / {len(disabled)} 禁用",
                latency=latency,
                total=len(all_sources),
                active=len(active),
                disabled=len(disabled),
                disabled_detail=disabled_with_reasons,
                reaped_stale_tasks=reaped,
                last_run_age_hr=staleness_hr,
            )
        else:
            overall = _ok(
                detail=f"{len(active)} 启用 / {len(disabled)} 禁用",
                latency=latency,
                total=len(all_sources),
                active=len(active),
                disabled=len(disabled),
                disabled_detail=disabled_with_reasons,
                reaped_stale_tasks=reaped,
                last_run_age_hr=staleness_hr,
            )
        return overall
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _fail(detail=f"{type(e).__name__}: {str(e)[:120]}", latency=latency)


def _to_aware(dt_like):
    """Mongo datetime 可能是 tz-aware 也可能 naive,统一成 tz-aware UTC。"""
    if dt_like is None:
        return None
    if isinstance(dt_like, str):
        try:
            dt_like = datetime.fromisoformat(dt_like.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(dt_like, datetime):
        if dt_like.tzinfo is None:
            return dt_like.replace(tzinfo=timezone.utc)
        return dt_like
    return None


def check_tasks() -> dict:
    """task_runs 运行中 / 僵尸 / 最近一轮情况"""
    t0 = time.monotonic()
    try:
        from storage.mongo_writer import get_db, reap_stale_task_runs, STALE_RUNNING_THRESHOLD_SEC
        db = get_db()

        # 主动 reap(让监控随手清理)
        reaped = reap_stale_task_runs()

        now_utc = datetime.now(timezone.utc)

        # 当前 running
        running_cur = list(db["task_runs"].find({"status": "running"}).sort("started_at", 1))
        running_cur_ser = [{
            "run_id": r["run_id"],
            "started_at": r["started_at"].isoformat() if hasattr(r.get("started_at"), "isoformat") else str(r.get("started_at")),
            "trigger": r.get("trigger"),
            "operator": r.get("operator"),
            "age_sec": round((now_utc - _to_aware(r.get("started_at"))).total_seconds()) if r.get("started_at") else None,
        } for r in running_cur]

        # 真僵尸(已超过 threshold)
        running_stuck = sum(
            1 for r in running_cur
            if (now_utc - _to_aware(r.get("started_at"))).total_seconds() > STALE_RUNNING_THRESHOLD_SEC
            if r.get("started_at")
        )

        # 最近一轮
        recent = db["task_runs"].find_one(sort=[("started_at", -1)])
        recent_ser = None
        if recent:
            recent_ser = {
                "run_id": recent.get("run_id"),
                "started_at": recent.get("started_at").isoformat() if hasattr(recent.get("started_at"), "isoformat") else str(recent.get("started_at")),
                "ended_at": recent.get("ended_at").isoformat() if hasattr(recent.get("ended_at"), "isoformat") else str(recent.get("ended_at")),
                "status": recent.get("status"),
                "items_fetched": recent.get("items_fetched", 0),
                "items_summarized": recent.get("items_summarized", 0),
                "items_failed": recent.get("items_failed", 0),
                "warning": recent.get("warning", ""),
            }

        # 24h failure rate
        cutoff_24 = now_utc - timedelta(hours=24)
        agg = list(db["task_runs"].aggregate([
            {"$match": {"started_at": {"$gte": cutoff_24}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]))
        status_breakdown = {a["_id"]: a["count"] for a in agg}

        total_24h = sum(status_breakdown.values())
        failed_24h = status_breakdown.get("failed", 0)
        fail_rate = (failed_24h / total_24h) if total_24h else 0.0

        # 综合判定
        status_lbl = "ok"
        detail = f"{len(running_cur)} running · 24h {total_24h} 次 (failed {failed_24h})"
        if running_stuck > 0 or fail_rate > 0.3:
            status_lbl = "fail"
            detail = f"{running_stuck} 僵尸 running 卡住 · 24h fail rate {fail_rate:.0%}"
        elif reaped > 0 or len(running_cur) > 3 or fail_rate > 0.1:
            status_lbl = "warn"
            if reaped > 0:
                detail = f"刚刚清理 {reaped} 个僵尸 · 24h fail rate {fail_rate:.0%}"
            else:
                detail = f"{len(running_cur)} running · 24h fail rate {fail_rate:.0%}"

        d: dict = {
            "status": status_lbl,
            "detail": detail,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "extra": {
                "running_now": running_cur_ser,
                "running_stuck": running_stuck,
                "reaped_stale": reaped,
                "stale_threshold_sec": STALE_RUNNING_THRESHOLD_SEC,
                "recent_run": recent_ser,
                "status_24h": status_breakdown,
                "fail_rate_24h": round(fail_rate, 3),
            },
        }
        return d
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _fail(detail=f"{type(e).__name__}: {str(e)[:120]}", latency=latency)


# LLM registry module-level cache(Day 7 优化:避免每次 build + aclose)
# 注意:registry 内部的熔断器/consecutive_fails 是动态的,但 provider 注册表不会变
_LLM_REGISTRY_CACHE = None
_LLM_REGISTRY_LOCK = None  # 懒加载,避免 import 时就 require threading


def _get_llm_registry():
    """懒加载 + module-level cache,避免每次 monitoring 都 build_default_registry()

    用双重检查锁避免 ThreadPoolExecutor 9 个线程同时首次 build(否则会 build 9 次浪费 8s × 9)
    """
    global _LLM_REGISTRY_CACHE, _LLM_REGISTRY_LOCK
    if _LLM_REGISTRY_LOCK is None:
        import threading
        _LLM_REGISTRY_LOCK = threading.Lock()
    if _LLM_REGISTRY_CACHE is None:
        with _LLM_REGISTRY_LOCK:
            if _LLM_REGISTRY_CACHE is None:
                from llm.model_registry import build_default_registry
                _LLM_REGISTRY_CACHE = build_default_registry()
    return _LLM_REGISTRY_CACHE


def check_llm() -> dict:
    """LLM provider 健康状态(读 registry 内部状态,不真打 LLM)

    Registry 结构:
      registry.groups[group_name].providers[i]:
        - cfg.id      str    provider id("m2_7_highspeed" / "kimi_k2_6" 等)
        - cfg.api_key str|None
        - breaker.is_open bool
        - cooldown.consecutive_failures int

    Day 7 优化:registry 进程级缓存 + 不再每次 aclose(原 8s → 50ms)
    """
    t0 = time.monotonic()
    try:
        registry = _get_llm_registry()

        # 聚合:每个 unique provider 只看一次(跨 group dedup)
        seen: dict[str, dict] = {}
        for gname, group in getattr(registry, "groups", {}).items():
            for p in getattr(group, "providers", []) or []:
                cfg = getattr(p, "cfg", None)
                if cfg is None:
                    continue
                pid = getattr(cfg, "id", "?")
                api_key = getattr(cfg, "api_key", None) or ""
                breaker = getattr(p, "breaker", None)
                circuit_open = bool(getattr(breaker, "is_open", False)) if breaker else False
                cooldown = getattr(p, "cooldown", None)
                fails = int(getattr(cooldown, "consecutive_failures", 0)) if cooldown else 0
                if pid not in seen:
                    seen[pid] = {
                        "name": pid,
                        "enabled": bool(api_key),
                        "circuit_open": circuit_open,
                        "consecutive_fails": fails,
                        "key_configured": bool(api_key),
                        "groups": [],
                    }
                if gname not in seen[pid]["groups"]:
                    seen[pid]["groups"].append(gname)

        providers_lite = list(seen.values())
        # 不再每次 aclose(registry 在进程生命周期内复用)

        latency = int((time.monotonic() - t0) * 1000)
        if not providers_lite:
            return _warn("Registry 无 provider 记录", latency=latency)
        configured = [p for p in providers_lite if p["key_configured"]]
        open_breakers = [p for p in providers_lite if p["circuit_open"]]

        if not configured:
            return _fail(
                detail="所有 provider 都未配置 API Key",
                latency=latency, providers=providers_lite,
            )
        if open_breakers:
            return _warn(
                detail=f"{len(open_breakers)} 个熔断器打开 ({', '.join(p['name'] for p in open_breakers)})",
                latency=latency, providers=providers_lite,
            )
        return _ok(
            detail=f"{len(configured)} provider 已配置,4 个 group 全部就绪",
            latency=latency, providers=providers_lite,
        )
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return _fail(detail=f"{type(e).__name__}: {str(e)[:120]}", latency=latency)


# ============================================================
# 总入口
# ============================================================

# ============================================================
# Module-level TTL 缓存(Day 7 优化)
# 前端默认 5s 轮询,但 collect_monitoring 自身也耗时(原 16s)
# 加 2s TTL 让 5s 内的重复请求直接走缓存
# ============================================================
_COLLECT_CACHE: dict | None = None
_COLLECT_CACHE_TS: float = 0.0
_COLLECT_CACHE_TTL = 2.0  # 秒


def _run_checks_parallel(checks: list[tuple[str, callable]]) -> dict[str, dict]:
    """用 ThreadPoolExecutor 并行执行 check 函数。

    每个 check 内部可能 import 模块/做 I/O,放线程池里并发跑。
    慢源(llm 8s / daemon 3s)不再阻塞快源(mongo 200ms)。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out: dict[str, dict] = {}
    if not checks:
        return out
    # max_workers = len(checks) 让所有 check 同时启动
    with ThreadPoolExecutor(max_workers=len(checks)) as ex:
        future_map = {ex.submit(fn): name for name, fn in checks}
        for fut in as_completed(future_map):
            name = future_map[fut]
            try:
                out[name] = fut.result()
            except Exception as e:
                out[name] = _fail(detail=f"{type(e).__name__}: {str(e)[:120]}", latency=0)
    return out


def collect_monitoring() -> dict:
    """聚合所有依赖,返回前端卡片需要的数据。

    结构按 Day 7 重构:三组
      - services: 影响当前使用的服务(web / api / docs / mongo / daemon)
      - tasks:    任务运行情况(自动 reap 僵尸)
      - resources: 其他资源(redis / sources 总览 / llm 路由)

    overall 优先级(只看 services + tasks 两组,resources 走 warn 不影响整体):
      - 任一 fail     → "fail"
      - 任一 warn     → "warn"
      - 全 ok         → "ok"

    Day 7 优化:
      1. ThreadPoolExecutor 并行(原 16s → 1s 内)
      2. module-level 2s TTL 缓存(防 5s 轮询击穿)
    """
    global _COLLECT_CACHE, _COLLECT_CACHE_TS
    now = time.monotonic()
    if _COLLECT_CACHE is not None and (now - _COLLECT_CACHE_TS) < _COLLECT_CACHE_TTL:
        return _COLLECT_CACHE

    # 9 个 check 并行跑
    checks = [
        ("web", check_web),
        ("api_server", check_api_server),
        ("docs", check_docs),
        ("mongo", check_mongo),
        ("daemon", check_daemon),
        ("tasks", check_tasks),
        ("redis", check_redis),
        ("sources", check_sources),
        ("llm", check_llm),
    ]
    flat = _run_checks_parallel(checks)

    services = {
        "web": flat["web"],
        "api_server": flat["api_server"],
        "docs": flat["docs"],
        "mongo": flat["mongo"],
        "daemon": flat["daemon"],
    }
    tasks_group = {"tasks": flat["tasks"]}
    resources = {
        "redis": flat["redis"],
        "sources": flat["sources"],
        "llm": flat["llm"],
    }

    core = {**services, **tasks_group}
    if any(c.get("status") == "fail" for c in core.values()):
        overall = "fail"
    elif any(c.get("status") == "warn" for c in core.values()):
        overall = "warn"
    else:
        overall = "ok"

    result = {
        "checked_at": _now(),
        "overall": overall,
        "groups": {
            "services": services,
            "tasks": tasks_group,
            "resources": resources,
        },
        "components": {**services, **tasks_group, **resources},
    }

    _COLLECT_CACHE = result
    _COLLECT_CACHE_TS = time.monotonic()
    return result
