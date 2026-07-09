<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📡 爬取任务监控</h1>
      <n-button @click="loadAll">🔄 刷新</n-button>
      <AdminTabs class="ml-auto" />
    </div>

    <!-- Day 10.5 · 抓取调度策略 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <h2 class="text-lg font-semibold">⏰ 抓取调度策略</h2>
          <p class="text-xs text-slate-500 mt-1">
            按每源自己的 <code class="px-1 bg-slate-100 rounded">cron_interval_seconds</code> 自动调度,daemon 每 60s 检查到期源。
            修改策略请到 <b>数据源管理</b> 页面。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <n-button
            type="warning"
            :loading="triggeringAll"
            :disabled="!scheduleOverview || scheduleOverview.due_now === 0"
            @click="triggerAllDue"
          >
            ▶ 立即抓 {{ scheduleOverview?.due_now ?? 0 }} 个到期源
          </n-button>
          <n-button quaternary @click="showScheduleDetail = !showScheduleDetail">
            {{ showScheduleDetail ? '收起详情' : '查看详情' }}
          </n-button>
        </div>
      </div>

      <div v-if="scheduleOverview" class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="bg-slate-50 rounded p-3">
          <div class="text-xs text-slate-500">总源数</div>
          <div class="text-xl font-bold text-slate-900">{{ scheduleOverview.total_sources }}</div>
        </div>
        <div class="bg-emerald-50 rounded p-3">
          <div class="text-xs text-emerald-700">定时调度</div>
          <div class="text-xl font-bold text-emerald-700">{{ scheduleOverview.active_scheduled }}</div>
        </div>
        <div class="bg-amber-50 rounded p-3">
          <div class="text-xs text-amber-700">仅手动</div>
          <div class="text-xl font-bold text-amber-700">{{ scheduleOverview.manual_only }}</div>
        </div>
        <div
          :class="['rounded p-3',
                   scheduleOverview.due_now > 0 ? 'bg-rose-50' : 'bg-slate-50']"
        >
          <div class="text-xs" :class="scheduleOverview.due_now > 0 ? 'text-rose-700' : 'text-slate-500'">
            当前到期
          </div>
          <div class="text-xl font-bold" :class="scheduleOverview.due_now > 0 ? 'text-rose-700' : 'text-slate-400'">
            {{ scheduleOverview.due_now }}
          </div>
          <div class="text-[10px] text-slate-400">daemon 下个 tick 也会自动跑</div>
        </div>
      </div>

      <!-- 调度详情表 -->
      <div v-if="showScheduleDetail && scheduleOverview" class="mt-4">
        <n-data-table
          :columns="scheduleCols"
          :data="scheduleOverview.items"
          :pagination="{ pageSize: 10 }"
          size="small"
          :bordered="false"
          :row-key="(r: any) => r.source_id"
        />
      </div>
    </section>

    <!-- 手动触发 ingest -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold">🚀 手动触发 ingest</h2>
        <n-button type="primary" :loading="ingesting" @click="triggerIngest">运行</n-button>
      </div>
      <p class="text-sm text-slate-500 mb-3">每个源最多抓 {{ ingestLimit }} 条;会真调 LLM 生成摘要(后台异步,几秒到几十秒)。</p>
      <n-input-number v-model:value="ingestLimit" :min="1" :max="30" class="!w-32 mb-3" :disabled="ingesting" />

      <!-- 实时进度 -->
      <div v-if="ingestResult" class="mt-3 space-y-2">
        <div class="flex items-center gap-2 text-sm">
          <span class="px-2 py-0.5 rounded text-xs font-mono" :class="statusBadgeClass">
            {{ statusLabel }}
          </span>
          <span class="text-slate-500 font-mono text-xs">run_id: {{ ingestResult.run_id }}</span>
          <span class="text-slate-400 text-xs" v-if="ingestResult.trigger">· {{ ingestResult.trigger }}</span>
          <span class="text-slate-400 text-xs" v-if="ingestResult.operator">· 操作人 {{ ingestResult.operator }}</span>
          <n-button v-if="['done', 'partial', 'failed', 'stale'].includes(ingestResult.status)"
            size="tiny" type="info" text @click="openTrace(ingestResult.run_id)">
            📊 查看调用树
          </n-button>
        </div>

        <div class="grid grid-cols-4 gap-3">
          <div class="bg-slate-50 rounded p-3">
            <div class="text-xs text-slate-500">已抓</div>
            <div class="text-xl font-bold text-slate-900">{{ ingestResult.items_fetched ?? '—' }}</div>
          </div>
          <div class="bg-emerald-50 rounded p-3">
            <div class="text-xs text-emerald-700">摘要成功</div>
            <div class="text-xl font-bold text-emerald-700">{{ ingestResult.items_summarized ?? '—' }}</div>
          </div>
          <div class="bg-rose-50 rounded p-3">
            <div class="text-xs text-rose-700">摘要失败</div>
            <div class="text-xl font-bold text-rose-700">{{ ingestResult.items_failed ?? '—' }}</div>
          </div>
          <div class="bg-amber-50 rounded p-3">
            <div class="text-xs text-amber-700">新增</div>
            <div class="text-xl font-bold text-amber-700">{{ ingestResult.items_new ?? '—' }}</div>
          </div>
        </div>

        <div v-if="ingestResult.duration_sec != null" class="text-xs text-slate-500">
          耗时 {{ ingestResult.duration_sec }} 秒
        </div>

        <n-alert v-if="ingestResult.warning" type="warning" :title="ingestResult.warning" :show-icon="true" />
        <n-alert v-else-if="ingestResult.status === 'failed'" type="error" title="任务失败" :show-icon="true" />
        <n-alert v-else-if="ingestResult.status === 'partial'" type="warning" title="部分成功" :show-icon="true" />
        <n-alert v-else-if="ingestResult.status === 'done' && ingestResult.items_summarized > 0" type="success" title="完成" :show-icon="true" />
        <n-alert v-else-if="ingestResult.status === 'done'" type="info" title="完成(无新内容)" :show-icon="true" />
      </div>
    </section>

    <!-- 任务运行时间线 + LLM模型组并排 -->
    <div class="grid lg:grid-cols-[1fr_280px] gap-4">
      <section class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-base font-semibold mb-4">🕐 任务运行(最近 20)</h2>
        <n-data-table
          v-if="runs.length"
          :columns="cols"
          :data="runs"
          :pagination="false"
          :bordered="false"
          :row-key="(r: any) => r.run_id"
          size="small"
        />
        <n-empty v-else description="暂无抓取事件" size="small" />
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-4">
        <h2 class="text-sm font-semibold mb-3">🤖 LLM 模型组</h2>
        <div v-if="llmGroups" class="space-y-2">
          <div v-for="(providers, gname) in llmGroups" :key="gname" class="border border-slate-100 rounded p-2">
            <div class="text-xs font-medium text-slate-700 mb-1">{{ gname }}</div>
            <div class="space-y-0.5">
              <div v-for="(p, pid) in providers" :key="pid" class="flex justify-between text-xs text-slate-500">
                <span>#{{ p.priority }} {{ pid }}</span>
                <span class="font-mono text-slate-400 text-[10px]">{{ p.model }}</span>
              </div>
            </div>
          </div>
        </div>
        <n-empty v-else size="small" />
      </section>
    </div>

    <!-- 调用树跟踪抽屉 -->
    <n-drawer v-model:show="traceVisible" :width="720" placement="right">
      <n-drawer-content :title="`调用树跟踪 · ${traceRunId.slice(0, 8)}…`" closable>
        <div v-if="traceLoading" class="py-8 text-center text-slate-400">加载中…</div>
        <div v-else-if="traceData" class="space-y-4">
          <!-- 顶层任务摘要 -->
          <div class="bg-slate-50 rounded-lg p-4">
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2 py-0.5 rounded text-xs font-mono" :class="traceStatusClass(traceData.task_run.status)">
                {{ traceStatusLabel(traceData.task_run.status) }}
              </span>
              <span class="text-xs text-slate-500 font-mono">{{ traceData.task_run.run_id }}</span>
            </div>
            <div class="grid grid-cols-4 gap-2 text-center">
              <div>
                <div class="text-xs text-slate-500">已抓</div>
                <div class="text-lg font-bold">{{ traceData.task_run.items_fetched ?? 0 }}</div>
              </div>
              <div>
                <div class="text-xs text-emerald-600">摘要成功</div>
                <div class="text-lg font-bold text-emerald-600">{{ traceData.task_run.items_summarized ?? 0 }}</div>
              </div>
              <div>
                <div class="text-xs text-rose-600">摘要失败</div>
                <div class="text-lg font-bold text-rose-600">{{ traceData.task_run.items_failed ?? 0 }}</div>
              </div>
              <div>
                <div class="text-xs text-slate-500">源总数</div>
                <div class="text-lg font-bold">{{ traceData.summary.total_sources }}</div>
              </div>
            </div>
            <div class="flex gap-3 mt-2 text-xs flex-wrap">
              <span class="text-emerald-600">✅ 成功 {{ traceData.summary.ok_sources }}</span>
              <span class="text-amber-600">⚠️ 部分 {{ traceData.summary.partial_sources || 0 }}</span>
              <span class="text-rose-600">❌ 失败 {{ traceData.summary.fail_sources }}</span>
              <span class="text-slate-500">⏸ 禁用 {{ traceData.summary.disabled_sources }}</span>
              <span class="text-sky-600">🕐 未到 {{ traceData.summary.not_due_sources || 0 }}</span>
              <span class="text-slate-500">⏱ 总耗时 {{ (traceData.summary.total_duration_ms / 1000).toFixed(1) }}s</span>
            </div>
          </div>

          <!-- 调用树:每源一条 -->
          <div>
            <h3 class="text-sm font-semibold mb-2 text-slate-700">🌲 源执行调用树</h3>
            <div class="space-y-1">
              <div
                v-for="(sr, idx) in traceData.source_runs"
                :key="sr.run_id"
                class="flex items-start gap-2 p-2 rounded border-l-2 bg-white"
                :class="sourceRunBorderClass(sr.status)"
              >
                <span class="text-slate-400 font-mono text-xs mt-0.5 w-6">{{ idx + 1 }}.</span>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-medium text-sm text-slate-800">{{ sr.source_id }}</span>
                    <span class="px-1.5 py-0.5 rounded text-[10px] font-mono" :class="sourceRunBadgeClass(sr.status)">
                      {{ SR_LABEL[sr.status] || sr.status }}
                    </span>
                    <span v-if="sr.duration_ms > 0" class="text-xs text-slate-400">{{ sr.duration_ms }}ms</span>
                    <span v-if="sr.fetched_count > 0" class="text-xs text-slate-500">抓 {{ sr.fetched_count }}</span>
                    <span v-if="sr.new_count > 0" class="text-xs text-emerald-600">新 {{ sr.new_count }}</span>
                    <span v-if="sr.summarized_count > 0" class="text-xs text-emerald-600">摘 {{ sr.summarized_count }}</span>
                    <span v-if="sr.failed_count > 0" class="text-xs text-rose-600">败 {{ sr.failed_count }}</span>
                  </div>
                  <div v-if="sr.error_msg" class="text-xs text-rose-600 mt-1 font-mono break-all">
                    {{ sr.error_code }}: {{ sr.error_msg }}
                  </div>
                  <div v-if="sr.started_at || sr.ended_at" class="text-[10px] text-slate-400 mt-0.5">{{ formatTime(sr.started_at) }} → {{ formatTime(sr.ended_at) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <n-empty v-else description="无跟踪数据" />
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, h } from 'vue'
import {
  NButton, NEmpty, NDataTable, NTag, NInputNumber, NAlert,
  NDrawer, NDrawerContent, useMessage,
  type DataTableColumns,
} from 'naive-ui'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import { api } from '@/lib/api'
import { getScheduleOverview, runSourceNow, type ScheduleRow } from '@/lib/api'
import AdminTabs from '@/components/AdminTabs.vue'

dayjs.extend(utc)
dayjs.extend(timezone)

const msg = useMessage()
const llmGroups = ref<Record<string, Record<string, any>> | null>(null)
const runs = ref<any[]>([])

// Day 10.5 · 调度
const scheduleOverview = ref<Awaited<ReturnType<typeof getScheduleOverview>> | null>(null)
const showScheduleDetail = ref(false)
const triggeringAll = ref(false)

// 任务级状态语义(从执行中/成功/失败真实视角)
const STATUS_TYPE: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  running: 'warning',   // 执行中
  done: 'success',      // 成功
  partial: 'warning',   // 部分成功
  failed: 'error',      // 失败
  stale: 'error',       // 僵尸(超时未结束,等同失败)
}
const STATUS_LABEL: Record<string, string> = {
  running: '执行中',
  done: '成功',
  partial: '部分成功',
  failed: '失败',
  stale: '僵尸',
}

