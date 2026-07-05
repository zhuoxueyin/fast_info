<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">🔧 管理后台</h1>
      <AdminTabs class="ml-auto" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { NEmpty, useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api } from '@/lib/api'
import type { Stats } from '@/types/api'
import AdminTabs from '@/components/AdminTabs.vue'

use([CanvasRenderer, BarChart, PieChart, TooltipComponent, LegendComponent, GridComponent, TitleComponent])

const msg = useMessage()
const stats = ref<Stats | null>(null)

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

const StatCard = (props: { label: string; value: number; icon: string }) =>
  h('div', { class: 'bg-white rounded-xl border border-slate-200 p-4' }, [
    h('div', { class: 'text-2xl mb-1' }, props.icon),
    h('div', { class: 'text-2xl font-bold text-slate-900' }, String(props.value)),
    h('div', { class: 'text-xs text-slate-500' }, props.label),
  ])

onMounted(load)
</script>
