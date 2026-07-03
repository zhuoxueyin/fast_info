<template>
  <div class="grid lg:grid-cols-[1fr_320px] gap-8">
    <article v-if="item" class="bg-white rounded-xl border border-slate-200 p-8">
      <div class="flex items-center gap-3 text-xs text-slate-500 mb-3 flex-wrap">
        <span class="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">{{ item.category_l1 || item.category || '其他' }}</span>
        <span v-if="item.category && item.category !== item.category_l1" class="px-2 py-0.5 rounded bg-slate-100 text-slate-600">{{ item.category }}</span>
        <span>来源: {{ sourceLabel }}</span>
        <span v-if="item.summary_model" class="text-slate-400">模型: {{ item.summary_model }}</span>
        <span>{{ timeLabel }}</span>
      </div>
      <h1 class="text-3xl font-bold text-slate-900 leading-tight mb-6">{{ item.title }}</h1>

      <div v-if="item.summary" class="prose prose-slate max-w-none text-base leading-relaxed text-slate-700 mb-6 whitespace-pre-wrap">
        {{ item.summary }}
      </div>
      <div v-else class="mb-6 p-4 bg-amber-50 border border-amber-100 rounded-lg text-sm text-amber-700">
        📝 暂无AI摘要，请点击"查看原文"阅读完整内容。
      </div>

      <div v-if="item.key_points?.length" class="mb-6">
        <h2 class="text-sm font-semibold text-slate-900 mb-3">📌 关键点</h2>
        <ul class="space-y-2 pl-5 list-disc text-slate-700">
          <li v-for="(p, i) in item.key_points" :key="i">{{ p }}</li>
        </ul>
      </div>

      <div v-if="item.tags?.length" class="flex flex-wrap gap-2 mb-6">
        <span v-for="t in item.tags" :key="t" class="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">#{{ t }}</span>
      </div>

      <a :href="item.url" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-emerald-600 hover:underline text-sm">
        查看原文 →
      </a>
    </article>
    <n-empty v-else-if="loaded" description="文章不存在" />
    <n-spin v-else />

    <aside v-if="item" class="space-y-4">
      <h2 class="text-sm font-semibold text-slate-900">同类目热门</h2>
      <div v-if="related.length" class="space-y-3">
        <router-link
          v-for="r in related"
          :key="r.id"
          :to="`/items/${r.id}`"
          class="block bg-white rounded-lg border border-slate-200 hover:border-emerald-300 hover:shadow-md transition p-3 cursor-pointer"
        >
          <div class="flex items-start justify-between gap-2 mb-1">
            <span class="inline-block px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-700 flex-shrink-0">
              {{ r.category_l1 || r.category || '其他' }}
            </span>
            <span v-if="r.relevance !== undefined" class="text-xs text-orange-500 font-medium flex-shrink-0">
              🔥 {{ r.relevance.toFixed(1) }}
            </span>
          </div>
          <div class="text-sm font-medium text-slate-900 leading-snug line-clamp-2 mb-1">{{ r.title }}</div>
          <div class="flex items-center justify-between text-xs text-slate-500">
            <span>{{ sourceName(r.source) }}</span>
            <span>{{ relTime(r) }}</span>
          </div>
        </router-link>
      </div>
      <n-empty v-else size="small" description="暂无同类目" />
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NEmpty, NSpin } from 'naive-ui'
import dayjs from 'dayjs'
import { api } from '@/lib/api'
import type { Item, HotResponse } from '@/types/api'

const route = useRoute()
const id = computed(() => route.params.id as string)
const item = ref<Item | null>(null)
const related = ref<Item[]>([])
const loaded = ref(false)

const SOURCE_MAP: Record<string, string> = {
  ithome: 'IT之家', '36kr': '36氪', sspai: '少数派', infoq: 'InfoQ',
  qbitai: '量子位', ifanr: '爱范儿', huxiu: '虎嗅', douban: '豆瓣',
}
const sourceName = (s: string) => SOURCE_MAP[s] || s
const sourceLabel = computed(() => item.value ? sourceName(item.value.source) : '')
const timeLabel = computed(() => {
  if (!item.value) return ''
  const t = item.value.published_at || item.value.fetched_at
  return t ? dayjs(t).format('YYYY-MM-DD HH:mm') : ''
})
const relTime = (r: Item) => {
  const t = r.published_at || r.fetched_at
  if (!t) return ''
  const diffMin = dayjs().diff(dayjs(t), 'minute')
  if (diffMin < 60) return `${diffMin}分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}小时前`
  return dayjs(t).format('MM-DD HH:mm')
}

async function loadItem() {
  loaded.value = false
  item.value = null
  related.value = []
  try {
    const r = await api<Item[]>(`/items`, { query: { ids: id.value } })
    if (r.length) {
      item.value = r[0]
      const cat = item.value.category_l1 || item.value.category
      if (cat) {
        try {
          const rel = await api<HotResponse>('/hot', { query: { limit: 8, hours: 168, category: cat, threshold: 0 } })
          related.value = rel.items.filter(x => x.id !== id.value).slice(0, 6)
        } catch {}
      }
    }
  } finally {
    loaded.value = true
  }
}

onMounted(() => {
  loadItem()
})

watch(() => route.params.id, () => {
  if (route.name === 'item-detail') {
    loadItem()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
})
</script>
