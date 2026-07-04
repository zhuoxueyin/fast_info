<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📡 爬取任务监控</h1>
      <n-button @click="loadAll">🔄 刷新</n-button>
      <nav class="flex gap-2 text-sm ml-auto">
        <router-link to="/admin" class="px-3 py-1 rounded hover:bg-slate-100">汇总</router-link>
        <router-link to="/admin/tasks" class="px-3 py-1 rounded bg-emerald-50 text-emerald-700">任务</router-link>
        <router-link to="/admin/sources" class="px-3 py-1 rounded hover:bg-slate-100">数据源</router-link>
        <router-link to="/admin/banner" class="px-3 py-1 rounded hover:bg-slate-100">Banner</router-link>
      </nav>
    </div>

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
                  <div class="font-medium text-slate-700 mb-1">{{ src }}</div>
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
import { ref, onMounted, h } from 'vue'
import { NButton, NEmpty, NDataTable, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import { api } from '@/lib/api'

dayjs.extend(utc)
dayjs.extend(timezone)

const msg = useMessage()
const llmGroups = ref<Record<string, Record<string, any>> | null>(null)
const runs = ref<any[]>([])

const TRIGGER_COLOR: Record<string, 'default' | 'success' | 'warning' | 'info'> = {
  scheduled: 'info', manual_api: 'success', manual_admin: 'warning', subs_run: 'default',
}

const TRIGGER_LABEL: Record<string, string> = {
  scheduled: '定时', manual_api: 'API', manual_admin: '手动', subs_run: '订阅',
}

const cols: DataTableColumns<any> = [
  { title: '时间', key: 'started_at', width: 140,
    render: (r: any) => r.started_at ? dayjs.utc(r.started_at).local().format('MM-DD HH:mm') : '-' },
  { title: '触发', key: 'trigger', width: 70,
    render: (r: any) => h(NTag, { type: TRIGGER_COLOR[r.trigger] || 'default', size: 'small' }, () => TRIGGER_LABEL[r.trigger] || r.trigger) },
  { title: '抓', key: 'items_fetched', width: 40 },
  { title: '摘', key: 'items_summarized', width: 40 },
  { title: '败', key: 'items_failed', width: 40 },
]

async function loadAll() {
  try {
    const [ll, tr] = await Promise.all([
      api<{ groups: Record<string, Record<string, any>> }>('/admin/llm/health'),
      api<any[]>('/admin/tasks/runs', { query: { limit: 20 } }),
    ])
    llmGroups.value = ll.groups
    runs.value = tr
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

onMounted(loadAll)
</script>
