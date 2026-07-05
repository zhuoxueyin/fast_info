"""
fastInfo · 环境身份标识集中读取器
====================================

设计目标:
    任何 Python 进程都能用一个函数拿到"我在哪一套环境"——避免排查异常时
    把 dev / docker / prod 数据混在一起看。

使用方式:
    from env_identity import get_env_identity, is_docker, env_tag

    info = get_env_identity()      # dict
    if is_docker():
        ...                        # docker 专用分支
    print(env_tag())               # 简短 tag: [DEV] / [DOCKER] / [PROD]

判定优先级(高→低):
    1. 环境变量 APP_ENV (显式声明,推荐)
    2. 启发式: /proc/1/cgroup 含 'docker' 或 /.dockerenv 存在 → "docker"
    3. 启发式: MONGO_URL 含服务名 'mongo:' 或 'redis:' → "docker"
    4. 兜底: "dev"
"""
from __future__ import annotations
import os
from typing import Literal


EnvName = Literal["dev", "docker", "prod", "staging"]


# ---------- 启发式检测(纯函数,不依赖 _env,供双方复用) ----------

def _detect_aliyun_ecs() -> bool:
    """阿里云 ECS 实例识别:
    - hostname 以 'iZ' / 'iZbp' 开头(阿里云默认命名规则)
    - /sys/class/dmi/id/product_name 含 'Aliyun'

    任意一条命中即视为 ECS(高置信度 → prod)。
    """
    try:
        hostname = (os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "")).lower()
        if hostname.startswith("iz") or hostname.startswith("izbp"):
            return True

        # DMI product_name(需要 root 权限,失败就跳过)
        for dmi_path in ("/sys/class/dmi/id/product_name", "/sys/devices/virtual/dmi/id/product_name"):
            try:
                with open(dmi_path, "r", encoding="utf-8", errors="ignore") as f:
                    if "aliyun" in f.read().lower():
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _detect_from_proc() -> str | None:
    """从 /proc 推断是否在容器里(Linux 容器内有效)。"""
    try:
        if os.path.exists("/.dockerenv"):
            return "docker"
        cgroup = "/proc/1/cgroup"
        if os.path.exists(cgroup):
            with open(cgroup, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if "docker" in content or "kubepods" in content or "containerd" in content:
                return "docker"
    except Exception:
        pass
    return None


def _detect_from_urls() -> str | None:
    """从 MONGO_URL / REDIS_URL 看是否用了容器服务名。"""
    mongo = os.environ.get("MONGO_URL", "")
    redis = os.environ.get("REDIS_URL", "")
    if mongo.startswith("mongodb://mongo:") or redis.startswith("redis://redis:"):
        return "docker"
    return None


def _detect_from_hostname() -> str | None:
    """hostname 含 'prod' / 'production' → prod。"""
    try:
        hostname = (os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "")).lower()
        if any(tok in hostname for tok in ("prod", "production")):
            return "prod"
    except Exception:
        pass
    return None


def _detect_from_mongo_db() -> str | None:
    """MONGO_DB 名含 'prod' → prod。"""
    mongo_db = os.environ.get("MONGO_DB", "").lower()
    if mongo_db and ("prod" in mongo_db or mongo_db.startswith("fastinfo_prod")):
        return "prod"
    return None


def detect_env_pure() -> EnvName:
    """纯启发式推断(不读 APP_ENV),供 _env.py 兜底逻辑复用。

    推断优先级(高→低):
        1. 阿里云 ECS → "prod"
        2. hostname 含 prod / production → "prod"
        3. MONGO_DB 含 prod → "prod"
        4. /proc 容器特征 → "docker"
        5. MONGO_URL / REDIS_URL 服务名 → "docker"
        6. 兜底 → "dev"

    与 detect_env() 的区别:本函数忽略 APP_ENV,仅看运行时特征。
    """
    if _detect_aliyun_ecs():
        return "prod"
    guess = (
        _detect_from_hostname()
        or _detect_from_mongo_db()
        or _detect_from_proc()
        or _detect_from_urls()
    )
    if guess:
        return guess  # type: ignore[return-value]
    return "dev"


def detect_env() -> EnvName:
    """推断当前环境名(供业务代码调用)。

    显式声明(APP_ENV)优先;否则启发式(detect_env_pure);最后 dev 兜底。
    """
    declared = os.environ.get("APP_ENV", "").strip().lower()
    if declared in ("dev", "docker", "prod", "staging", "test"):
        return declared  # type: ignore[return-value]
    return detect_env_pure()