// ===== 手动触发 ingest =====
const ingesting = ref(false)
const ingestResult = ref<any>(null)
const ingestLimit = ref(8)
let pollTimer: number | null = null

const statusLabel = computed(() => {
  const s = ingestResult.value?.status
  return STATUS_LABEL[s] || s || '未知'
})

const statusBadgeClass = computed(() => {
  const s = ingestResult.value?.status
  if (s === 'running') return 'bg-amber-100 text-amber-700 animate-pulse'
  if (s === 'done') return 'bg-emerald-100 text-emerald-700'
  if (s === 'partial') return 'bg-amber-100 text-amber-700'
  if (s === 'failed' || s === 'stale') return 'bg-rose-100 text-rose-700'
  return 'bg-slate-100 text-slate-700'
})

async function triggerIngest() {
  ingesting.value = true
  ingestResult.value = null
  stopPolling()
  try {
    const r = await api<{
      run_id: string; status: string; trigger?: string; operator?: string; limit?: number
    }>(`/admin/ingest/run`, {
      method: 'POST',
      query: { limit: ingestLimit.value },
      timeout: 10000,
    })
    ingestResult.value = {
      run_id: r.run_id, status: r.status, trigger: r.trigger,
      operator: r.operator, limit: r.limit, started_at: new Date().toISOString(),
    }
    msg.info(`已触发,run_id=${r.run_id.slice(0, 8)}…,开始轮询…`, { duration: 2000 })
    startPolling(r.run_id)
  } catch (e: any) {
    ingesting.value = false
    msg.error(e?.data?.detail || '触发失败')
  }
}

