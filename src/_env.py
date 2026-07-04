"""
fastInfo · 集中环境变量加载器
============================

设计目标:
1. **本地开发** (venv + python 直接跑):
   自动加载 项目根目录/.env → os.environ
2. **Docker 部署**:
   自动加载 /app/.env (compose volume 挂进来的) → os.environ
3. **不破坏已有行为**:
   - 不覆盖 shell 已显式 export 的 env (override=False)
   - python-dotenv 没装 → 静默 skip,不报错
4. **不引入副作用**:
   - 不 print (避免污染 uvicorn 启动日志)
   - 不抛异常

调用方式 (在所有 entrypoint 脚本顶部):
    from _env import load_env
    load_env()

entrypoint 列表:
    scripts/api_server.py
    scripts/ingest_daemon.py
    scripts/subs_scheduler.py
    fastinfo.py (CLI 入口)
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable


# 候选路径(按顺序找,找到第一个存在的就停)
def _candidate_paths() -> Iterable[Path]:
    # 1. 项目根 .env (本地 venv 开发 / 容器内 /app/.env 都覆盖)
    #    通过 __file__ 算 src/ 的父目录 = 项目根
    project_root = Path(__file__).resolve().parent.parent
    yield project_root / ".env"
    # 2. 容器内 /app/.env (Docker compose volume 挂载)
    yield Path("/app/.env")


def load_env(verbose: bool = False) -> Path | None:
    """加载 .env 到 os.environ。

    返回实际加载的路径(便于 debug),未找到返回 None。
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        if verbose:
            print("[_env] python-dotenv not installed, skip .env loading")
        return None

    for env_path in _candidate_paths():
        if env_path.exists() and env_path.is_file():
            # override=False: shell 已 export 的 env 优先
            # (允许临时 export 调试,不破坏 dev 工作流)
            load_dotenv(env_path, override=False, encoding="utf-8")
            if verbose:
                print(f"[_env] loaded {env_path}")
            return env_path

    if verbose:
        print("[_env] no .env found in candidate paths")
    return None


if __name__ == "__main__":
    # 调试入口:python -m src._env 看加载情况
    p = load_env(verbose=True)
    import os
    print(f"[_env] result path: {p}")
    print(f"[_env] MMX_API_KEY set: {bool(os.environ.get('MMX_API_KEY'))}")
    print(f"[_env] MONGO_URL: {os.environ.get('MONGO_URL', '<unset>')}")