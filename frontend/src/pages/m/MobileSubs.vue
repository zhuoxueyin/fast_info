<template>
  <div>
    <h1 class="text-xl font-bold mb-3">📡 我的订阅 ({{ subs.length }})</h1>
    <div v-if="loading" class="text-center text-slate-400 py-8">加载中…</div>
    <div v-else-if="!subs.length" class="text-center text-slate-400 py-8">还没有订阅</div>
    <div v-else class="space-y-2">
      <div
        v-for="s in subs"
        :key="s.id"
        class="bg-white rounded-lg border p-3"
      >
        <div class="flex items-center justify-between">
          <span class="font-medium text-slate-900">{{ s.title }}</span>
          <span class="text-xs text-slate-500">{{ s.is_active ? '运行中' : '已暂停' }}</span>
        </div>
        <div class="text-xs text-slate-500 mt-1 line-clamp-1">{{ s.nl_query }}</div>
        <div class="flex items-center gap-2 mt-2 text-xs text-slate-500">
          <span>每 {{ s.interval_min || 30 }} 分钟</span>
          <span>·</span>
          <span>最多 {{ s.max_items }} 条</span>
        </div>
        <div class="flex gap-1 mt-2 flex-wrap">
          <span v-for="kw in s.keywords.slice(0,3)" :key="kw" class="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">{{ kw }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/lib/api'
import type { Subscription } from '@/types/api'

const subs = ref<Subscription[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const r = await api<{ items: Subscription[] }>('/subs')
    subs.value = r.items
  } finally {
    loading.value = false
  }
})
</script>