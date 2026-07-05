<template>
  <div>
    <!-- 头部 -->
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📡 数据源管理</h1>
      <n-button @click="refreshAll" :loading="loading">🔄 刷新</n-button>
      <AdminTabs class="ml-auto" />
    </div>

    <!-- Agent 接入提示 -->
    <n-alert type="info" :show-icon="true" class="mb-4" :bordered="false">
      <span class="font-medium">新增数据源请通过 Agent 接入</span>
    </n-alert>

    <!-- 健康度总览(Day 6 扩展到 6 个:加 今日抓取数 / 今日新增 items) -->
    <section class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      <n-card size="small">
        <div class="text-xs text-slate-500">总源数</div>
        <div class="text-2xl font-bold">{{ healthSummary?.total_sources ?? '—' }}</div>
      </n-card>
      <n-card size="small">
        <div class="text-xs text-slate-500">启用</div>
        <div class="text-2xl font-bold text-emerald-600">{{ healthSummary?.active_sources ?? '—' }}</div>
      </n-card>
      <n-card size="small">
        <div class="text-xs text-slate-500">禁用</div>
        <div class="text-2xl font-bold text-rose-600">{{ healthSummary?.disabled_sources ?? '—' }}</div>
      </n-card>
      <n-card
        size="small"
        :class="['cursor-pointer transition', onlyFailing ? 'ring-2 ring-amber-400 bg-amber-50' : '']"
        @click="toggleFailingOnly"
        :title="onlyFailing ? '当前已开启:仅显示异常源,点此关闭' : '点此切换:仅显示异常源'"
      >
        <div class="text-xs text-slate-500 flex items-center gap-1">
          连续失败 ≥1
          <n-switch
            :value="onlyFailing"
            size="small"
            @click.stop="toggleFailingOnly"
          />
        </div>
        <div class="text-2xl font-bold text-amber-600">{{ failingSources }}</div>
        <div class="text-[10px] mt-0.5" :class="onlyFailing ? 'text-amber-600' : 'text-slate-400'">
          {{ onlyFailing ? '仅显示异常中 · 点此关闭' : '点击仅显示异常' }}
        </div>
      </n-card>
      <n-card size="small">
        <div class="text-xs text-slate-500">24h 抓取总数</div>
        <div class="text-2xl font-bold text-sky-600">{{ totals.fetched }}</div>
      </n-card>
      <n-card size="small">
        <div class="text-xs text-slate-500">24h 新增 items</div>
        <div class="text-2xl font-bold text-indigo-600">{{ totals.newItems }}</div>
      </n-card>
    </section>

    <!-- 筛选条 -->
    <div class="flex items-center gap-3 mb-3">
      <n-select
        v-model:value="filterL1"
        :options="l1Options"
        placeholder="全部 L1 类目"
        clearable
        style="width: 180px"
        size="small"
        @update:value="refreshAll"
      />
      <n-checkbox v-model:checked="activeOnly" @update:checked="refreshAll">
        仅显示启用
      </n-checkbox>
      <span class="ml-auto text-xs text-slate-500">
        共 {{ sources.length }} 条
      </span>
    </div>

    <!-- 批量操作栏(Day 6 新增) -->
    <section
      v-if="selectedSourceIds.length > 0"
      class="bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-2 mb-3 flex items-center gap-3 flex-wrap"
    >
      <span class="text-sm text-indigo-900 font-medium">
        已选 <b>{{ selectedSourceIds.length }}</b> 条
      </span>
      <span class="text-xs text-slate-500">
        ({{ selectedActiveCount }} 启用 / {{ selectedInactiveCount }} 禁用)
      </span>
      <div class="ml-auto flex items-center gap-2 flex-wrap">
        <n-button
          size="small"
          type="primary"
          :disabled="selectedActiveCount === selectedSourceIds.length"
          :loading="batchBusy"
          @click="onBatchToggle(true)"
        >
          ✅ 批量启用
        </n-button>
        <n-button
          size="small"
          type="warning"
          :disabled="selectedInactiveCount === selectedSourceIds.length"
          :loading="batchBusy"
          @click="onBatchToggle(false)"
        >
          ⏸ 批量禁用
        </n-button>
        <!-- Day 10.5 批量调度 -->
        <n-divider vertical />
        <n-select
          v-model:value="batchScheduleInterval"
          :options="schedulePresetOptions"
          size="small"
          placeholder="批量调度…"
          style="width: 140px"
          :disabled="batchBusy"
          @update:value="onBatchSchedule"
        />
        <n-button size="small" quaternary @click="clearSelection">清除选择</n-button>
      </div>
    </section>

    <!-- Day 10.5 · 调度总览卡 -->
    <section v-if="scheduleOverview" class="bg-white border border-slate-200 rounded-xl p-4 mb-3">
      <div class="flex items-center gap-3 mb-2">
        <span class="text-sm font-semibold text-slate-700">⏰ 抓取调度总览</span>
        <n-tag size="small" type="info" :bordered="false">daemon 调度器模式</n-tag>
        <span class="text-xs text-slate-400 ml-auto">每源独立 cron,daemon 每 60s 检查到期源</span>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
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
          :class="['rounded p-3 cursor-pointer transition',
                   scheduleOverview.due_now > 0 ? 'bg-rose-50 hover:bg-rose-100' : 'bg-slate-50']"
          @click="triggerAllDue"
          :title="scheduleOverview.due_now > 0 ? '点此立刻抓所有到期源' : '当前无到期源'"
        >
          <div class="text-xs" :class="scheduleOverview.due_now > 0 ? 'text-rose-700' : 'text-slate-500'">
            到期未跑
          </div>
          <div class="text-xl font-bold" :class="scheduleOverview.due_now > 0 ? 'text-rose-700' : 'text-slate-400'">
            {{ scheduleOverview.due_now }}
          </div>
          <div class="text-[10px]" :class="scheduleOverview.due_now > 0 ? 'text-rose-600' : 'text-slate-400'">
            {{ scheduleOverview.due_now > 0 ? '点此立刻抓 →' : '全部准时' }}
          </div>
        </div>
      </div>
    </section>

    <!-- 源列表与健康度 -->
    <section class="bg-white rounded-xl border border-slate-200 p-4">
      <div v-if="sources.length === 0 && !loading" class="py-10 text-center text-slate-400 text-sm">
        暂无数据源
      </div>
      <n-data-table
        v-else
        :columns="columns"
        :data="tableData"
        :loading="loading"
        :pagination="{ pageSize: 20 }"
        size="small"
        :bordered="false"
        :row-key="rowKey"
        :checked-row-keys="selectedSourceIds"
        @update:checked-row-keys="onSelectionChange"
      />
    </section>

    <!-- 编辑源弹窗 -->
    <n-modal v-model:show="showEditModal" preset="card" title="编辑数据源" style="max-width: 700px">
      <n-form :model="editingSource" label-placement="left" label-width="120" v-if="editingSource">
        <n-form-item label="source_id">
          <n-input :value="editingSource.source_id" disabled />
        </n-form-item>
        <n-form-item label="展示名">
          <n-input v-model:value="editingSource.display_name" />
        </n-form-item>
        <n-form-item label="L1 类目">
          <n-select v-model:value="editingSource.l1" :options="l1Options" />
        </n-form-item>
        <n-form-item label="URL">
          <n-input v-model:value="editingSource.url" />
        </n-form-item>
        <n-form-item label="cron (秒)">
          <n-input-number v-model:value="editingSource.cron_interval_seconds" :min="60" />
        </n-form-item>
        <n-form-item label="limit/run">
          <n-input-number v-model:value="editingSource.limit_per_run" :min="1" :max="100" />
        </n-form-item>
        <n-form-item label="禁用阈值">
          <n-input-number v-model:value="editingSource.auto_disable_threshold" :min="1" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="editingSource.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" @click="onSaveEdit" :loading="editing">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 测试抓取结果弹窗 -->
    <n-modal v-model:show="showTestResult" preset="card" :title="`测试抓取: ${testResult?.source_id || '?'}`" style="max-width: 800px">
      <div v-if="testResult">
        <div class="text-sm text-slate-500 mb-3">
          状态 <n-tag :type="statusTagType(testResult.status)">{{ testResult.status }}</n-tag>
          耗时 {{ testResult.duration_ms }}ms · 命中 {{ testResult.fetched_count }}
        </div>
        <div v-if="testResult.error" class="bg-rose-50 text-rose-700 p-3 rounded mb-3 text-sm">
          {{ testResult.error }}
        </div>
        <ul class="space-y-2 text-sm">
          <li v-for="(it, i) in testResult.items" :key="i" class="border-b pb-2">
            <a :href="it.url" target="_blank" class="text-blue-600 hover:underline">{{ it.title }}</a>
            <div class="text-xs text-slate-500">{{ it.source }} · {{ it.published_at || '—' }}</div>
          </li>
        </ul>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, h } from 'vue'
