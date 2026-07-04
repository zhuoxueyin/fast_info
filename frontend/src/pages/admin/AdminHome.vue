<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">🔧 管理后台</h1>
      <nav class="flex gap-2 text-sm">
        <router-link to="/admin" class="px-3 py-1 rounded bg-emerald-50 text-emerald-700">汇总</router-link>
        <router-link to="/admin/tasks" class="px-3 py-1 rounded hover:bg-slate-100">任务</router-link>
        <router-link to="/admin/banner" class="px-3 py-1 rounded hover:bg-slate-100">Banner 配置</router-link>
      </nav>
    </div>

    <div v-if="stats" class="grid gap-4 md:grid-cols-4 mb-6">
      <StatCard label="总 items" :value="stats.total_items" icon="📰" />
      <StatCard label="总用户" :value="stats.total_users" icon="👥" />
      <StatCard label="总订阅" :value="stats.total_subscriptions" icon="📡" />
      <StatCard label="总推送" :value="stats.total_delivered" icon="📬" />
    </div>

    <div class="grid lg:grid-cols-2 gap-6">
      <section class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-lg font-semibold mb-4">📊 来源分布</h2>
        <v-chart v-if="stats?.by_source?.length" :option="sourceChart" style="height: 280px" autoresize />
        <n-empty v-else />
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-lg font-semibold mb-4">🏷 类目分布 Top 15</h2>
        <v-chart v-if="stats?.by_category?.length" :option="categoryChart" style="height: 280px" autoresize />
        <n-empty v-else />
      </section>
    </div>

    <section class="bg-white rounded-xl border border-slate-200 p-6 mt-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">🚀 手动触发 ingest</h2>
        <n-button type="primary" :loading="ingesting" @click="triggerIngest">运行</n-button>
      </div>
      <p class="text-sm text-slate-500 mb-3">每个源最多抓 {{ ingestLimit }} 条;会真调 LLM 生成摘要(后台异步,几秒到几十秒)。</p>
      <n-input-number v-model:value="ingestLimit" :min="1" :max="30" class="!w-32 mb-3" :disabled="ingesting" />

      <!-- 实时进度 -->
      <div v-if="ingestResult" class="mt-3 space-y-2">
        <div class="flex items-center gap-2 text-sm">
          <span class="px-2 py-0.5 rounded text-xs font-mono"
                :class="statusBadgeClass">
            {{ statusLabel }}
          </span>
          <span class="text-slate-500 font-mono text-xs">run_id: {{ ingestResult.run_id }}</span>
          <span class="text-slate-400 text-xs" v-if="ingestResult.trigger">· {{ ingestResult.trigger }}</span>
          <span class="text-slate-400 text-xs" v-if="ingestResult.operator">· 操作人 {{ ingestResult.operator }}</span>
        </div>

        <!-- 进度数字 -->
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

        <!-- 耗时 -->
        <div v-if="ingestResult.duration_sec != null" class="text-xs text-slate-500">
          耗时 {{ ingestResult.duration_sec }} 秒
        </div>

        <!-- warning / error -->
        <n-alert v-if="ingestResult.warning" type="warning" :title="ingestResult.warning" :show-icon="true" />
        <n-alert v-else-if="ingestResult.status === 'done' && ingestResult.items_summarized > 0" type="success" title="完成" :show-icon="true" />
        <n-alert v-else-if="ingestResult.status === 'done'" type="info" title="完成(无新内容)" :show-icon="true" />

        <!-- 按源明细 -->
        <details v-if="ingestResult.per_source && Object.keys(ingestResult.per_source).length" class="text-xs">
          <summary class="cursor-pointer text-slate-600 hover:text-slate-900">按源明细({{ Object.keys(ingestResult.per_source).length }} 个)</summary>
          <table class="w-full mt-2 text-left">
            <thead><tr class="text-slate-500"><th class="py-1">源</th><th class="py-1">fetched</th><th class="py-1">summarized</th><th class="py-1">errors</th></tr></thead>
            <tbody>
              <tr v-for="(v, k) in ingestResult.per_source" :key="k" class="border-t border-slate-100">
                <td class="py-1 font-mono">{{ k }}</td>
                <td class="py-1">{{ v.fetched }}</td>
                <td class="py-1">{{ v.summarized }}</td>
                <td class="py-1">{{ v.errors }}</td>
              </tr>
            </tbody>
          </table>
        </details>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, h } from 'vue'
import { NEmpty, NButton, NInputNumber, NAlert, useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api } from '@/lib/api'
import type { Stats } from '@/types/api'