function startPolling(run_id: string) {
  const started_ms = Date.now()
  const tick = async () => {
    try {
      const s = await api<{
        run_id: string; status: string; started_at?: string; finished_at?: string | null;
        items_fetched?: number; items_summarized?: number; items_failed?: number; warning?: string;
        per_source?: Record<string, { fetched: number; summarized: number; errors: number; latency_ms?: number }>;
      }>(`/admin/ingest/task/${run_id}`, { timeout: 5000 })

      const duration_sec = s.finished_at
        ? Math.round((new Date(s.finished_at).getTime() - new Date(s.started_at!).getTime()) / 1000)
        : Math.round((Date.now() - started_ms) / 1000)

      ingestResult.value = { ...ingestResult.value, ...s, duration_sec }

      if (s.status === 'done' || s.status === 'partial' || s.status === 'failed') {
        stopPolling()
        ingesting.value = false
        if (s.status === 'failed') {
          msg.error(`任务失败: ${s.warning || '未知原因'}`)
        } else if (s.status === 'partial') {
          msg.warning(`部分成功: 成功 ${s.items_summarized ?? 0} / 失败 ${s.items_failed ?? 0}`)
        } else if ((s.items_summarized ?? 0) > 0) {
          msg.success(`完成: 新增 ${s.items_summarized} 条 / 失败 ${s.items_failed ?? 0} 条`)
        } else {
          msg.warning(`完成但 0 条新增: ${s.warning || '无内容或全部已抓过'}`, { duration: 6000 })
        }
        loadAll()
      }
    } catch (e: any) {
      console.warn('[ingest poll]', e)
    }
  }
  tick()
  pollTimer = window.setInterval(tick, 1500)
}