import {
  NAlert, NButton, NCard, NCheckbox, NDataTable,
  NForm, NFormItem, NInput, NInputNumber, NModal,
  NSelect, NSwitch, NTag, useMessage,
  type DataTableColumns,
} from 'naive-ui'
import {
  listSources, getHealthSummary, updateSource,
  toggleSource, testSource, batchToggleSources,
  getScheduleOverview, updateSchedule, batchUpdateSchedule, runSourceNow,
  type SourceConfig, type SourceHealthSummary, type RecentRun,
  type ScheduleRow,
} from '@/lib/api'
import AdminTabs from '@/components/AdminTabs.vue'

const message = useMessage()
const sources = ref<SourceConfig[]>([])
const healthSummary = ref<Awaited<ReturnType<typeof getHealthSummary>> | null>(null)
const loading = ref(false)

// 筛选
const filterL1 = ref<string | null>(null)
const activeOnly = ref(false)
const onlyFailing = ref(false)

// 批量选择(Day 6)
const selectedSourceIds = ref<string[]>([])
const batchBusy = ref(false)

const showEditModal = ref(false)
const showTestResult = ref(false)
const editing = ref(false)
const editingSource = ref<SourceConfig | null>(null)
const testResult = ref<any>(null)

// Day 10.5 · 调度总览
const scheduleOverview = ref<Awaited<ReturnType<typeof getScheduleOverview>> | null>(null)
const batchScheduleInterval = ref<number | null>(null)

