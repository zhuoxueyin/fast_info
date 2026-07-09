<template>
  <div>
    <!-- 搜索框 -->
    <div class="flex items-center gap-2 mb-4">
      <button class="p-1 -ml-1" @click="goBack">
        <ChevronLeft :size="22" />
      </button>
      <div class="relative flex-1">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
          <Search :size="16" />
        </span>
        <input
          v-model="q"
          ref="inputRef"
          type="text"
          placeholder="搜索关键词..."
          class="w-full pl-10 pr-10 py-2.5 text-sm rounded-full bg-white border border-slate-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:border-emerald-400 placeholder:text-slate-400"
          @keyup.enter="doSearch"
        />
        <button
          v-if="q"
          class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600"
          @click="q = ''"
        >
          <X :size="14" />
        </button>
      </div>
      <button
        class="text-sm font-medium text-emerald-600 px-2"
        :disabled="!q.trim() || loading"
        @click="doSearch"
      >
        搜索
      </button>
    </div>

    <!-- 搜索建议 / 历史 -->
    <div v-if="!hasSearched" class="space-y-4">
      <div v-if="history.length">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-xs font-medium text-slate-500 flex items-center gap-1">
            <History :size="12" />
            最近搜索
          </h3>
          <button class="text-[10px] text-slate-400" @click="clearHistory">清空</button>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="h in history"
            :key="h"
            class="text-xs px-3 py-1 rounded-full bg-white border border-slate-200 text-slate-700 active:scale-95"
            @click="quickSearch(h)"
          >{{ h }}</button>
        </div>
      </div>

      <div v-if="hotKeywords.length">
        <h3 class="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1">
          <Flame :size="12" class="text-orange-500" />
          热门搜索
        </h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="(k, idx) in hotKeywords"
            :key="k"
            class="text-xs px-3 py-1 rounded-full bg-white border border-slate-200 text-slate-700 active:scale-95"
            :class="idx < 3 ? 'border-orange-200 bg-orange-50/50' : ''"
            @click="quickSearch(k)"
          >{{ k }}</button>
        </div>
      </div>
    </div>

    <!-- 搜索结果 -->
    <div v-else>
      <div class="text-xs text-slate-500 mb-2">
        {{ loading ? '搜索中...' : `共 ${results.length} 条结果` }}
      </div>
      <div v-if="loading && !results.length" class="text-center text-slate-400 py-8 text-sm">搜索中…</div>
      <div v-else-if="!results.length" class="text-center text-slate-400 py-8 text-sm">没有找到相关内容</div>
      <div v-else class="space-y-2">
        <router-link
          v-for="item in results"
          :key="item.id"
          :to="`/m/items/${item.id}`"
          class="block bg-white rounded-xl border border-slate-200 p-3 active:scale-[0.99] transition"
        >
          <div class="flex items-center gap-1.5 mb-1">
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
              {{ item.category_l1 || '其他' }}
            </span>
            <span class="text-[10px] text-slate-400 truncate">{{ sourceLabel(item.source) }}</span>
          </div>
          <h3 class="text-sm font-medium text-slate-900 leading-snug line-clamp-2 mb-1" v-html="highlight(item.title)"></h3>
          <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed">{{ item.summary }}</p>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, X, ChevronLeft, History, Flame } from 'lucide-vue-next'
import { api } from '@/lib/api'

const route = useRoute()
const router = useRouter()

const q = ref(String(route.query.q || ''))
const results = ref<any[]>([])
const loading = ref(false)
const hasSearched = ref(false)
const history = ref<string[]>([])
const inputRef = ref<HTMLInputElement>()

const hotKeywords = ['AI', '大模型', '小米', '苹果', '世界杯', '世界杯', '新能源']

function sourceLabel(src: string) {
  const m: Record<string, string> = {
    cls: '财联社', leiphone: '雷锋网', ithome: 'IT之家', sina: '新浪',
    qq: '腾讯', kr36: '36氪', huxiu: '虎嗅', sohu: '搜狐',
  }
  return m[src] || src
}

function highlight(text: string): string {
  if (!q.value) return text
  const re = new RegExp(`(${q.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.replace(re, '<mark class="bg-yellow-200 text-slate-900 px-0.5 rounded">$1</mark>')
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/m')
}

function saveHistory(term: string) {
  if (!term) return
  history.value = [term, ...history.value.filter(h => h !== term)].slice(0, 10)
  try { localStorage.setItem('m_search_history', JSON.stringify(history.value)) } catch {}
}

function loadHistory() {
  try {
    const h = localStorage.getItem('m_search_history')
    if (h) history.value = JSON.parse(h)
  } catch {}
}

function clearHistory() {
  history.value = []
  try { localStorage.removeItem('m_search_history') } catch {}
}

function quickSearch(term: string) {
  q.value = term
  doSearch()
}

async function doSearch() {
  const term = q.value.trim()
  if (!term) return
  loading.value = true
  hasSearched.value = true
  saveHistory(term)
  try {
    const r = await api<any>('/search', { query: { q: term, limit: 30 } })
    results.value = r?.items || []
  } catch {
    results.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  loadHistory()
  // URL 里有 q 直接搜
  if (q.value) {
    await doSearch()
  }
  // 自动聚焦
  await nextTick()
  inputRef.value?.focus()
})
</script>