<template>
  <div>
    <div class="mb-4">
      <h1 class="text-2xl font-bold text-slate-900">搜索结果</h1>
      <p class="text-sm text-slate-500 mt-1">
        关键词: <span class="text-slate-700 font-medium">{{ q }}</span> · 命中 {{ total }} 条
      </p>
    </div>
    <div v-if="items.length" class="space-y-4">
      <ItemCard v-for="it in items" :key="it.id" :item="it" />
    </div>
    <n-empty v-else description="无结果,试试其他关键词" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NEmpty } from 'naive-ui'
import { api } from '@/lib/api'
import type { Item, SearchResponse } from '@/types/api'
import ItemCard from '@/components/ItemCard.vue'

const route = useRoute()
const q = ref((route.query.q as string) || '')
const items = ref<Item[]>([])
const total = ref(0)

async function load() {
  if (!q.value) return
  try {
    const r = await api<SearchResponse>('/search', { query: { q: q.value, limit: 30 } })
    items.value = r.items
    total.value = r.total
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)
watch(() => route.query.q, (v) => {
  q.value = (v as string) || ''
  load()
})
</script>