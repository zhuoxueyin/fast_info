<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">🔧 管理后台</h1>
      <AdminTabs class="ml-auto" />
    </div>

    <div v-if="loading && !stats" class="text-sm text-slate-500 mb-6">加载中…</div>

    <div v-if="stats" class="grid gap-4 md:grid-cols-4 mb-6">
      <StatCard label="总 items" :value="stats.total_items" icon="📰" />
      <StatCard label="总用户" :value="stats.total_users" icon="👥" />
      <StatCard label="总订阅" :value="stats.total_subscriptions" icon="📡" />
      <StatCard label="总推送" :value="stats.total_delivered" icon="📬" />
    </div>

    <div class="grid lg:grid-cols-2 gap-6">
      <section class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-lg font-semibold mb-4">📊 来源分布</h2>
        <component
          v-if="VChart && sourceRows.length"
          :is="VChart"
          :option="sourceChart"
          style="height: 280px"
          autoresize
        />
        <div v-else-if="sourceRows.length" class="space-y-2">
          <div v-for="row in sourceRows" :key="row.name" class="flex items-center gap-2 text-sm">
            <span class="w-28 truncate text-slate-600" :title="row.name">{{ row.name }}</span>
            <div class="flex-1 h-2 bg-slate-100 rounded overflow-hidden">
              <div class="h-full bg-emerald-500 rounded" :style="{ width: row.pct + '%' }" />
            </div>
            <span class="w-10 text-right text-slate-500">{{ row.value }}</span>
          </div>
        </div>
        <n-empty v-else />
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-lg font-semibold mb-4">🏷 类目分布 Top 15</h2>
        <component
          v-if="VChart && categoryRows.length"
          :is="VChart"
          :option="categoryChart"
          style="height: 280px"
          autoresize
        />
        <div v-else-if="categoryRows.length" class="space-y-2">
          <div v-for="row in categoryRows" :key="row.name" class="flex items-center gap-2 text-sm">
            <span class="w-28 truncate text-slate-600" :title="row.name">{{ row.name }}</span>
            <div class="flex-1 h-2 bg-slate-100 rounded overflow-hidden">
              <div class="h-full bg-teal-500 rounded" :style="{ width: row.pct + '%' }" />
            </div>
            <span class="w-10 text-right text-slate-500">{{ row.value }}</span>
          </div>
        </div>
        <n-empty v-else />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h, shallowRef, type Component } from 'vue'
import { NEmpty, useMessage } from 'naive-ui'
import { api } from '@/lib/api'
import type { Stats } from '@/types/api'
import AdminTabs from '@/components/AdminTabs.vue'

const msg = useMessage()
const stats = ref<Stats | null>(null)
const loading = ref(false)
/** 懒加载 vue-echarts,避免 AdminHome 主 chunk 膨胀到 500KB 导致弱网动态 import 失败 */
const VChart = shallowRef<Component | null>(null)

const sourceRows = computed(() => {
  const rows = stats.value?.by_source || []
  const max = Math.max(1, ...rows.map(r => r.count || 0))
  return rows.map(r => ({
    name: r._id || '未知',
    value: r.count || 0,
    pct: Math.round(((r.count || 0) / max) * 100),
  }))
})

const categoryRows = computed(() => {
  const rows = (stats.value?.by_category || []).slice(0, 15)
  const max = Math.max(1, ...rows.map(r => r.count || 0))
  return rows.map(r => ({
    name: r._id || '其他',
    value: r.count || 0,
    pct: Math.round(((r.count || 0) / max) * 100),
  }))
})

const sourceChart = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  xAxis: {
    type: 'category',
    data: (stats.value?.by_source || []).map(s => s._id),
    axisLabel: { rotate: 30 },
  },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar',
    data: (stats.value?.by_source || []).map(s => s.count),
    itemStyle: { color: '#10B981' },
  }],
}))

const categoryChart = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: (stats.value?.by_category || []).slice(0, 15).map(c => ({
      name: c._id || '其他',
      value: c.count,
    })),
  }],
}))

async function loadStats() {
  loading.value = true
  try {
    stats.value = await api<Stats>('/admin/stats')
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadCharts() {
  try {
    const [
      { use },
      { CanvasRenderer },
      { BarChart, PieChart },
      { TooltipComponent, LegendComponent, GridComponent, TitleComponent },
      mod,
    ] = await Promise.all([
      import('echarts/core'),
      import('echarts/renderers'),
      import('echarts/charts'),
      import('echarts/components'),
      import('vue-echarts'),
    ])
    use([
      CanvasRenderer,
      BarChart,
      PieChart,
      TooltipComponent,
      LegendComponent,
      GridComponent,
      TitleComponent,
    ])
    VChart.value = mod.default
  } catch {
    // 图表失败不阻塞管理页;上方 CSS 条形图兜底
    msg.warning('图表组件加载失败,已切换为简版展示')
  }
}

const StatCard = (props: { label: string; value: number; icon: string }) =>
  h('div', { class: 'bg-white rounded-xl border border-slate-200 p-4' }, [
    h('div', { class: 'text-2xl mb-1' }, props.icon),
    h('div', { class: 'text-2xl font-bold text-slate-900' }, String(props.value)),
    h('div', { class: 'text-xs text-slate-500' }, props.label),
  ])

onMounted(() => {
  loadStats()
  loadCharts()
})
</script>