function stopPolling() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onBeforeUnmount(() => {
  stopPolling()
  if (scheduleTimer != null) {
    clearInterval(scheduleTimer)
    scheduleTimer = null
  }
})

// ===== 调用树跟踪 =====
const traceVisible = ref(false)
const traceLoading = ref(false)
const traceData = ref<any>(null)
const traceRunId = ref('')

async function openTrace(run_id: string) {
  traceRunId.value = run_id
  traceVisible.value = true
  traceLoading.value = true
  traceData.value = null
  try {
    traceData.value = await api<{
      task_run: any
      source_runs: any[]
      summary: { total_sources: number; ok_sources: number; fail_sources: number; disabled_sources: number; total_duration_ms: number }
    }>(`/admin/tasks/runs/${run_id}/trace`)
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载跟踪数据失败')
  } finally {
    traceLoading.value = false
  }
}

function traceStatusLabel(s: string) {
  return STATUS_LABEL[s] || s || '未知'
}

function traceStatusClass(s: string) {
  if (s === 'running') return 'bg-amber-100 text-amber-700'
  if (s === 'done') return 'bg-emerald-100 text-emerald-700'
  if (s === 'partial') return 'bg-amber-100 text-amber-700'
  if (s === 'failed' || s === 'stale') return 'bg-rose-100 text-rose-700'
  return 'bg-slate-100 text-slate-700'
}