def is_declared() -> bool:
    """APP_ENV 是否显式声明(不是启发式兜底产生的)。

    生产环境必须显式 export APP_ENV=prod,否则这个返回 False。
    业务代码应该在启动时检查,如果 False 且 env=prod → 打 WARN 日志。

    实现:_env.py 加载 .env 后,显式声明会设 _FASTINFO_APP_ENV_DECLARED=1。
    """
    try:
        from _env import is_app_env_declared
        return is_app_env_declared()
    except Exception:
        # 兜底:直接查 env
        return bool(os.environ.get("_FASTINFO_APP_ENV_DECLARED", "").lower() in ("1", "true", "yes"))


# ---------- 展示用辅助 ----------

# 每个环境对应的 ANSI 颜色码(shell 输出用)
# 注意:这套代码只用于 stdout 字符串拼接,不影响日志解析
_COLORS = {
    "dev":     "\033[1;36m",   # 青色 + 加粗(本机)
    "docker":  "\033[1;33m",   # 黄色 + 加粗(预发)
    "staging": "\033[1;35m",   # 紫色 + 加粗(灰度)
    "prod":    "\033[1;31m",   # 红色 + 加粗(生产)
    "test":    "\033[1;32m",   # 绿色 + 加粗(测试)
}
_RESET = "\033[0m"


def env_color(env: str | None = None) -> str:
    """返回 ANSI 颜色前缀(用于彩色打印)。"""
    if env is None:
        env = detect_env()
    return _COLORS.get(env, _COLORS["dev"])


def env_tag(env: str | None = None) -> str:
    """短 tag,适合贴日志/横幅/接口。

    例: '[DEV]' / '[DOCKER]' / '[PROD]'
    """
    if env is None:
        env = detect_env()
    return f"[{env.upper()}]"


def is_docker() -> bool:
    return detect_env() == "docker"


def is_dev() -> bool:
    return detect_env() == "dev"


# ---------- 完整身份快照 ----------

def get_env_identity() -> dict:
    """返回当前环境身份完整快照,给 /healthz /whoami 用。

    Returns:
        {
            "env": "dev" | "docker" | ...,
            "tag": "[DEV]" | ...,
            "mongo_url": "...",
            "mongo_db": "...",
            "redis_url": "...",
            "hostname": "...",
            "pid": 12345,
            "data_dir": "...",
            "declared": True/False,   ← APP_ENV 是否显式声明
        }
    """
    env = detect_env()
    return {
        "env": env,
        "tag": env_tag(env),
        "mongo_url": os.environ.get("MONGO_URL", "<unset>"),
        "mongo_db":  os.environ.get("MONGO_DB",  "<unset>"),
        "redis_url": os.environ.get("REDIS_URL", "<unset>"),
        "site_base": os.environ.get("FASTINFO_SITE_BASE", "<unset>"),
        "hostname":  os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "?"),
        "pid":       os.getpid(),
        "data_dir":  os.environ.get("DATA_DIR", "./data"),
        "declared":  is_declared(),
    }


def warn_if_undeclared_prod() -> None:
    """启动时调用:如果检测到 prod 但 APP_ENV 没显式声明,打 WARN 日志。

    业务入口(api_server / ingest_daemon / subs_scheduler)应该在启动第一行调用。
    生产环境如果出现 WARN,说明 ECS 部署忘了 export APP_ENV=prod,需立即修复。
    """
    env = detect_env()
    if env == "prod" and not is_declared():
        import logging
        logger = logging.getLogger("fastinfo.env")
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
            logger.addHandler(h)
        logger.warning(
            "[ENV-IDENTITY] APP_ENV=prod is INFERRED, not explicitly declared!\n"
            "  -> Set APP_ENV=prod explicitly in ECS systemd unit / docker-compose env_file / shell\n"
            "  -> Heuristic detection depends on hostname/DMI; custom images may fail silently"
        )


# ---------- 启动横幅 ----------

def startup_banner(service: str) -> str:
    """生成启动横幅,带 ANSI 颜色 + 环境 tag。

    适合贴在 api_server / ingest_daemon / subs_scheduler 启动第一行。
    """
    info = get_env_identity()
    color = env_color(info["env"])
    return (
        f"{color}┌─ {service} ─ {info['tag']} ─{_RESET}\n"
        f"{color}│{_RESET}  MONGO={info['mongo_url']}  DB={info['mongo_db']}\n"
        f"{color}│{_RESET}  REDIS={info['redis_url']}  PID={info['pid']}\n"
        f"{color}└─{_RESET}"
    )


if __name__ == "__main__":
    # 调试入口:python -m src.env_identity
    import json
    print(startup_banner("env_identity demo"))
    print()
    print(json.dumps(get_env_identity(), indent=2, ensure_ascii=False))