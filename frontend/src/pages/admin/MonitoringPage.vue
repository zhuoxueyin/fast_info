<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">实时监控</h1>
      <AdminTabs class="ml-auto" />
    </div>

    <!-- 顶部状态条 -->
    <div
      class="rounded-xl px-5 py-3 mb-6 flex items-center gap-3 border"
      :class="overallBg"
    >
      <span class="text-2xl">{{ overallEmoji }}</span>
      <div class="flex-1">
        <div class="font-semibold">{{ overallText }}</div>
        <div class="text-xs opacity-80">
          上次检查: {{ data?.checked_at || '—' }} · 5 秒自动刷新
          <span v-if="autoReapedCount > 0" class="ml-2 text-emerald-600">
            · 本轮自动清理 {{ autoReapedCount }} 个僵尸
          </span>
        </div>
      </div>
      <n-button size="small" @click="reload">立即刷新</n-button>
      <n-button size="small" type="primary" :loading="restarting" @click="restartDaemon">
        重启 ingest_daemon
      </n-button>
    </div>

    <!-- 加载占位 -->
    <div v-if="!data" class="text-center py-20 text-slate-400">
      加载中…
    </div>

    <template v-else>
      <!-- ===== 服务组(影响当前使用)===== -->
      <section class="mb-6">
        <div class="flex items-baseline gap-2 mb-3">
          <h2 class="text-base font-semibold text-slate-800">🛰️ 核心服务</h2>
          <span class="text-xs text-slate-500">直接影响当前使用 · 5 项</span>
        </div>
        <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          <DependencyCard
            v-for="(comp, key) in data.groups?.services || {}"
            :key="key"
            :name="String(key)"
            :comp="comp"
            @enable-source="onEnableSource"
          >
            <template #extras="{ comp: c }">
              <!-- daemon 卡片展开 ingest / scheduler 详情 -->
              <template v-if="c.extra?.ingest">
                <div class="flex justify-between">
                  <span>ingest_daemon</span>
                  <span :class="c.extra.ingest.status === 'ok' ? 'text-emerald-600' : 'text-rose-600'">
                    {{ c.extra.ingest.status }}
                  </span>
                </div>
                <div class="flex justify-between">
                  <span>subs_scheduler</span>
                  <span :class="c.extra.subs_scheduler.status === 'ok' ? 'text-emerald-600' : 'text-rose-600'">
                    {{ c.extra.subs_scheduler.status }}
                  </span>
                </div>
              </template>
            </template>
          </DependencyCard>
        </div>
      </section>

      <!-- ===== 任务组(运行中 + 僵尸自动清理)===== -->
      <section class="mb-6">
        <div class="flex items-baseline gap-2 mb-3">
          <h2 class="text-base font-semibold text-slate-800">⚙️ 任务运行</h2>
          <span class="text-xs text-slate-500">僵尸任务超时自动清理 · 无需手动</span>
        </div>
        <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <DependencyCard
            v-for="(comp, key) in data.groups?.tasks || {}"
            :key="key"
            :name="String(key)"
            :comp="comp"
            @enable-source="onEnableSource"
          >
            <template #extras="{ comp: c }">
              <div v-if="c.extra?.running_stuck > 0" class="text-rose-600">
                ⚠ {{ c.extra.running_stuck }} 个僵尸卡住
              </div>
              <div v-if="c.extra?.reaped_stale > 0" class="text-emerald-600">
                ✓ 本轮已自动清理 {{ c.extra.reaped_stale }} 个
              </div>
              <div v-if="c.extra?.fail_rate_24h != null" class="text-slate-500">
                24h 失败率 {{ Math.round(c.extra.fail_rate_24h * 100) }}%
              </div>
            </template>
          </DependencyCard>
        </div>

        <!-- 当前运行中的任务(展开) -->
        <div
          v-if="data.groups?.tasks?.tasks?.extra?.running_now?.length"
          class="mt-3 bg-white rounded-xl border border-slate-200 p-4"
        >
          <h3 class="text-sm font-semibold mb-2 text-slate-700">
            当前运行中 ({{ data.groups.tasks.tasks.extra.running_now.length }})
          </h3>
          <div class="space-y-1 text-sm">
            <div
              v-for="t in data.groups.tasks.tasks.extra.running_now"
              :key="t.run_id"
              class="flex items-center gap-2 font-mono text-xs border-b border-slate-100 pb-1"
            >
              <span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">{{ t.trigger }}</span>
              <span class="text-slate-700">{{ t.run_id.slice(0, 8) }}…</span>
              <span class="text-slate-400">{{ formatAge(t.age_sec) }}前开始</span>
              <span
                v-if="(t.age_sec || 0) > (data.groups.tasks.tasks.extra.stale_threshold_sec || 1800)"
                class="text-rose-600 font-medium"
              >
                · 即将被 reap
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- ===== 资源组(可折叠)===== -->
      <section class="mb-6">
        <div class="flex items-center gap-2 mb-3">
          <n-button text size="small" @click="resourcesCollapsed = !resourcesCollapsed">
            {{ resourcesCollapsed ? '▶' : '▼' }} 其他资源 (3 项)
          </n-button>
        </div>
        <div v-if="!resourcesCollapsed" class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <DependencyCard
            v-for="(comp, key) in data.groups?.resources || {}"
            :key="key"
            :name="String(key)"
            :comp="comp"
            @enable-source="onEnableSource"
          >
            <template #extras="{ comp: c }">
              <!-- sources 卡片展开 disabled 详情 -->
              <template v-if="c.extra?.disabled_detail && c.extra.disabled_detail.length">
                <div class="text-amber-600">
                  {{ c.extra.disabled }} 个禁用 ·
                  <span class="text-xs">点击"重启用"恢复</span>
                </div>
              </template>
              <!-- llm 卡片展开熔断信息 -->
              <template v-if="c.extra?.providers">
                <div
                  v-for="p in c.extra.providers.filter((x: any) => x.circuit_open)"
                  :key="p.name"
                  class="text-rose-600"
                >
                  熔断: {{ p.name }}
                </div>
              </template>
            </template>
          </DependencyCard>
        </div>
      </section>

      <!-- 已禁用源(便于在监控页直接重启用) -->
      <div
        v-if="disabledSources.length"
        class="mt-3 bg-white rounded-xl border border-slate-200 p-4"
      >
        <h3 class="text-sm font-semibold mb-2 text-slate-700">
          已禁用的源 ({{ disabledSources.length }})
        </h3>
        <div class="space-y-1 text-sm">
          <div
            v-for="s in disabledSources"
            :key="s.source_id"
            class="flex items-center gap-2 border-b border-slate-100 pb-1"
          >
            <n-tag type="error" size="small">{{ s.source_id }}</n-tag>
            <span class="text-slate-700 text-xs">{{ s.display_name }}</span>
            <span class="text-slate-400 text-xs truncate flex-1" :title="s.last_error">
              consecutive_fails={{ s.consecutive_fails }}
              <span v-if="s.last_error_code"> · {{ s.last_error_code }}</span>
            </span>
            <n-button size="tiny" type="primary" @click="enableSource(s.source_id)">
              重启用
            </n-button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { api } from '@/lib/api'
