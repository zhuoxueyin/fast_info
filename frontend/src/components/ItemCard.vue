<template>
  <router-link
    :to="`/items/${item.id}`"
    class="block bg-white rounded-lg border border-slate-200 hover:border-emerald-300 hover:shadow-md transition p-4 cursor-pointer h-full flex flex-col"
  >
    <div class="flex items-start justify-between mb-2 gap-2">
      <span class="inline-block px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-700 flex-shrink-0 break-words">
        {{ displayCategory }}
      </span>
      <span v-if="item.relevance !== undefined" class="text-xs text-orange-500 font-medium flex-shrink-0">
        🔥 {{ item.relevance.toFixed(1) }}
      </span>
    </div>
    <h3 :class="compact ? 'text-sm' : 'text-base'" class="font-semibold text-slate-900 leading-snug mb-2 line-clamp-2 break-words" :title="item.title">
      {{ item.title }}
    </h3>
    <p v-if="!compact && item.summary" class="text-sm text-slate-600 leading-relaxed line-clamp-2 mb-3 break-words" :title="item.summary">
      {{ item.summary }}
    </p>
    <div class="flex items-center justify-between text-xs text-slate-500 mt-auto">
      <span>{{ sourceLabel }}</span>
      <span>{{ timeLabel }}</span>
    </div>
  </router-link>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { Item } from '@/types/api'

const props = defineProps<{ item: Item; compact?: boolean }>()

const SOURCE_MAP: Record<string, string> = {
  ithome: 'IT之家', '36kr': '36氪', sspai: '少数派', infoq: 'InfoQ',
  qbitai: '量子位', ifanr: '爱范儿', huxiu: '虎嗅', douban: '豆瓣',
}

const displayCategory = computed(() => props.item.category_l1 || props.item.category || '其他')
const sourceLabel = computed(() => SOURCE_MAP[props.item.source] || props.item.source)
const timeLabel = computed(() => {
  const t = props.item.published_at || props.item.fetched_at
  if (!t) return ''
  const d = dayjs(t)
  const now = dayjs()
  const diffMin = now.diff(d, 'minute')
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.format('MM-DD HH:mm')
})
</script>
