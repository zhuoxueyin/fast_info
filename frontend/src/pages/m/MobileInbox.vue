<template>
  <div class="pb-2">
    <div class="mb-4">
      <h1 class="text-xl font-bold text-slate-900">晨报信封</h1>
      <p class="text-[11px] text-slate-400 mt-0.5">已推送简报的回看台 · 按频道归组</p>
    </div>

    <div v-if="loading" class="text-center text-slate-400 py-12 text-sm">拆信中…</div>
    <div
      v-else-if="!envelopes.length"
      class="rounded-3xl bg-white border border-dashed border-slate-300 p-10 text-center"
    >
      <div class="text-3xl mb-2">✉️</div>
      <p class="text-sm text-slate-600 font-medium">还没有推送</p>
      <p class="text-xs text-slate-400 mt-1 mb-4">订阅频道跑起来后，推送会出现在这里</p>
      <router-link to="/m/channels" class="text-xs font-semibold text-emerald-600">去频道 →</router-link>
    </div>

    <div v-else class="space-y-3">
      <article
        v-for="env in envelopes"
        :key="env.key"
        class="rounded-2xl overflow-hidden bg-white border border-slate-200/80 shadow-sm"
      >
        <!-- 信封头 -->
        <button
          class="w-full flex items-center gap-3 p-3.5 text-left active:bg-slate-50"
          @click="env.open = !env.open"
        >
          <span
            class="w-11 h-11 rounded-xl flex items-center justify-center text-lg flex-shrink-0 shadow-inner"
            :style="{ background: env.tone }"
          >
            ✉️
          </span>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-semibold text-slate-900 line-clamp-1">{{ env.title }}</div>
            <div class="text-[11px] text-slate-400 mt-0.5">
              {{ env.count }} 条 · {{ env.timeLabel }}
            </div>
          </div>
          <ChevronDown
            :size="16"
            class="text-slate-300 transition-transform flex-shrink-0"
            :class="{ 'rotate-180': env.open }"
          />
        </button>

        <!-- 展开卡片 -->
        <div v-if="env.open" class="border-t border-slate-100 px-3 pb-3 space-y-2">
          <router-link
            v-for="row in env.items"
            :key="row.item.id + (row.delivered_at || '')"
            :to="`/m/items/${row.item.id}`"
            class="block pt-2.5 active:opacity-80"
            @click="prepFeed(env)"
          >
            <div class="text-[13px] font-medium text-slate-800 leading-snug line-clamp-2">
              {{ row.item.title }}
            </div>
            <p v-if="oneLiner(row.item.summary)" class="text-[11px] text-slate-500 mt-1 line-clamp-2">
              {{ oneLiner(row.item.summary, 48) }}
            </p>
            <div class="text-[10px] text-slate-400 mt-1 flex justify-between">
              <span>{{ row.item.category_l1 || row.item.category || '' }}</span>
              <span>{{ formatRelativeTime(row.delivered_at) }}</span>
            </div>
          </router-link>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { InboxResponse, InboxItem } from '@/types/api'
import {
  coverTone,
  formatRelativeTime,
  oneLiner,
  saveFeedIds,
} from '@/lib/mobile-ui'

type Envelope = {
  key: string
  title: string
  count: number
  timeLabel: string
  tone: string
  open: boolean
  items: InboxItem[]
}

const loading = ref(true)
const envelopes = ref<Envelope[]>([])

function prepFeed(env: Envelope) {
  saveFeedIds(env.items.map((r) => r.item.id))
}

onMounted(async () => {
  try {
    const r = await api<InboxResponse>('/inbox', { query: { sort: 'time', page_size: 80 } })
    const items = r.items || []
    // 按 subscription_title + 日期 归组成信封
    const map = new Map<string, InboxItem[]>()
    for (const row of items) {
      const day = (row.delivered_at || '').slice(0, 10) || 'unknown'
      const title = row.subscription_title || '未命名频道'
      const key = `${title}__${day}`
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(row)
    }
    envelopes.value = Array.from(map.entries()).map(([key, rows], idx) => {
      const title = key.split('__')[0]
      const latest = rows[0]?.delivered_at
      return {
        key,
        title,
        count: rows.length,
        timeLabel: formatRelativeTime(latest) || '—',
        tone: coverTone(key + String(idx)),
        open: idx === 0,
        items: rows,
      }
    })
  } finally {
    loading.value = false
  }
})
</script>
