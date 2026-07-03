<template>
  <div v-if="item" class="bg-white rounded-lg border p-4">
    <span class="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">{{ item.category || '其他' }}</span>
    <h1 class="text-lg font-bold text-slate-900 mt-2 leading-snug">{{ item.title }}</h1>
    <div class="text-xs text-slate-500 mt-1 mb-3">{{ sourceLabel(item.source) }} · {{ timeLabel }}</div>
    <p v-if="item.summary" class="text-sm text-slate-700 leading-relaxed">{{ item.summary }}</p>
    <ul v-if="item.key_points?.length" class="mt-3 list-disc pl-5 text-sm text-slate-700 space-y-1">
      <li v-for="(p, i) in item.key_points" :key="i">{{ p }}</li>
    </ul>
    <a :href="item.url" target="_blank" class="block text-center text-emerald-600 text-sm mt-4 py-2 border-t">查看原文 →</a>
  </div>
  <div v-else-if="!loading" class="text-center text-slate-400 py-12">文章不存在</div>
  <div v-else class="text-center text-slate-400 py-12">加载中…</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { api } from '@/lib/api'
import type { Item } from '@/types/api'

const route = useRoute()
const item = ref<Item | null>(null)
const loading = ref(true)
const SRC: Record<string, string> = { ithome: 'IT之家', '36kr': '36氪', qbitai: '量子位', sspai: '少数派', infoq: 'InfoQ', huxiu: '虎嗅', ifanr: '爱范儿' }
const sourceLabel = (s: string) => SRC[s] || s
const timeLabel = computed(() => {
  if (!item.value) return ''
  const t = item.value.published_at || item.value.fetched_at
  return t ? dayjs(t).format('MM-DD HH:mm') : ''
})

onMounted(async () => {
  try {
    const r = await api<Item[]>('/items', { query: { ids: route.params.id } })
    if (r.length) item.value = r[0]
  } finally {
    loading.value = false
  }
})
</script>