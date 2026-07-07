#!/usr/bin/env bash
#
# 构建辅助函数：根据当前系统内存自动选择常规构建或低内存构建策略。
# 被 deploy-prod.sh / deploy-staging.sh source 使用，不直接执行。
#

# 检测是否为低内存机器。
# 参数 $1: 阈值(MB)，默认 2048 (2 GB)。
# 返回 0 表示低内存，1 表示内存充足。
detect_low_memory() {
  local threshold_mb="${1:-2048}"
  local total_mem_kb total_mem_mb

  total_mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
  total_mem_mb=$((total_mem_kb / 1024))

  if [ "${total_mem_mb}" -le "${threshold_mb}" ]; then
    return 0
  else
    return 1
  fi
}

# 获取当前系统总内存(MB)。
get_total_memory_mb() {
  awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0
}

# 内存感知构建。
# 在内存 <= 阈值时自动串行、限内存构建；否则走默认 docker compose build。
# 参数：
#   $1: 阈值(MB)，可选，默认 2048
#   其余参数：要构建的 service 列表；为空时构建全部（等价于 docker compose build）
build_with_memory_awareness() {
  local threshold_mb="${1:-2048}"
  shift || true
  local services=("$@")
  local total_mem_mb

  total_mem_mb=$(get_total_memory_mb)

  if detect_low_memory "${threshold_mb}"; then
    echo "LOW MEMORY DETECTED: ${total_mem_mb} MB <= ${threshold_mb} MB"
    echo "Switching to low-memory build strategy (serial + memory-limited)."

    if [ "${#services[@]}" -eq 0 ]; then
      # 未指定 service 时，只构建需要本地构建的 service。
      # mongo/redis 使用官方镜像，api/web/ingest_daemon/subs_scheduler 需要构建。
      services=(api web ingest_daemon subs_scheduler)
    fi

    local script_dir project_root
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    project_root="$(cd "${script_dir}/.." && pwd)"

    "${project_root}/scripts/build-low-memory.sh" "${services[@]}"
  else
    echo "Memory sufficient: ${total_mem_mb} MB"
    if [ "${#services[@]}" -eq 0 ]; then
      docker compose build
    else
      docker compose build "${services[@]}"
    fi
  fi
}
