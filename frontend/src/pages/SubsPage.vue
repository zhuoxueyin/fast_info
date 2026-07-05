<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-slate-900">📡 我的订阅 ({{ subs.length }})</h1>
      <div class="flex gap-2">
        <n-button @click="$router.push('/me')">← 个人中心</n-button>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-6">
      <n-data-table
        v-if="subs.length"
        :columns="cols"
        :data="subs"
        :pagination="false"
        :bordered="false"
      />
      <n-empty v-else description="还没有订阅,去创建一个吧">
        <template #extra>
          <n-button type="primary" @click="$router.push('/subs/new')">新建订阅</n-button>
        </template>
      </n-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NDataTable, NEmpty, useMessage, NPopconfirm, NSwitch, NTag, type DataTableColumns } from 'naive-ui'
import { useAuthStore } from '@/store/auth'
import { api } from '@/lib/api'
import type { Subscription } from '@/types/api'

const router = useRouter()
const auth = useAuthStore()
const msg = useMessage()
const subs = ref<Subscription[]>([])

const cols: DataTableColumns<Subscription> = [
  { title: '标题', key: 'title', width: 160 },
  { title: 'NL', key: 'nl_query', ellipsis: { tooltip: true }, width: 180 },
  {
    title: '关键词', key: 'keywords', width: 180,
    render: (row: Subscription) => h('div', { class: 'flex flex-wrap gap-1' },
      row.keywords.slice(0, 4).map(k => h(NTag, { type: 'success', size: 'small' }, () => k))),
  },
  {
    title: '类目', key: 'categories_l1',
    render: (row: Subscription) => h('div', { class: 'flex flex-wrap gap-1' },
      (row.categories_l1 || []).map(c => h(NTag, { size: 'small', type: 'info' }, () => c))),
  },
  {
    title: '频率', key: 'freq', width: 90,
    render: (row: Subscription) => row.interval_min
      ? `每 ${row.interval_min}m`
      : (row.cron_expr || '0 9 * * *'),
  },
  {
    title: '渠道', key: 'channels', width: 140,
    render: (row: Subscription) => h('div', { class: 'flex flex-wrap gap-1' },
      (row.channels || ['inbox']).map(c => h(NTag, { size: 'small' }, () => chLabel(c)))),
  },
  {
    title: '启用', key: 'is_active', width: 80,
    render: (row: Subscription) => h(NSwitch, {
      value: row.is_active,
      onUpdateValue: (v: boolean) => toggleActive(row, v),
    }),
  },
  {
    title: '操作', key: 'actions', width: 260,
    render: (row: Subscription) => h('div', { class: 'flex gap-2' }, [
      h(NButton, { size: 'small', onClick: () => runSub(row.id) }, () => '▶ 立即推送'),
      h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => goEdit(row.id) }, () => '✏️ 修改'),
      h(NPopconfirm, {
        onPositiveClick: () => deleteSub(row.id),
      }, {
        trigger: () => h(NButton, { size: 'small', type: 'error' }, () => '删除'),
        default: () => '确定删除这个订阅?',
      }),
    ]),
  },
]

function chLabel(c: string): string {
  return { inbox: '站内', email: '邮件', feishu: '飞书', wechat: '企微', webhook: 'Webhook' }[c] || c
}

async function load() {
  try {
    const r = await api<{ items: Subscription[] }>('/subs')
    subs.value = r.items
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

async function runSub(id: string) {
  try {
    const r = await api<{ delivered: number; matched: number; scanned: number }>(`/subs/${id}/run`, { method: 'POST' })
    msg.success(`扫描 ${r.scanned} / 命中 ${r.matched} / 推送 ${r.delivered}`)
    load()
  } catch (e: any) {
    const detail = e?.data?.detail || e?.message || '运行失败'
    msg.error(typeof detail === 'string' ? detail : '运行失败，请检查后端日志')
  }
}

function goEdit(id: string) {
  router.push(`/subs/edit/${id}`)
}

async function deleteSub(id: string) {
  try {
    await api(`/subs/${id}`, { method: 'DELETE' })
    msg.success('已删除')
    load()
  } catch (e: any) {
    msg.error(e?.data?.detail || '删除失败')
  }
}

async function toggleActive(row: Subscription, v: boolean) {
  try {
    await api(`/subs/${row.id}`, { method: 'PATCH', body: { is_active: v } })
    row.is_active = v
    msg.success(v ? '已启用' : '已暂停')
  } catch (e: any) {
    msg.error(e?.data?.detail || '更新失败')
  }
}

onMounted(() => {
  load()
})
</script>