// 调度预设(下拉选项,常见档位 — 选完立刻批量改)
const schedulePresetOptions = [
  { label: '⏱ 5 分钟', value: 300 },
  { label: '⏱ 10 分钟', value: 600 },
  { label: '⏱ 15 分钟', value: 900 },
  { label: '⏱ 30 分钟', value: 1800 },
  { label: '⏰ 1 小时', value: 3600 },
  { label: '⏰ 2 小时', value: 7200 },
  { label: '🕐 6 小时', value: 21600 },
  { label: '☀️ 12 小时', value: 43200 },
  { label: '📅 1 天', value: 86400 },
  { label: '✋ 仅手动', value: 0 },
]

const l1Options = ['科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他'].map(v => ({ label: v, value: v }))

const failingSources = computed(() => {
  if (!healthSummary.value?.items) return 0
  return healthSummary.value.items.filter(s => (s.consecutive_fails || 0) >= 1).length
})

// 24h 聚合:抓取总数 / 新增 items 数(从 health summary 直接聚合)
const totals = computed(() => {
  const items = healthSummary.value?.items || []
  return {
    fetched: items.reduce((s, i) => s + (i.total_fetched || 0), 0),
    newItems: items.reduce((s, i) => s + (i.total_new || 0), 0),
  }
})

// 已选中的源中,启用/禁用计数
const selectedActiveCount = computed(() => {
  if (!selectedSourceIds.value.length) return 0
  const map = new Map(sources.value.map(s => [s.source_id, !!s.is_active]))
  return selectedSourceIds.value.reduce((n, id) => n + (map.get(id) ? 1 : 0), 0)
})
const selectedInactiveCount = computed(() => selectedSourceIds.value.length - selectedActiveCount.value)

