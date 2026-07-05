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
5. **APP_ENV 自动兜底**:
   加载完 .env 后,如果 APP_ENV 仍没值,根据 MONGO_URL 启发式猜一个,
   避免任何代码分支看到 APP_ENV=<unset>。
   需要"环境身份"具体函数见 env_identity.py。

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
import os
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

    # 标记:只要 APP_ENV 有值,无论 shell 来还是 .env 来,都是"显式声明"
    pre_existing = os.environ.get("APP_ENV")

    for env_path in _candidate_paths():
        if env_path.exists() and env_path.is_file():
            # override=False: shell 已 export 的 env 优先
            # (允许临时 export 调试,不破坏 dev 工作流)
            load_dotenv(env_path, override=False, encoding="utf-8")
            if verbose:
                print(f"[_env] loaded {env_path}")
            # 标记 declared(只要 APP_ENV 已被设置)
            if os.environ.get("APP_ENV"):
                os.environ["_FASTINFO_APP_ENV_DECLARED"] = "1"
            _fallback_app_env()  # 加载完再兜底(只在 APP_ENV 还没值时才生效)
            return env_path

    if verbose:
        print("[_env] no .env found in candidate paths")
    # 即使没 .env 文件,shell 已 export 也算 declared
    if pre_existing:
        os.environ["_FASTINFO_APP_ENV_DECLARED"] = "1"
    _fallback_app_env()  # 即使没 .env,也兜底一次
    return None


def _fallback_app_env() -> None:
    """APP_ENV 兜底:加载完 .env 后,如果还没声明,调 env_identity.detect_env_pure() 启发式推断。

    ⚠️ 显式 export APP_ENV=... 永远优先(shell env 在 load_dotenv 前就有)。
       加载完 .env 后,如果 APP_ENV 已被设置(无论是 shell 还是 .env),
       都标记 _FASTINFO_APP_ENV_DECLARED=1,供业务代码判断"我是不是兜底来的"。

    ⚠️ ECS 部署**强烈建议**显式声明 APP_ENV=prod —— 启发式只能识别
    最常见的"阿里云 ECS + systemd 容器"组合,自定义镜像/裸 systemd 进程
    会落到 docker / dev 兜底。

    启发式具体逻辑在 env_identity.detect_env_pure()(单一真实源,避免两边逻辑漂移)。
    """
    if os.environ.get("APP_ENV"):
        # 已经被显式设置(shell 或 .env),标记一下
        os.environ["_FASTINFO_APP_ENV_DECLARED"] = "1"
        return

    # 调 env_identity 的纯启发式(避免逻辑两套)
    from env_identity import detect_env_pure
    os.environ["APP_ENV"] = detect_env_pure()


def is_app_env_declared() -> bool:
    """APP_ENV 是否显式声明(不是 _fallback_app_env 兜底产生的)。

    业务代码应该用这个判断:如果 APP_ENV 是兜底来的,生产环境必须显式声明,
    否则应该打 WARN 日志提示。
    """
    return bool(os.environ.get("_FASTINFO_APP_ENV_DECLARED", "").lower() in ("1", "true", "yes"))


if __name__ == "__main__":
    # 调试入口:python -m src._env 看加载情况
    p = load_env(verbose=True)
    import os
    print(f"[_env] result path: {p}")
    print(f"[_env] MMX_API_KEY set: {bool(os.environ.get('MMX_API_KEY'))}")
    print(f"[_env] MONGO_URL: {os.environ.get('MONGO_URL', '<unset>')}")