<template>
  <div>
    <h1 class="text-xl font-bold mb-3">🔥 热门</h1>
    <div v-if="loading" class="text-center text-slate-400 py-8">加载中…</div>
    <div v-else class="space-y-3">
      <router-link
        v-for="(it, i) in items"
        :key="it.id"
        :to="`/m/items/${it.id}`"
        class="block bg-white rounded-lg border border-slate-200 p-3"
      >
        <div class="flex items-start gap-2 mb-1">
          <span class="font-bold text-emerald-600 text-sm w-6">{{ i + 1 }}</span>
          <span class="text-sm font-medium text-slate-900 line-clamp-2 flex-1">{{ it.title }}</span>
        </div>
        <div class="flex items-center gap-2 text-xs text-slate-500 pl-8">
          <span>{{ it.category || '' }}</span>
          <span>·</span>
          <span>{{ sourceLabel(it.source) }}</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/lib/api'
import type { Item, HotResponse } from '@/types/api'

const items = ref<Item[]>([])
const loading = ref(true)
const SRC: Record<string, string> = { ithome: 'IT之家', '36kr': '36氪', qbitai: '量子位', sspai: '少数派', infoq: 'InfoQ', huxiu: '虎嗅', ifanr: '爱范儿', wallstreetcn: '华尔街见闻', cls: '财联社', hupu: '虎扑', dongqiudi: '懂球帝', bilibili: 'B站', douban: '豆瓣', autohome: '汽车之家' }
const sourceLabel = (s: string) => SRC[s] || s

onMounted(async () => {
  try {
    const r = await api<HotResponse>('/hot', { query: { limit: 30, threshold: 0 } })
    items.value = r.items
  } finally {
    loading.value = false
  }
})
</script>