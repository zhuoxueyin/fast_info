<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-slate-900">📥 我的推送 ({{ total }})</h1>
      <n-button @click="$router.push('/me')">← 个人中心</n-button>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex gap-3 items-center">
      <n-input v-model:value="filterSub" placeholder="订阅名..." clearable class="!w-56" />
      <n-select v-model:value="filterCategory" :options="categoryOpts" placeholder="类目" clearable class="!w-40" />
      <n-select v-model:value="sort" :options="sortOpts" class="!w-32" />
      <n-button @click="load">🔄 刷新</n-button>
    </div>

    <n-data-table
      v-if="rows.length"
      :columns="cols"
      :data="rows"
      :pagination="{ pageSize: 20 }"
      :bordered="false"
      :row-key="(r: any) => r.item.id"
      :row-props="() => ({ style: 'height: 56px' })"
      :single-line="false"
    />
    <n-empty v-else description="还没有推送" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { NInput, NSelect, NButton, NDataTable, NEmpty, NTag, type DataTableColumns } from 'naive-ui'
import dayjs from 'dayjs'
import { api } from '@/lib/api'
import type { InboxResponse, InboxItem } from '@/types/api'

const total = ref(0)
const items = ref<InboxItem[]>([])
const filterSub = ref('')
const filterCategory = ref<string | null>(null)
const sort = ref<'relevance' | 'time'>('relevance')
const categoryOpts = ref<{ label: string; value: string }[]>([])

const sortOpts = [
  { label: '按热度', value: 'relevance' },
  { label: '按时间', value: 'time' },
]

const rows = computed(() => items.value)

const cols: DataTableColumns<InboxItem> = [
  { title: '订阅', key: 'subscription_title', width: 100, render: (r: InboxItem) => h('span', { class: 'text-xs text-slate-600' }, r.subscription_title || '-') },
  {
    title: '标题', key: 'item.title', ellipsis: { tooltip: true },
    render: (r: InboxItem) => h('router-link', {
      to: `/items/${r.item.id}`,
      class: 'text-slate-900 hover:text-emerald-600',
      style: 'display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4;',
    }, () => r.item.title),
  },
  { title: '类目', key: 'item.category_l1', width: 70, render: (r: InboxItem) => h(NTag, { size: 'small', type: 'success' }, () => r.item.category_l1 || r.item.category || '-') },
  {
    title: '相关度', key: 'item.relevance', width: 70, align: 'right',
    render: (r: InboxItem) => r.item.relevance !== undefined ? r.item.relevance.toFixed(1) : '-',
  },
  {
    title: '推送时间', key: 'delivered_at', width: 130,
    render: (r: InboxItem) => r.delivered_at ? dayjs(r.delivered_at).format('MM-DD HH:mm') : '-',
  },
]

async function load() {
  try {
    const r = await api<InboxResponse>('/inbox', {
      query: {
        sort: sort.value,
        subscription: filterSub.value || undefined,
        category: filterCategory.value || undefined,
        page_size: 100,
      },
    })
    items.value = r.items
    total.value = r.total
  } catch {}
}

onMounted(async () => {
  try {
    const cats = await api<{ categories: string[] }>('/categories')
    categoryOpts.value = cats.categories.map(c => ({ label: c, value: c }))
  } catch {}
  load()
})
</script>