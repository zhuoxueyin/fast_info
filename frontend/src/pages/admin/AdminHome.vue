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
      <p class="text-sm text-slate-500 mb-3">每个源最多抓 {{ ingestLimit }} 条;会真调 LLM 生成摘要(几秒到几十秒)。</p>
      <n-input-number v-model:value="ingestLimit" :min="1" :max="30" class="!w-32 mb-3" />
      <n-alert v-if="ingestResult" type="success" :title="`run_id: ${ingestResult.run_id}`">
        抓 {{ ingestResult.items_fetched }} / 摘要 {{ ingestResult.items_summarized }} / 失败 {{ ingestResult.items_failed }}
      </n-alert>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
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
  try {
    const r = await api<{ run_id: string; items_fetched: number; items_summarized: number; items_failed: number }>(
      `/admin/ingest/run`, { method: 'POST', query: { limit: ingestLimit.value }, timeout: 120000 }
    )
    ingestResult.value = r
    msg.success('完成')
    load()
  } catch (e: any) {
    msg.error(e?.data?.detail || '运行失败')
  } finally {
    ingesting.value = false
  }
}

const StatCard = (props: { label: string; value: number; icon: string }) =>
  h('div', { class: 'bg-white rounded-xl border border-slate-200 p-4' }, [
    h('div', { class: 'text-2xl mb-1' }, props.icon),
    h('div', { class: 'text-2xl font-bold text-slate-900' }, String(props.value)),
    h('div', { class: 'text-xs text-slate-500' }, props.label),
  ])

onMounted(load)
</script>