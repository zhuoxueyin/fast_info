#!/usr/bin/env bash
# fastInfo · env 模板与实例文件同步检查
# ========================================
# 用法:
#   bash scripts/check-env-sync.sh              # 检查全部 env 文件
#   bash scripts/check-env-sync.sh prod         # 只检查生产 env.prod.local
#
# 规则:
#   - .example 模板文件进 git,每次 git pull 会更新
#   - .local / .env 实例文件不进 git,不会被 git pull 更新
#   - 当模板新增 key 时,实例文件必须手动同步,否则部署可能使用默认值或失败
# ========================================

set -uo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { printf "${GREEN}==>${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}!!>${NC} %s\n" "$1"; }
err()  { printf "${RED}xx>${NC} %s\n" "$1"; }

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

MODE="${1:-all}"
EXIT_CODE=0

# 提取文件中的 key 名(只取 KEY= 形式,忽略注释和空行)
extract_keys() {
  grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$1" 2>/dev/null | sed 's/=.*//' | sort -u
}

# 检查一组模板/实例
check_pair() {
  local template="$1"
  local instance="$2"
  local label="$3"

  if [ ! -f "$template" ]; then
    err "模板文件不存在: $template"
    return 1
  fi

  if [ ! -f "$instance" ]; then
    err "实例文件不存在: $instance"
    warn "   请执行: cp $template $instance"
    warn "   然后编辑 $instance 填入环境专用值"
    return 1
  fi

  local missing
  missing=$(comm -23 <(extract_keys "$template") <(extract_keys "$instance"))

  log "检查 $label"
  log "   模板: $template"
  log "   实例: $instance"

  if [ -z "$missing" ]; then
    log "   ✅ 实例包含模板全部 key"
  else
    warn "   !! 实例缺少以下模板中的 key:"
    echo "$missing" | sed 's/^/        /'
    warn "   请把缺失的 key 从模板复制到实例,并填入合适的值"
    EXIT_CODE=1
  fi
}

log "开始 env 文件同步检查 · mode=$MODE"
echo ""

if [ "$MODE" = "all" ] || [ "$MODE" = "dotenv" ]; then
  check_pair ".env.example" ".env" "共享配置(.env)"
  echo ""
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "docker" ] || [ "$MODE" = "staging" ]; then
  check_pair "docker/env.docker.local.example" "docker/env.docker.local" "Docker 预发配置(env.docker.local)"
  echo ""
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "prod" ]; then
  check_pair "docker/env.prod.local.example" "docker/env.prod.local" "生产配置(env.prod.local)"
  echo ""
fi

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
  log "✅ 全部 env 文件同步检查通过"
else
  err "❌ 部分 env 文件不同步,请按上方提示修复后再部署"
fi

exit "$EXIT_CODE"