// 筛选条:异常源切换
function toggleFailingOnly() {
  onlyFailing.value = !onlyFailing.value
  // 不需要 refresh,因为仅是 UI 过滤,前端做即可
}

// 健康状态计算
function getHealth(row: SourceConfig): {
  rate: number | null
  total: number
  ok: number
  fail: number
  consecutive: number
  threshold: number
  color: 'emerald' | 'amber' | 'rose' | 'slate'
  label: string
  lastStatus: string | null
  lastRunAt: string | null
  recent: RecentRun[]
  disabledReason: string | null
} {
  const s = healthSummary.value?.items?.find(i => i.source_id === row.source_id) as SourceHealthSummary | undefined
  const threshold = row.auto_disable_threshold || 5
  if (!s) {
    return { rate: null, total: 0, ok: 0, fail: 0, consecutive: 0, threshold, color: 'slate', label: '无数据', lastStatus: null, lastRunAt: null, recent: [], disabledReason: null }
  }
  const consecutive = s.consecutive_fails || 0
  const total = s.total_runs || 0
  const ok = s.ok_runs || 0
  const fail = s.fail_runs || 0
  const rate = s.success_rate
  let color: 'emerald' | 'amber' | 'rose' | 'slate' = 'emerald'
  let label = '健康'
  if (!row.is_active) {
    color = 'slate'
    label = '已禁用'
  } else if (consecutive >= threshold) {
    color = 'rose'
    label = '已禁用'
  } else if (consecutive > 0) {
    color = 'amber'
    label = '异常'
  } else if (total === 0) {
    color = 'slate'
    label = '未运行'
  }
  return {
    rate, total, ok, fail, consecutive, threshold, color, label,
    lastStatus: s.last_status, lastRunAt: s.last_run_at,
    recent: s.recent_runs || [],
    disabledReason: s.disabled_reason || null,
  }
}

// 颜色 → Tailwind 静态类映射(避免 JIT 不扫到拼接类)
const colorBg: Record<'emerald' | 'amber' | 'rose' | 'slate', string> = {
  emerald: 'bg-emerald-500',
  amber: 'bg-amber-500',
  rose: 'bg-rose-500',
  slate: 'bg-slate-400',
}
const colorText: Record<'emerald' | 'amber' | 'rose' | 'slate', string> = {
  emerald: 'text-emerald-600',
  amber: 'text-amber-600',
  rose: 'text-rose-600',
  slate: 'text-slate-500',
}