use([CanvasRenderer, BarChart, PieChart, TooltipComponent, LegendComponent, GridComponent, TitleComponent])

const msg = useMessage()
const stats = ref<Stats | null>(null)
const ingesting = ref(false)
const ingestResult = ref<any>(null)
const ingestLimit = ref(8)
let pollTimer: number | null = null

const statusLabel = computed(() => {
  const s = ingestResult.value?.status
  if (s === 'running') return '抓取中…'
  if (s === 'done') return '完成'
  if (s === 'failed') return '失败'
  return s || '未知'
})

const statusBadgeClass = computed(() => {
  const s = ingestResult.value?.status
  if (s === 'running') return 'bg-amber-100 text-amber-700 animate-pulse'
  if (s === 'done') return 'bg-emerald-100 text-emerald-700'
  if (s === 'failed') return 'bg-rose-100 text-rose-700'
  return 'bg-slate-100 text-slate-700'
})

const sourceChart = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  xAxis: { type: 'category', data: stats.value?.by_source.map(s => s._id) || [], axisLabel: { rotate: 30 } },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar', data: stats.value?.by_source.map(s => s.count) || [],
    itemStyle: { color: '#10B981' },
  }],
}))

const categoryChart = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: stats.value?.by_category.slice(0, 15).map(c => ({ name: c._id || '其他', value: c.count })) || [],
  }],
}))

async function load() {
  try {
    stats.value = await api<Stats>('/admin/stats')
  } catch (e: any) { msg.error(e?.data?.detail || '加载失败') }
}

async function triggerIngest() {
  ingesting.value = true
  ingestResult.value = null
  stopPolling()  // 清掉可能残留的轮询
  try {
    // 1. POST 触发(立刻返回 run_id + status=running)
    const r = await api<{
      run_id: string;
      status: string;
      trigger?: string;
      operator?: string;
      limit?: number;
    }>(`/admin/ingest/run`, {
      method: 'POST',
      query: { limit: ingestLimit.value },
      timeout: 10000,  // 5s 内必返,无需 120s
    })
    ingestResult.value = {
      run_id: r.run_id,
      status: r.status,
      trigger: r.trigger,
      operator: r.operator,
      limit: r.limit,
      started_at: new Date().toISOString(),
    }
    msg.info(`已触发,run_id=${r.run_id.slice(0, 8)}…,开始轮询…`, { duration: 2000 })

    // 2. 开始轮询,直到 status=done/failed
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
        run_id: string;
        status: string;
        started_at?: string;
        finished_at?: string | null;
        items_fetched?: number;
        items_summarized?: number;
        items_failed?: number;
        warning?: string;
        per_source?: Record<string, { fetched: number; summarized: number; errors: number; latency_ms?: number }>;
      }>(`/admin/ingest/task/${run_id}`, { timeout: 5000 })

      const duration_sec = s.finished_at
        ? Math.round((new Date(s.finished_at).getTime() - new Date(s.started_at).getTime()) / 1000)
        : Math.round((Date.now() - started_ms) / 1000)

      ingestResult.value = { ...ingestResult.value, ...s, duration_sec }

      if (s.status === 'done' || s.status === 'failed') {
        stopPolling()
        ingesting.value = false
        // 顶层提示
        if (s.status === 'failed') {
          msg.error(`任务失败: ${s.warning || '未知原因'}`)
        } else if ((s.items_summarized ?? 0) > 0) {
          msg.success(`完成: 新增 ${s.items_summarized} 条 / 失败 ${s.items_failed ?? 0} 条`)
        } else {
          msg.warning(`完成但 0 条新增: ${s.warning || '无内容或全部已抓过'}`, { duration: 6000 })
        }
        load()  // 刷一下汇总数字
      }
    } catch (e: any) {
      // 404 / 网络抖动不立刻停,重试下一次
      console.warn('[ingest poll]', e)
    }
  }
  // 立即跑一次,然后每 1.5s
  tick()
  pollTimer = window.setInterval(tick, 1500)
}

function stopPolling() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onBeforeUnmount(() => stopPolling())

const StatCard = (props: { label: string; value: number; icon: string }) =>
  h('div', { class: 'bg-white rounded-xl border border-slate-200 p-4' }, [
    h('div', { class: 'text-2xl mb-1' }, props.icon),
    h('div', { class: 'text-2xl font-bold text-slate-900' }, String(props.value)),
    h('div', { class: 'text-xs text-slate-500' }, props.label),
  ])

onMounted(load)
</script>