function sourceRunBadgeClass(s: string) {
  if (s === 'ok') return 'bg-emerald-100 text-emerald-700'
  if (s === 'partial') return 'bg-amber-100 text-amber-700'
  if (s === 'fail') return 'bg-rose-100 text-rose-700'
  if (s === 'disabled') return 'bg-slate-200 text-slate-500'
  if (s === 'not_due') return 'bg-sky-100 text-sky-600'
  return 'bg-slate-100 text-slate-400'
}

function sourceRunBorderClass(s: string) {
  if (s === 'ok') return 'border-emerald-400'
  if (s === 'partial') return 'border-amber-400'
  if (s === 'fail') return 'border-rose-400'
  if (s === 'disabled') return 'border-slate-300'
  if (s === 'not_due') return 'border-sky-300 border-dashed'
  return 'border-slate-200 border-dashed'
}

function formatTime(t: string) {
  return t ? dayjs.utc(t).local().format('HH:mm:ss') : ''
}

// ===== 任务列表 =====
const TRIGGER_COLOR: Record<string, 'default' | 'success' | 'warning' | 'info'> = {
  scheduled: 'info', manual_api: 'success', manual_admin: 'warning', manual: 'warning', subs_run: 'default',
}
const TRIGGER_LABEL: Record<string, string> = {
  scheduled: '定时', manual_api: 'API', manual_admin: '手动', manual: '手动', subs_run: '订阅',
}

const cols: DataTableColumns<any> = [
  { title: '时间', key: 'started_at', width: 140,
    render: (r: any) => r.started_at ? dayjs.utc(r.started_at).local().format('MM-DD HH:mm') : '-' },
  { title: '触发', key: 'trigger', width: 70,
    render: (r: any) => h(NTag, { type: TRIGGER_COLOR[r.trigger] || 'default', size: 'small' }, () => TRIGGER_LABEL[r.trigger] || r.trigger) },
  { title: '状态', key: 'status', width: 90,
    render: (r: any) => h(NTag, {
      type: STATUS_TYPE[r.status] || 'default',
      size: 'small',
    }, () => STATUS_LABEL[r.status] || r.status || '-') },
  { title: '抓', key: 'items_fetched', width: 50 },
  { title: '成功', key: 'items_summarized', width: 50,
    render: (r: any) => h('span', { class: r.items_summarized > 0 ? 'text-emerald-600 font-medium' : 'text-slate-400' }, r.items_summarized ?? 0) },
  { title: '失败', key: 'items_failed', width: 50,
    render: (r: any) => h('span', { class: r.items_failed > 0 ? 'text-rose-600 font-medium' : 'text-slate-400' }, r.items_failed ?? 0) },
  { title: '源', key: 'source_stats', width: 110,
    render: (r: any) => {
      const st = r.source_stats
      if (!st) return h('span', { class: 'text-slate-300 text-xs' }, '-')
      const ok = st.ok || 0, fail = st.fail || 0, partial = st.partial || 0, disabled = st.disabled || 0
      const total = ok + fail + partial + disabled
      if (total === 0) return h('span', { class: 'text-slate-300 text-xs' }, '-')
      const cells = []
      if (ok) cells.push(h('span', { class: 'text-emerald-600 font-medium' }, `✓${ok}`))
      if (fail) cells.push(h('span', { class: 'text-rose-600 font-medium' }, `✗${fail}`))
      if (partial) cells.push(h('span', { class: 'text-amber-600 font-medium' }, `△${partial}`))
      if (disabled) cells.push(h('span', { class: 'text-slate-400' }, `⊘${disabled}`))
      return h('div', { class: 'flex items-center gap-1 text-xs font-mono' }, cells)
    } },
  { title: '说明', key: 'reason', minWidth: 180,
    render: (r: any) => {
      const reason = r.status_reason || r.warning || ''
      return h('span', {
        class: 'text-xs text-slate-500',
        title: reason,
      }, reason ? (reason.length > 30 ? reason.slice(0, 30) + '…' : reason) : '-')
    } },
  { title: '操作', key: 'actions', width: 100,
    render: (r: any) => h(NButton, { size: 'tiny', type: 'info', text: true, onClick: () => openTrace(r.run_id) }, () => '📊 跟踪') },
]

// 源级状态映射
const SR_TYPE: Record<string, 'success' | 'error' | 'warning' | 'info' | 'default'> = {
  ok: 'success', fail: 'error', partial: 'warning', disabled: 'info', not_due: 'info',
}
const SR_LABEL: Record<string, string> = {
  ok: '成功', fail: '失败', partial: '部分', disabled: '禁用', not_due: '未到',
}