async function refreshAll() {
  loading.value = true
  try {
    const [list, summary, sched] = await Promise.all([
      listSources({
        l1: filterL1.value || undefined,
        active_only: activeOnly.value,
      }),
      getHealthSummary(1),
      getScheduleOverview(),
    ])
    sources.value = list.items
    healthSummary.value = summary
    scheduleOverview.value = sched
    // 过滤掉失效选择(源被删后,rowKey 不在了,Naive UI 会自动清)
    const ids = new Set(sources.value.map(s => s.source_id))
    selectedSourceIds.value = selectedSourceIds.value.filter(id => ids.has(id))
  } catch (e: any) {
    message.error('加载失败:' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

// Day 10.5 · 调度相关
async function onUpdateSchedule(source_id: string, seconds: number) {
  try {
    const r = await updateSchedule(source_id, seconds)
    message.success(`${source_id} → ${r.label}`)
    await refreshAll()
  } catch (e: any) {
    message.error('调度修改失败: ' + (e?.message || e))
  }
}

async function onBatchSchedule(seconds: number | null) {
  if (seconds === null || selectedSourceIds.value.length === 0) return
  const label = schedulePresetOptions.find(o => o.value === seconds)?.label || `${seconds}s`
  batchBusy.value = true
  try {
    const res = await batchUpdateSchedule(selectedSourceIds.value, seconds)
    if (res.skipped && res.skipped.length > 0) {
      message.warning(`已批量调度 ${res.updated} 个源 → ${label} · 跳过 ${res.skipped.length}`)
    } else {
      message.success(`已批量调度 ${res.updated} 个源 → ${label}`)
    }
    batchScheduleInterval.value = null
    selectedSourceIds.value = []
    await refreshAll()
  } catch (e: any) {
    message.error('批量调度失败: ' + (e?.message || e))
  } finally {
    batchBusy.value = false
  }
}

async function triggerAllDue() {
  const due = (scheduleOverview.value?.items || []).filter(r =>
    r.is_active && r.interval_seconds > 0 && r.due_in_seconds <= 0
  )
  if (due.length === 0) {
    message.info('当前无到期源')
    return
  }
  message.info(`触发 ${due.length} 个到期源: ${due.slice(0, 3).map(d => d.source_id).join(', ')}${due.length > 3 ? '…' : ''}`)
  let ok = 0
  for (const r of due) {
    try {
      await runSourceNow(r.source_id, 8)
      ok++
    } catch (e: any) {
      console.warn(`run-now ${r.source_id}:`, e)
    }
  }
  message.success(`已触发 ${ok}/${due.length} 个到期源`)
  await refreshAll()
}

async function onRunNow(row: SourceConfig) {
  try {
    message.loading(`正在抓 ${row.source_id}…`)
    const r = await runSourceNow(row.source_id, 8)
    message.success(`${row.source_id}: 抓 ${r.fetched} / 摘要 ${r.summarized} / 失败 ${r.failed}`)
    await refreshAll()
  } catch (e: any) {
    message.error(`抓取失败: ${e?.message || e}`)
  }
}

async function onToggle(s: SourceConfig, next: boolean) {
  if (s.is_active === next) return
  try {
    await toggleSource(s.source_id)
    message.success(`${s.source_id} 已${next ? '启用' : '禁用'}`)
    await refreshAll()
  } catch (e: any) {
    message.error('操作失败: ' + (e?.message || e))
  }
}

function openEdit(s: SourceConfig) {
  editingSource.value = { ...s }
  showEditModal.value = true
}

async function onSaveEdit() {
  if (!editingSource.value) return
  editing.value = true
  try {
    await updateSource(editingSource.value.source_id, editingSource.value)
    message.success('已保存')
    showEditModal.value = false
    await refreshAll()
  } catch (e: any) {
    message.error('保存失败: ' + (e?.message || e))
  } finally {
    editing.value = false
  }
}

async function onTest(s: SourceConfig) {
  testResult.value = { source_id: s.source_id, status: '...', duration_ms: 0, fetched_count: 0, items: [] }
  showTestResult.value = true
  try {
    testResult.value = await testSource(s.source_id, 5)
  } catch (e: any) {
    testResult.value = {
      source_id: s.source_id,
      status: 'fail',
      duration_ms: 0,
      fetched_count: 0,
      items: [],
      error: e?.message || String(e),
    }
  }
}

function statusTagType(status: string): 'success' | 'warning' | 'error' | 'default' | 'info' {
  switch (status) {
    case 'ok': return 'success'
    case 'partial': return 'warning'
    case 'fail': return 'error'
    case 'disabled': return 'default'
    default: return 'info'
  }
}

function statusTagLabel(status: string): string {
  switch (status) {
    case 'ok': return 'OK'
    case 'partial': return '部分'
    case 'fail': return '失败'
    case 'disabled': return '禁用'
    default: return status || '?'
  }
}

function formatTime(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function rowKey(row: SourceConfig) {
  return row.source_id
}

function onSelectionChange(keys: string[]) {
  selectedSourceIds.value = keys
}

function clearSelection() {
  selectedSourceIds.value = []
}

async function onBatchToggle(isActive: boolean) {
  if (selectedSourceIds.value.length === 0) return
  batchBusy.value = true
  try {
    const res = await batchToggleSources(selectedSourceIds.value, isActive)
    const msg = isActive
      ? `已批量启用 ${res.updated} 个源`
      : `已批量禁用 ${res.updated} 个源`
    if (res.skipped && res.skipped.length > 0) {
      message.warning(`${msg} · 跳过 ${res.skipped.length} 个不存在: ${res.skipped.slice(0, 3).join(', ')}${res.skipped.length > 3 ? '...' : ''}`)
    } else {
      message.success(msg)
    }
    selectedSourceIds.value = []
    await refreshAll()
  } catch (e: any) {
    message.error('批量操作失败: ' + (e?.message || e))
  } finally {
    batchBusy.value = false
  }
}

// 表格渲染的源(包含 onlyFailing 过滤)
const tableData = computed(() => {
  if (!onlyFailing.value) return sources.value
  const failingIds = new Set(
    (healthSummary.value?.items || [])
      .filter(s => (s.consecutive_fails || 0) >= 1 || !s.is_active)
      .map(s => s.source_id)
  )
  return sources.value.filter(s => failingIds.has(s.source_id))
})

const columns: DataTableColumns<SourceConfig> = [
  { type: 'selection', width: 36 },
  {
    title: '开关',
    key: 'toggle',
    width: 70,
    render: (row: SourceConfig) => {
      // 自动禁用时用原生 title 显示原因(避免 NTooltip + h 函数组合的渲染坑)
      const st = getHealth(row)
      const titleTip = (st.disabledReason && !row.is_active) ? st.disabledReason : undefined
      return h(NSwitch, {
        size: 'small',
        value: !!row.is_active,
        title: titleTip,
        'aria-label': `${row.source_id} ${row.is_active ? '启用' : '禁用'}`,
        onUpdateValue: (v: boolean) => onToggle(row, v),
      })
    },
  },
  {
    title: '健康',
    key: 'health',
    width: 210,
    render: (row: SourceConfig) => {
      const st = getHealth(row)
      return h('div', { class: 'text-xs flex flex-col gap-0.5' }, [
        h('div', { class: 'flex items-center' }, [
          h('span', { class: `w-2 h-2 rounded-full inline-block mr-2 ${colorBg[st.color]}` }),
          h('span', { class: `font-medium ${colorText[st.color]}` }, st.label),
        ]),
        h('div', { class: 'text-slate-500' },
          `成功率 ${st.rate != null ? Math.round(st.rate * 100) + '%' : '—'} · 连续失败 ${st.consecutive}/${st.threshold}`),
        h('div', { class: 'text-slate-400' },
          `近 24h ${st.total} 次 (${st.ok} 成功 / ${st.fail} 失败)`),
      ])
    },
  },
  {
    title: 'source_id',
    key: 'source_id',
    width: 170,
    render: (row: SourceConfig) => h('span', { class: 'font-mono text-xs' }, row.source_id),
  },
  {
    title: 'kind',
    key: 'kind',
    width: 90,
    render: (row: SourceConfig) => h('span', { class: 'text-xs text-slate-500' }, row.kind || '—'),
  },
  {
    title: 'L1',
    key: 'l1',
    width: 70,
    render: (row: SourceConfig) => h('span', { class: 'text-xs' }, row.l1 || '—'),
  },
  {
    title: '展示名',
    key: 'display_name',
    render: (row: SourceConfig) => h('span', null, row.display_name || '—'),
  },
  {
    title: '调度',
    key: 'schedule',
    width: 200,
    render: (row: SourceConfig) => {
      const sched = scheduleOverview.value?.items?.find(s => s.source_id === row.source_id) as ScheduleRow | undefined
      const seconds = sched?.interval_seconds ?? row.cron_interval_seconds ?? 0
      const label = sched?.interval_label || (seconds > 0 ? `${Math.round(seconds / 60)} 分钟` : '手动')
      const dueIn = sched?.due_in_seconds ?? null
      const lastRun = sched?.last_run_at
      // 到期/逾期高亮
      let dueHint = ''
      let dueClass = 'text-slate-400'
      if (row.is_active && seconds > 0 && dueIn !== null) {
        if (dueIn <= 0) {
          dueHint = '已到期'
          dueClass = 'text-rose-600 font-medium'
        } else if (dueIn < 300) {
          dueHint = `${Math.round(dueIn / 60)} 分钟后`
          dueClass = 'text-amber-600'
        } else {
          dueHint = `${Math.round(dueIn / 60)} 分钟后`
          dueClass = 'text-slate-400'
        }
      } else if (seconds === 0) {
        dueHint = '仅手动'
        dueClass = 'text-amber-600'
      } else if (!row.is_active) {
        dueHint = '已禁用'
        dueClass = 'text-slate-400'
      }
      return h('div', { class: 'text-xs flex flex-col gap-0.5' }, [
        h('div', { class: 'flex items-center gap-1' }, [
          h('span', { class: 'font-medium text-slate-700' }, label),
          h(NSelect, {
            size: 'tiny',
            value: seconds,
            options: schedulePresetOptions,
            style: 'width: 100px',
            placeholder: '改',
            'onUpdate:value': (v: number) => onUpdateSchedule(row.source_id, v),
          }),
        ]),
        h('div', { class: dueClass }, dueHint),
        h('div', { class: 'text-slate-400' },
          lastRun ? `上次 ${formatTime(lastRun)}` : '尚未跑过'),
      ])
    },
  },
  {
    title: '最近 3 次',
    key: 'recent_runs',
    width: 200,
    render: (row: SourceConfig) => {
      const st = getHealth(row)
      const runs = (st.recent || []).slice(0, 3)
      if (runs.length === 0) {
        return h('span', { class: 'text-xs text-slate-400' }, '暂无')
      }
      // 直接 NTag 横排,hover 用浏览器原生 title(避免 NTooltip + h 函数的渲染坑)
      return h('div', { class: 'flex items-center gap-1' },
        runs.map((r) => {
          const tip = [
            `${statusTagLabel(r.status)} · ${formatTime(r.ended_at)}`,
            r.duration_ms ? `${r.duration_ms}ms` : '',
            `命中 ${r.fetched_count} / 新增 ${r.new_count}`,
            r.error_msg ? `· ${r.error_msg}` : '',
          ].filter(Boolean).join(' · ')
          return h(NTag, {
            type: statusTagType(r.status),
            size: 'small',
            bordered: false,
            title: tip,
            class: 'text-xs cursor-help',
          }, { default: () => statusTagLabel(r.status) })
        })
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render: (row: SourceConfig) => h('div', { class: 'flex items-center gap-1' }, [
      h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => onRunNow(row) }, { default: () => '▶ 立即抓' }),
      h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
      h(NButton, { size: 'small', type: 'info', ghost: true, onClick: () => onTest(row) }, { default: () => '测试' }),
    ]),
  },
]

onMounted(() => {
  refreshAll()
  // 跨页自动刷新:从其他页(尤其是 MonitoringPage)改了源之后,回来自动看到最新
  window.addEventListener('focus', refreshAll)
  document.addEventListener('visibilitychange', onVisible)
  window.addEventListener('fastinfo:sources-changed', onSourcesChanged)
  // Day 10.5:调度总览定时刷新(60s,与 daemon tick 对齐 — 看到 due_now 变化)
  scheduleTimer = window.setInterval(refreshScheduleOnly, 60000)
})

onBeforeUnmount(() => {
  window.removeEventListener('focus', refreshAll)
  document.removeEventListener('visibilitychange', onVisible)
  window.removeEventListener('fastinfo:sources-changed', onSourcesChanged)
  if (scheduleTimer != null) {
    clearInterval(scheduleTimer)
    scheduleTimer = null
  }
})

// 仅刷新 schedule(轻量,60s 一次,比整个 refreshAll 轻)
let scheduleTimer: number | null = null
async function refreshScheduleOnly() {
  try {
    scheduleOverview.value = await getScheduleOverview()
  } catch {
    // 静默,不打扰用户
  }
}

function onVisible() {
  if (document.visibilityState === 'visible') refreshAll()
}

function onSourcesChanged() {
  // MonitoringPage 上 enable/toggle/batch-toggle 完会广播这个事件
  refreshAll()
}
</script>