<template>
  <div>
    <h1 class="text-xl font-bold mb-3">📥 推送 ({{ items.length }})</h1>
    <div v-if="loading" class="text-center text-slate-400 py-8">加载中…</div>
    <div v-else-if="!items.length" class="text-center text-slate-400 py-8">还没有推送</div>
    <div v-else class="space-y-2">
      <router-link
        v-for="(r, i) in items"
        :key="i"
        :to="`/m/items/${r.item.id}`"
        class="block bg-white rounded-lg border p-3"
      >
        <div class="text-xs text-slate-500 mb-1">{{ r.subscription_title || '-' }}</div>
        <div class="font-medium text-slate-900 text-sm line-clamp-2 mb-1">{{ r.item.title }}</div>
        <div class="flex items-center justify-between text-xs text-slate-500">
          <span>{{ r.item.category || '' }}</span>
          <span>{{ formatTime(r.delivered_at) }}</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { api } from '@/lib/api'
import type { InboxResponse } from '@/types/api'

const items = ref<any[]>([])
const loading = ref(true)
const formatTime = (t?: string) => t ? dayjs(t).format('MM-DD HH:mm') : ''

onMounted(async () => {
  try {
    const r = await api<InboxResponse>('/inbox', { query: { sort: 'time', page_size: 50 } })
    items.value = r.items
  } finally {
    loading.value = false
  }
})
</script>