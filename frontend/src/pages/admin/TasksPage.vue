<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📡 爬取任务监控</h1>
      <n-button @click="loadAll">🔄 刷新</n-button>
      <nav class="flex gap-2 text-sm ml-auto">
        <router-link to="/admin" class="px-3 py-1 rounded hover:bg-slate-100">汇总</router-link>
        <router-link to="/admin/tasks" class="px-3 py-1 rounded bg-emerald-50 text-emerald-700">任务</router-link>
        <router-link to="/admin/banner" class="px-3 py-1 rounded hover:bg-slate-100">Banner</router-link>
      </nav>
    </div>

    <!-- 抓取源(按 L1 类目分组,独立开关) -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-4">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold">📰 抓取源</h2>
        <div class="flex items-center gap-2">
          <n-button size="small" @click="toggleAll(true)">全部启用</n-button>
          <n-button size="small" @click="toggleAll(false)">全部停用</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="saveSources">💾 保存</n-button>
        </div>
      </div>

      <div class="space-y-4">
        <div v-for="cat in l1Order" :key="cat">
          <h3 class="text-sm font-medium text-slate-500 mb-2 flex items-center gap-2">
            <span>{{ l1Icon(cat) }}</span>{{ cat }}
            <span class="text-xs text-slate-400">({{ groupedSources[cat]?.length || 0 }}个源)</span>
          </h3>
          <div v-if="(groupedSources[cat] || []).length" class="grid gap-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            <div
              v-for="s in groupedSources[cat]"
              :key="s.id"
              class="rounded-lg border p-3 flex items-center justify-between gap-2 transition"
              :class="s.enabled ? 'border-slate-200 bg-white' : 'border-slate-200 bg-slate-50 opacity-60'"
            >
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium text-slate-900 flex items-center gap-1">
                  <n-tag size="tiny" :bordered="false" :type="s.kind === 'rss' ? 'success' : 'warning'" class="!mr-1">
                    {{ s.kind === 'rss' ? 'RSS' : s.kind }}
                  </n-tag>
                  <span class="truncate">{{ s.name }}</span>
                </div>
                <div class="text-xs text-slate-500 mt-1">
                  抓取: {{ getSourceStat(s.id)?.fetched_24h ?? 0 }} ·
                  <span v-if="getSourceStat(s.id)?.healthy === false" class="text-red-500">⚠ 异常</span>
                  <span v-else class="text-emerald-600">正常</span>
                </div>
              </div>
              <n-switch size="small" :value="s.enabled" @update:value="(v: boolean) => s.enabled = v" />
            </div>
          </div>
        </div>
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
        >
          <template #expanded-row="{ row }">
            <div class="pl-8 py-2 bg-slate-50 rounded">
              <div class="text-xs text-slate-500 mb-2">各渠道详情</div>
              <div v-if="row.per_source && Object.keys(row.per_source).length" class="grid gap-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                <div
                  v-for="(info, src) in row.per_source"
                  :key="src"
                  class="bg-white rounded border border-slate-200 p-2 text-xs"
                >
                  <div class="font-medium text-slate-700 mb-1">{{ sourceName(String(src)) }}</div>
                  <div class="flex gap-3 text-slate-500">
                    <span>抓: <b class="text-slate-700">{{ info.fetched ?? 0 }}</b></span>
                    <span>摘: <b class="text-emerald-600">{{ info.summarized ?? 0 }}</b></span>
                    <span>败: <b class="text-red-500">{{ info.errors ?? 0 }}</b></span>
                  </div>
                </div>
              </div>
              <n-empty v-else size="small" description="暂无渠道详情" />
            </div>
          </template>
        </n-data-table>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { NButton, NEmpty, NDataTable, NSwitch, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import { api } from '@/lib/api'
import type { TaskRun, SourceStatus, LLMHealth, SourceConfigItem, SourceConfigResponse } from '@/types/api'

dayjs.extend(utc)
dayjs.extend(timezone)

const msg = useMessage()
const sourceConfig = ref<SourceConfigItem[]>([])
const sourceStatus = ref<SourceStatus[]>([])
const llmGroups = ref<LLMHealth['groups'] | null>(null)
const runs = ref<TaskRun[]>([])
const saving = ref(false)

const SOURCE_NAME_MAP: Record<string, string> = {
  ithome: 'IT之家', '36kr': '36氪', sspai: '少数派', infoq: 'InfoQ',
  qbitai: '量子位', ifanr: '爱范儿', huxiu: '虎嗅', douban: '豆瓣',
}
const sourceName = (s: string) => SOURCE_NAME_MAP[s] || s

const l1Order = ['AI', '科技', '财经', '汽车', '娱乐', '体育', '其他']
const l1IconMap: Record<string, string> = {
  科技: '🔬', AI: '🤖', 体育: '⚽', 娱乐: '🎬', 财经: '💰', 汽车: '🚗', 其他: '📂',
}
const l1Icon = (c: string) => l1IconMap[c] || '📂'

const groupedSources = computed(() => {
  const map: Record<string, SourceConfigItem[]> = {}
  for (const s of sourceConfig.value) {
    const c = s.category_l1 || '其他'
    if (!map[c]) map[c] = []
    map[c].push(s)
  }
  return map
})

function getSourceStat(id: string): SourceStatus | undefined {
  return sourceStatus.value.find(s => s.source === id)
}

const TRIGGER_COLOR: Record<string, 'default' | 'success' | 'warning' | 'info'> = {
  scheduled: 'info', manual_api: 'success', manual_admin: 'warning', subs_run: 'default',
}

const TRIGGER_LABEL: Record<string, string> = {
  scheduled: '定时', manual_api: 'API', manual_admin: '手动', subs_run: '订阅',
}

const cols: DataTableColumns<TaskRun> = [
  { title: '时间', key: 'started_at', width: 140,
    render: (r: TaskRun) => r.started_at ? dayjs.utc(r.started_at).local().format('MM-DD HH:mm') : '-' },
  { title: '触发', key: 'trigger', width: 70,
    render: (r: TaskRun) => h(NTag, { type: TRIGGER_COLOR[r.trigger] || 'default', size: 'small' }, () => TRIGGER_LABEL[r.trigger] || r.trigger) },
  { title: '抓', key: 'items_fetched', width: 40 },
  { title: '摘', key: 'items_summarized', width: 40 },
  { title: '败', key: 'items_failed', width: 40 },
]

function toggleAll(enable: boolean) {
  for (const s of sourceConfig.value) s.enabled = enable
}

async function saveSources() {
  saving.value = true
  try {
    const enabled = sourceConfig.value.filter(s => s.enabled).map(s => s.id)
    await api('/admin/sources', { method: 'PUT', body: { enabled } })
    msg.success(`已保存,启用 ${enabled.length} 个源`)
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function loadAll() {
  try {
    const [cfg, ss, ll, tr] = await Promise.all([
      api<SourceConfigResponse>('/admin/sources'),
      api<SourceStatus[]>('/admin/tasks/source-status'),
      api<LLMHealth>('/admin/llm/health'),
      api<TaskRun[]>('/admin/tasks/runs', { query: { limit: 20 } }),
    ])
    sourceConfig.value = [...cfg.rss, ...cfg.kol]
    sourceStatus.value = ss
    llmGroups.value = ll.groups
    runs.value = tr
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

onMounted(loadAll)
</script>