async function loadAll() {
  try {
    const [ll, tr, sched] = await Promise.all([
      api<{ groups: Record<string, Record<string, any>> }>('/admin/llm/health'),
      api<any[]>('/admin/tasks/runs', { query: { limit: 20 } }),
      getScheduleOverview(),
    ])
    llmGroups.value = ll.groups
    runs.value = tr
    scheduleOverview.value = sched
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

// Day 10.5 · 立即抓所有到期源
async function triggerAllDue() {
  const due = (scheduleOverview.value?.items || []).filter(r =>
    r.is_active && r.interval_seconds > 0 && r.due_in_seconds <= 0
  )
  if (due.length === 0) {
    msg.info('当前无到期源')
    return
  }
  triggeringAll.value = true
  msg.info(`触发 ${due.length} 个到期源: ${due.slice(0, 3).map(d => d.source_id).join(', ')}${due.length > 3 ? '…' : ''}`)
  let ok = 0
  let fail = 0
  for (const r of due) {
    try {
      await runSourceNow(r.source_id, 8)
      ok++
    } catch (e) {
      console.warn(`run-now ${r.source_id}:`, e)
      fail++
    }
  }
  triggeringAll.value = false
  if (fail === 0) {
    msg.success(`已触发 ${ok} 个到期源`)
  } else {
    msg.warning(`触发完成:${ok} 成功 / ${fail} 失败`)
  }
  await loadAll()
}

// 调度详情表列
const scheduleCols: DataTableColumns<ScheduleRow> = [
  {
    title: '源',
    key: 'source_id',
    width: 180,
    render: (r) => h('span', { class: 'font-mono text-xs' }, r.source_id),
  },
  {
    title: '启用',
    key: 'is_active',
    width: 60,
    render: (r) => h(NTag, {
      type: r.is_active ? 'success' : 'default',
      size: 'small',
      bordered: false,
    }, { default: () => r.is_active ? '✓' : '✗' }),
  },
  {
    title: '间隔',
    key: 'interval_label',
    width: 80,
    render: (r) => h('span', { class: 'text-xs' }, r.interval_label),
  },
  {
    title: '上次',
    key: 'last_run_at',
    width: 140,
    render: (r) => h('span', { class: 'text-xs text-slate-500' }, r.last_run_at ? formatTime(r.last_run_at) : '—'),
  },
  {
    title: '下次',
    key: 'next_run_at',
    width: 140,
    render: (r) => h('span', { class: 'text-xs' }, r.next_run_at ? formatTime(r.next_run_at) : '—'),
  },
  {
    title: '距今',
    key: 'due_in_seconds',
    width: 100,
    render: (r) => {
      if (!r.is_active) return h('span', { class: 'text-xs text-slate-400' }, '禁用')
      if (r.interval_seconds === 0) return h('span', { class: 'text-xs text-amber-600' }, '手动')
      const d = r.due_in_seconds
      if (d <= 0) return h('span', { class: 'text-xs text-rose-600 font-medium' }, `已逾期 ${Math.abs(Math.round(d / 60))} 分`)
      if (d < 3600) return h('span', { class: 'text-xs text-slate-600' }, `${Math.round(d / 60)} 分后`)
      return h('span', { class: 'text-xs text-slate-600' }, `${(d / 3600).toFixed(1)} 时后`)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (r) => h(NButton, {
      size: 'tiny',
      type: 'primary',
      ghost: true,
      onClick: async () => {
        try {
          msg.loading(`抓 ${r.source_id}…`)
          const res = await runSourceNow(r.source_id, 8)
          msg.success(`${r.source_id}: 抓 ${res.fetched} / 摘要 ${res.summarized}`)
          await loadAll()
        } catch (e: any) {
          msg.error(`抓取失败: ${e?.message || e}`)
        }
      },
    }, { default: () => '▶ 抓' }),
  },
]

let scheduleTimer: number | null = null
async function refreshScheduleOnly() {
  try {
    scheduleOverview.value = await getScheduleOverview()
  } catch {
    // 静默
  }
}

onMounted(() => {
  loadAll()
  // 调度总览 60s 刷新 — 跟 daemon tick 对齐,看到 due_now 自然下降
  scheduleTimer = window.setInterval(refreshScheduleOnly, 60000)
})
</script>
