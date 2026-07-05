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
      <template #header>
        <span class="font-medium">新增数据源请通过 Agent 接入</span>
      </template>
      页面暂不开放手工新建。后续源接入统一由 Agent 完成(抓取策略 / 镜像 / 配额等由 Agent 自动配置)。
      可通过「编辑」调整现有源的展示名、L1 类目、cron 周期与单次抓取上限。
    </n-alert>

    <!-- 健康度总览 -->
    <section class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
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
      <n-card size="small">
        <div class="text-xs text-slate-500">连续失败 ≥1 的源</div>
        <div class="text-2xl font-bold text-amber-600">{{ failingSources }}</div>
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
        共 {{ (sources || []).length }} 条
      </span>
    </div>

    <!-- 源列表与健康度 -->
    <section class="bg-white rounded-xl border border-slate-200 p-4">
      <n-data-table
        :columns="columns"
        :data="(sources || [])"
        :loading="loading"
        :pagination="{ pageSize: 20 }"
        size="small"
        :bordered="false"
        :row-key="(row: any) => row.source_id"
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
          状态 <n-tag :type="statusTagType(testResult.status) as any">{{ testResult.status }}</n-tag>
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
import { ref, computed, h, onMounted } from 'vue'
import { NButton, NTag, NSwitch, NSpace, NCheckbox, NSelect, useMessage } from 'naive-ui'
import {
  listSources, getHealthSummary, updateSource,
  toggleSource, testSource, type SourceConfig, type SourceHealthSummary,
} from '@/lib/api'
import AdminTabs from '@/components/AdminTabs.vue'

const message = useMessage()
const sources = ref<SourceConfig[]>([])
const healthSummary = ref<Awaited<ReturnType<typeof getHealthSummary>> | null>(null)
const loading = ref(false)

// 筛选
const filterL1 = ref<string | null>(null)
const activeOnly = ref(false)

const showEditModal = ref(false)
const showTestResult = ref(false)
const editing = ref(false)
const editingSource = ref<SourceConfig | null>(null)
const testResult = ref<any>(null)

const l1Options = ['科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他'].map(v => ({ label: v, value: v }))

const failingSources = computed(() => {
  if (!healthSummary.value?.items) return 0
  return healthSummary.value.items.filter(s => (s.consecutive_fails || 0) >= 1).length
})

async function refreshAll() {
  loading.value = true
  try {
    const [list, summary] = await Promise.all([
      listSources({
        l1: filterL1.value || undefined,
        active_only: activeOnly.value,
      }),
      getHealthSummary(1),
    ])
    sources.value = list.items
    healthSummary.value = summary
  } catch (e: any) {
    message.error('加载失败:' + (e?.message || e))
  } finally {
    loading.value = false
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

function statusTagType(status: string) {
  switch (status) {
    case 'ok': return 'success'
    case 'partial': return 'warning'
    case 'fail': return 'error'
    case 'disabled': return 'default'
    default: return 'info'
  }
}

function healthState(row: SourceConfig) {
  const s = healthSummary.value?.items?.find(i => i.source_id === row.source_id) as SourceHealthSummary | undefined
  if (!s) {
    return { rate: null, total: 0, ok: 0, fail: 0, consecutive: 0, threshold: 5, color: 'slate', label: '无数据' }
  }
  const consecutive = s.consecutive_fails || 0
  const threshold = row.auto_disable_threshold || 5
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
  return { rate, total, ok, fail, consecutive, threshold, color, label }
}

// 行内开关 loading 状态
const toggling: Record<string, boolean> = {}

const columns = computed(() => [
  {
    title: '开关',
    key: 'toggle',
    width: 80,
    render: (row: SourceConfig) =>
      h(NSwitch, {
        size: 'small',
        value: row.is_active,
        loading: toggling[row.source_id] === true,
        onUpdateValue: (v: boolean) => {
          toggling[row.source_id] = true
          onToggle(row, v).finally(() => { delete toggling[row.source_id] })
        },
      }),
  },
  {
    title: '健康',
    key: 'health',
    width: 220,
    render: (row: SourceConfig) => {
      const st = healthState(row)
      const dotCls = `w-2 h-2 rounded-full bg-${st.color}-500 inline-block mr-2`
      return h('div', { class: 'text-xs flex flex-col gap-0.5' }, [
        h('div', { class: 'flex items-center' }, [
          h('span', { class: dotCls }),
          h('span', { class: `text-${st.color}-600 font-medium` }, st.label),
        ]),
        h('div', { class: 'text-slate-500' }, [
          `成功率 ${st.rate != null ? Math.round(st.rate * 100) + '%' : '—'}`,
          ` · 连续失败 ${st.consecutive}/${st.threshold}`,
        ]),
        h('div', { class: 'text-slate-400' }, `近 24h ${st.total} 次(${st.ok} 成功 / ${st.fail} 失败)`),
      ])
    },
  },
  { title: 'source_id', key: 'source_id', width: 180 },
  { title: 'kind', key: 'kind', width: 110 },
  { title: 'L1', key: 'l1', width: 80 },
  {
    title: '展示名',
    key: 'display_name',
    render: (row: SourceConfig) => row.display_name || '—',
  },
  {
    title: 'cron',
    key: 'cron_interval_seconds',
    width: 90,
    render: (row: SourceConfig) => row.cron_interval_seconds ? `${Math.round((row.cron_interval_seconds || 0) / 60)}min` : '—',
  },
  {
    title: 'limit',
    key: 'limit_per_run',
    width: 70,
  },
  {
    title: '最近抓取',
    key: 'last_run',
    width: 160,
    render: (row: SourceConfig) => {
      const s = healthSummary.value?.items?.find(i => i.source_id === row.source_id) as SourceHealthSummary | undefined
      if (!s || !s.last_run_at) return h('span', { class: 'text-slate-400 text-xs' }, '—')
      const tag = statusTagType(s.last_status || '')
      return h('div', { class: 'text-xs flex flex-col' }, [
        h(NTag, { type: tag as any, size: 'small', bordered: false }, () => s.last_status || '?'),
        h('span', { class: 'text-slate-400 mt-0.5' }, formatTime(s.last_run_at)),
      ])
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render: (row: SourceConfig) =>
      h(NSpace, { size: 4 }, () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, () => '编辑'),
        h(NButton, { size: 'small', type: 'info', ghost: true, onClick: () => onTest(row) }, () => '测试'),
      ]),
  },
])

function formatTime(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(refreshAll)
</script>