import AdminTabs from '@/components/AdminTabs.vue'
import DependencyCard from '@/components/DependencyCard.vue'

const msg = useMessage()
const data = ref<any>(null)
const restarting = ref(false)
const resourcesCollapsed = ref(true)  // 默认折叠(资源组不常用)
let timer: number | undefined

const overallBg = computed(() => {
  switch (data.value?.overall) {
    case 'ok':   return 'bg-emerald-50 border-emerald-200 text-emerald-800'
    case 'warn': return 'bg-amber-50 border-amber-200 text-amber-800'
    case 'fail': return 'bg-red-50 border-red-200 text-red-800'
    default:     return 'bg-slate-50 border-slate-200 text-slate-700'
  }
})
const overallEmoji = computed(() => {
  switch (data.value?.overall) {
    case 'ok':   return '✓'
    case 'warn': return '!'
    case 'fail': return '×'
    default:     return '·'
  }
})
const overallText = computed(() => {
  switch (data.value?.overall) {
    case 'ok':   return '全部核心依赖正常'
    case 'warn': return '部分依赖告警'
    case 'fail': return '检测到严重问题'
    default:     return '状态未知'
  }
})

// 本轮自动清理的僵尸数(check_tasks 自动 reap)
const autoReapedCount = computed(() => {
  return data.value?.groups?.tasks?.tasks?.extra?.reaped_stale || 0
})

// 已禁用源列表(从 resources.sources.extra.disabled_detail 拿)
const disabledSources = computed(() => {
  return data.value?.groups?.resources?.sources?.extra?.disabled_detail || []
})

async function reload() {
  try {
    data.value = await api('/admin/monitoring')
  } catch (e: any) {
    msg.error(e?.data?.detail || '监控拉取失败')
  }
}

async function restartDaemon() {
  restarting.value = true
  try {
    const r = await api('/admin/source/restart-daemon', { method: 'POST' })
    if (r.restarted) {
      msg.success(`已下发重启命令`)
    } else {
      msg.warning(r.reason || '重启未生效')
    }
    setTimeout(reload, 1500)
  } catch (e: any) {
    msg.error(e?.data?.detail || '重启失败')
  } finally {
    restarting.value = false
  }
}

async function enableSource(sourceId: string) {
  try {
    await api(`/admin/source/${encodeURIComponent(sourceId)}/enable`, { method: 'POST' })
    msg.success(`已重启用 ${sourceId}`)
    // 广播事件,SourcesPage 监听后自动刷新
    window.dispatchEvent(new CustomEvent('fastinfo:sources-changed', { detail: { source_id: sourceId, action: 'enable' } }))
    reload()
  } catch (e: any) {
    msg.error(e?.data?.detail || '重启用失败')
  }
}

function onEnableSource(sourceId: string) {
  enableSource(sourceId)
}

function formatAge(sec: number | null | undefined): string {
  if (sec == null) return '-'
  if (sec < 60) return `${Math.round(sec)}s`
  if (sec < 3600) return `${Math.round(sec / 60)}min`
  return `${(sec / 3600).toFixed(1)}h`
}

onMounted(() => {
  reload()
  timer = window.setInterval(reload, 5000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>