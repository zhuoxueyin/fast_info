<template>
  <div>
    <!-- 顶部搜索框 -->
    <div class="pt-2 pb-3">
      <div class="relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
          <Search :size="16" />
        </span>
        <input
          v-model="q"
          type="text"
          placeholder="搜索资讯 · 关键词 · 话题"
          class="w-full pl-10 pr-4 py-2.5 text-sm rounded-full bg-white border border-slate-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:border-emerald-400 placeholder:text-slate-400"
          @keyup.enter="onSearch"
        />
      </div>
    </div>

    <!-- 话题快速入口 -->
    <div class="bg-white border border-slate-200 rounded-xl p-3 mb-4">
      <div class="flex items-center gap-1.5 mb-2">
        <span class="inline-flex items-center justify-center w-6 h-6 rounded bg-gradient-to-br from-purple-400 to-pink-500 text-white">
          <Sparkles :size="13" />
        </span>
        <span class="font-semibold text-sm text-slate-900">今天要关注什么？</span>
      </div>
      <div class="flex gap-2">
        <input
          v-model="topicQ"
          type="text"
          placeholder="输入话题,AI 自动聚合 24h 相关资讯"
          class="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-300"
          :disabled="topicCreating"
          @keyup.enter="createNowTopic"
        />
        <button
          class="px-4 py-2 text-sm rounded-lg bg-emerald-500 text-white font-medium active:scale-95 disabled:opacity-60"
          :disabled="topicCreating"
          @click="createNowTopic"
        >
          {{ topicCreating ? '查询中…' : '查询' }}
        </button>
      </div>
    </div>

    <!-- Banner 分组(横向滚动卡片) -->
    <div v-if="bannerGroups.length" class="mb-5">
      <h2 class="text-sm font-bold text-slate-900 mb-2 flex items-center gap-1.5">
        <span class="inline-block w-1 h-3.5 rounded-full bg-gradient-to-b from-emerald-400 to-teal-500"></span>
        热门话题
      </h2>
      <div class="flex gap-2 overflow-x-auto -mx-4 px-4 pb-2 snap-x snap-mandatory">
        <div
          v-for="group in bannerGroups"
          :key="group.category"
          class="flex-shrink-0 w-44 rounded-xl p-3 text-white shadow-sm snap-start"
          :style="{ background: PALETTE[group.category] || PALETTE['其他'] }"
          @click="selectL1(group.category)"
        >
          <div class="flex items-center justify-between mb-1.5">
            <div class="text-xs font-semibold">{{ group.category }}</div>
            <component :is="l1Icon(group.category)" :size="14" />
          </div>
          <ul class="space-y-0.5">
            <li
              v-for="(item, idx) in group.items.slice(0, 3)"
              :key="item.id"
              class="text-[11px] text-white/90 leading-tight line-clamp-1"
            >
              {{ idx + 1 }}. {{ item.title }}
            </li>
            <li v-if="!group.items.length" class="text-[11px] text-white/50">暂无数据</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- L1 横向 tabs -->
    <div class="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4 sticky top-0 bg-slate-50 z-10">
      <button
        v-for="cat in l1Tabs"
        :key="cat"
        class="text-xs px-3 py-1.5 rounded-full whitespace-nowrap transition flex-shrink-0 flex items-center gap-1"
        :class="activeL1 === cat
          ? 'bg-emerald-500 text-white'
          : 'bg-white border border-slate-200 text-slate-700'"
        @click="selectL1(cat)"
      >
        <component :is="l1Icon(cat)" :size="11" />
        {{ cat }}
      </button>
    </div>

    <!-- L2 横向 tabs (次级类目) -->
    <div v-if="availableL2.length && activeL1 !== '全部'" class="flex gap-1.5 overflow-x-auto pb-1 mt-2 -mx-4 px-4">
      <button
        class="text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0"
        :class="!activeL2 ? 'bg-blue-500 text-white' : 'bg-slate-50 border border-slate-200 text-slate-600'"
        @click="activeL2 = ''"
      >全部</button>
      <button
        v-for="l2 in availableL2"
        :key="l2"
        class="text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0"
        :class="activeL2 === l2 ? 'bg-blue-500 text-white' : 'bg-slate-50 border border-slate-200 text-slate-600'"
        @click="activeL2 = l2"
      >{{ l2 }}</button>
    </div>

    <!-- 文章流 -->
    <div class="mt-3 space-y-2">
      <div v-if="loading && !feed.length" class="text-center text-slate-400 py-8 text-sm">加载中…</div>
      <div v-else-if="!feed.length" class="text-center text-slate-400 py-8 text-sm">暂无数据</div>
      <router-link
        v-for="item in feed"
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
        <h3 class="text-sm font-medium text-slate-900 leading-snug line-clamp-2 mb-1">{{ item.title }}</h3>
        <p v-if="item.summary" class="text-xs text-slate-500 line-clamp-2 leading-relaxed">{{ item.summary }}</p>
        <div class="flex items-center justify-between text-[10px] text-slate-400 mt-1.5">
          <span>{{ formatTime(item.published_at || item.fetched_at) }}</span>
          <span v-if="item.relevance" class="text-orange-500 flex items-center gap-0.5">
            <Flame :size="10" />
            {{ fmtRel(item.relevance) }}
          </span>
        </div>
      </router-link>
      <div v-if="feed.length" class="text-center text-slate-400 text-xs py-4">{{ loadingMore ? '加载更多…' : (noMore ? '已加载全部' : '上拉加载更多') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Search, Sparkles, Flame, Cpu, Newspaper, TrendingUp, Briefcase, Car, Trophy, Music, HelpCircle } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()

const q = ref('')
const topicQ = ref('')
const topicCreating = ref(false)

const l1Tabs = ['全部', '科技', 'AI', '财经', '体育', '娱乐', '汽车', '其他']
const activeL1 = ref('全部')
const activeL2 = ref('')
const availableL2 = ref<string[]>([])

const bannerGroups = ref<any[]>([])
const feed = ref<any[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const noMore = ref(false)
const offset = ref(0)
const PAGE_SIZE = 20

const PALETTE: Record<string, string> = {
  科技: 'linear-gradient(135deg, #10B981, #059669)',
  AI: 'linear-gradient(135deg, #8B5CF6, #6366F1)',
  财经: 'linear-gradient(135deg, #F59E0B, #D97706)',
  体育: 'linear-gradient(135deg, #EF4444, #DC2626)',
  娱乐: 'linear-gradient(135deg, #EC4899, #DB2777)',
  汽车: 'linear-gradient(135deg, #3B82F6, #2563EB)',
  其他: 'linear-gradient(135deg, #6B7280, #4B5563)',
}

function l1Icon(name: string) {
  const map: Record<string, any> = {
    科技: Cpu, AI: Sparkles, 财经: TrendingUp, 体育: Trophy,
    娱乐: Music, 汽车: Car, 其他: HelpCircle,
  }
  return map[name] || Newspaper
}

function sourceLabel(src: string) {
  if (!src) return ''
  // 简单的 source_id → 友好名
  const m: Record<string, string> = {
    cls: '财联社', leiphone: '雷锋网', ithome: 'IT之家', sina: '新浪',
    qq: '腾讯', kr36: '36氪', huxiu: '虎嗅', sohu: '搜狐',
    weibo_hot: '微博热搜', tieba: '贴吧', douyin: '抖音',
  }
  return m[src] || src
}

function formatTime(t?: string) {
  if (!t) return ''
  const d = dayjs(t)
  const now = dayjs()
  if (now.diff(d, 'minute') < 60) return `${now.diff(d, 'minute')}分钟前`
  if (now.diff(d, 'hour') < 24) return `${now.diff(d, 'hour')}小时前`
  return d.format('MM-DD')
}

function fmtRel(r: number) {
  return Math.round(r * 100) + ''
}

function onSearch() {
  if (!q.value.trim()) return
  router.push({ path: '/m/search', query: { q: q.value.trim() } })
}

async function createNowTopic() {
  if (!topicQ.value.trim()) return
  topicCreating.value = true
  try {
    const r = await api<any>('/topics/now', {
      method: 'POST',
      body: { query: topicQ.value.trim() },
    })
    if (r?.id) router.push(`/m/topic/${r.id}`)
    else if (r?.tid) router.push(`/m/topic/${r.tid}`)
  } catch (e: any) {
    alert(e?.data?.detail || '查询失败')
  } finally {
    topicCreating.value = false
  }
}

function selectL1(cat: string) {
  activeL1.value = cat
  activeL2.value = ''
  offset.value = 0
  feed.value = []
  noMore.value = false
  loadFeed()
}

async function loadBanner() {
  try {
    const r = await api<any>('/banner')
    if (r?.groups) bannerGroups.value = r.groups
  } catch {
    // ignore
  }
}

async function loadFeed() {
  if (loading.value) return
  loading.value = true
  try {
    const params: any = { limit: PAGE_SIZE, offset: offset.value }
    if (activeL1.value !== '全部') params.l1 = activeL1.value
    if (activeL2.value) params.l2 = activeL2.value
    const r = await api<any>('/items', { query: params })
    const newItems = r?.items || []
    feed.value = [...feed.value, ...newItems]
    if (newItems.length < PAGE_SIZE) noMore.value = true
  } catch {
    noMore.value = true
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || noMore.value) return
  loadingMore.value = true
  offset.value += PAGE_SIZE
  try {
    const params: any = { limit: PAGE_SIZE, offset: offset.value }
    if (activeL1.value !== '全部') params.l1 = activeL1.value
    if (activeL2.value) params.l2 = activeL2.value
    const r = await api<any>('/items', { query: params })
    const newItems = r?.items || []
    feed.value = [...feed.value, ...newItems]
    if (newItems.length < PAGE_SIZE) noMore.value = true
  } catch {
    noMore.value = true
  } finally {
    loadingMore.value = false
  }
}

// 滚动到底自动加载
function onScroll() {
  const sc = document.scrollingElement
  if (!sc) return
  if (sc.scrollHeight - sc.scrollTop - sc.clientHeight < 200) {
    loadMore()
  }
}

onMounted(async () => {
  loadBanner()
  loadFeed()
  document.addEventListener('scroll', onScroll, { passive: true })
})

// 监听 activeL1 变化时清掉 scroll handler
watch(activeL1, () => {
  document.removeEventListener('scroll', onScroll)
  nextTick(() => document.addEventListener('scroll', onScroll, { passive: true }))
})
</script>