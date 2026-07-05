#!/bin/sh
# fastInfo · API 容器启动入口
# =====================================
# 触发时机:docker-compose 启动 api / ingest_daemon / subs_scheduler 时
#
# 职责:
#   1. 首次启动时执行 init_admin_collections.py 建索引
#   2. (可选)初始化 admin 账号,受 FASTINFO_INIT_ADMIN 控制
#   3. **生产环境启动时检测 APP_ENV=prod 是否被显式声明**
#      如果是 prod 但未声明,打 WARN(后续业务代码也可以用 is_declared() 检查)
#   4. exec 原始 CMD(uvicorn / ingest_daemon / subs_scheduler)
# =====================================
set -eu

# 1. Bootstrap(首次启动建索引 + admin)
if [ "${FASTINFO_BOOTSTRAP:-1}" = "1" ]; then
  python scripts/init_admin_collections.py

  if [ "${FASTINFO_INIT_ADMIN:-1}" = "1" ]; then
    ADMIN_USERNAME="${FASTINFO_ADMIN_USERNAME:-admin}"
    ADMIN_PASSWORD="${FASTINFO_ADMIN_PASSWORD:-admin@2026}"
    python scripts/init_admin.py --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  fi
fi

# 2. 环境身份检查(不阻断,只打 WARN)
#    生产环境必须显式 APP_ENV=prod;若被兜底推断,日志里能看到
if [ "${APP_ENV:-}" = "prod" ]; then
  python - <<'PY'
import os, sys
try:
    sys.path.insert(0, '/app/src')
    from env_identity import is_declared, get_env_identity, warn_if_undeclared_prod
    info = get_env_identity()
    # 用 ASCII banner 在容器日志里显眼
    if info.get('env') == 'prod':
        if info.get('declared'):
            print(f"[ENV-IDENTITY] OK · APP_ENV=prod · declared=True · mongo_db={info.get('mongo_db')}")
        else:
            warn_if_undeclared_prod()
    else:
        print(f"[ENV-IDENTITY] APP_ENV=prod requested, but detected env={info.get('env')} mongo_db={info.get('mongo_db')}")
except Exception as e:
    print(f"[ENV-IDENTITY] check failed (non-fatal): {e}", file=sys.stderr)
PY
fi

# 3. exec 原始 CMD
exec "$@"