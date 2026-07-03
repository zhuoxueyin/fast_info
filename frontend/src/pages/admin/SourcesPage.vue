<template>
  <div>
    <!-- 头部 -->
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📡 数据源管理</h1>
      <n-button @click="refreshAll" :loading="loading">🔄 刷新</n-button>
      <n-button type="primary" @click="showAddModal = true">+ 新增源</n-button>
      <nav class="flex gap-2 text-sm ml-auto">
        <router-link to="/admin" class="px-3 py-1 rounded hover:bg-slate-100">汇总</router-link>
        <router-link to="/admin/tasks" class="px-3 py-1 rounded hover:bg-slate-100">任务</router-link>
        <router-link to="/admin/sources" class="px-3 py-1 rounded bg-emerald-50 text-emerald-700">源</router-link>
        <router-link to="/admin/banner" class="px-3 py-1 rounded hover:bg-slate-100">Banner</router-link>
      </nav>
    </div>

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

    <!-- 健康度表格 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h2 class="text-lg font-semibold mb-4">源列表与健康度</h2>
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

    <!-- 新增源弹窗 -->
    <n-modal v-model:show="showAddModal" preset="card" title="新增数据源" style="max-width: 600px">
      <n-form :model="newSource" label-placement="left" label-width="120">
        <n-form-item label="source_id">
          <n-input v-model:value="newSource.source_id" placeholder="如 newrss / weibo:12345" />
        </n-form-item>
        <n-form-item label="kind">
          <n-select
            v-model:value="newSource.kind"
            :options="kindOptions"
            placeholder="选择类型"
          />
        </n-form-item>
        <n-form-item label="展示名">
          <n-input v-model:value="newSource.display_name" placeholder="中文显示名" />
        </n-form-item>
        <n-form-item label="URL">
          <n-input v-model:value="newSource.url" placeholder="主 URL(或微博/X 的 uid)" />
        </n-form-item>
        <n-form-item label="一级类目 L1">
          <n-select v-model:value="newSource.l1" :options="l1Options" placeholder="选 L1" />
        </n-form-item>
        <n-form-item label="limit/run">
          <n-input-number v-model:value="newSource.limit_per_run" :min="1" :max="100" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="showAddModal = false">取消</n-button>
          <n-button type="primary" @click="onAdd" :loading="adding">创建</n-button>
        </div>
      </template>
    </n-modal>

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
import { NButton, NTag, NSwitch, NSpace, useMessage } from 'naive-ui'
import {
  listSources, getHealthSummary, createSource, updateSource,
  toggleSource, testSource, type SourceConfig, type SourceHealthSummary,
} from '@/lib/api'

const message = useMessage()
const sources = ref<SourceConfig[]>([])
const healthSummary = ref<Awaited<ReturnType<typeof getHealthSummary>> | null>(null)
const loading = ref(false)

const showAddModal = ref(false)
const showEditModal = ref(false)
const showTestResult = ref(false)
const adding = ref(false)
const editing = ref(false)
const editingSource = ref<SourceConfig | null>(null)
const testResult = ref<any>(null)

const l1Options = ['科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他'].map(v => ({ label: v, value: v }))
const kindOptions = [
  { label: 'RSS / Atom', value: 'rss' },
  { label: '微博用户', value: 'weibo_user' },
  { label: 'X(Twitter)用户', value: 'x_user' },
  { label: '小红书用户', value: 'xhs_note' },
]

const newSource = ref<Partial<SourceConfig>>({
  source_id: '',
  kind: 'rss',
  display_name: '',
  url: '',
  l1: '科技',
  limit_per_run: 15,
})

const failingSources = computed(() => {
  if (!healthSummary.value?.items) return 0
  return healthSummary.value.items.filter(s => (s.consecutive_fails || 0) >= 1).length
})

async function refreshAll() {
  loading.value = true
  try {
    const [list, summary] = await Promise.all([
      listSources(),
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

async function onToggle(s: SourceConfig) {
  try {
    await toggleSource(s.source_id)
    message.success(`${s.source_id} 已${s.is_active ? '禁用' : '启用'}`)
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

async function onAdd() {
  if (!newSource.value.source_id || !newSource.value.kind) {
    message.warning('source_id 和 kind 必填')
    return
  }
  adding.value = true
  try {
    await createSource(newSource.value)
    message.success('已创建')
    showAddModal.value = false
    newSource.value = {
      source_id: '', kind: 'rss', display_name: '', url: '', l1: '科技', limit_per_run: 15,
    }
    await refreshAll()
  } catch (e: any) {
    message.error('创建失败: ' + (e?.message || e))
  } finally {
    adding.value = false
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

const columns = computed(() => [
  {
    title: '状态',
    key: 'is_active',
    width: 90,
    render: (row: SourceConfig) =>
      h(NTag, { type: row.is_active ? 'success' : 'error', size: 'small' }, () => row.is_active ? '启用' : '禁用'),
  },
  {
    title: 'health',
    key: 'health_cell',
    width: 180,
    render: (row: SourceConfig) => {
      const s = healthSummary.value?.items?.find(i => i.source_id === row.source_id) as SourceHealthSummary | undefined
      if (!s) return '—'
      const rate = s.success_rate != null ? `${Math.round(s.success_rate * 100)}%` : '—'
      const fc = s.consecutive_fails || 0
      const color = fc >= row.auto_disable_threshold ? 'error' : (fc > 0 ? 'warning' : 'success')
      return h('div', { class: 'text-xs' }, [
        h('div', { class: `text-${color === 'error' ? 'rose' : color === 'warning' ? 'amber' : 'emerald'}-600 font-medium` }, `成功率 ${rate}`),
        h('div', { class: 'text-slate-500' }, `连续失败 ${fc}/${row.auto_disable_threshold}`),
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
    title: '操作',
    key: 'actions',
    width: 280,
    render: (row: SourceConfig) =>
      h(NSpace, { size: 4 }, () => [
        h(NButton, { size: 'small', onClick: () => onToggle(row) }, () => row.is_active ? '禁用' : '启用'),
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, () => '编辑'),
        h(NButton, { size: 'small', type: 'info', onClick: () => onTest(row) }, () => '测试'),
      ]),
  },
])

onMounted(refreshAll)
</script>
