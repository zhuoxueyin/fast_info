<template>
  <div class="pb-2">
    <!-- 日期问候 -->
    <div class="mb-3">
      <div class="text-[11px] text-slate-400 font-medium tracking-wide">{{ dateLabel }}</div>
      <h1 class="text-xl font-bold text-slate-900 mt-0.5">{{ greeting }}</h1>
    </div>

    <!-- 搜索 -->
    <div class="relative mb-3">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
        <Search :size="15" />
      </span>
      <input
        v-model="q"
        type="search"
        placeholder="搜索资讯 · 关键词"
        class="w-full pl-9 pr-4 py-2.5 text-sm rounded-2xl bg-white border border-slate-200/80 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-300 placeholder:text-slate-400"
        @keyup.enter="onSearch"
      />
    </div>

    <!-- 雷达条（登录后） -->
    <section v-if="auth.isLoggedIn && radarItems.length" class="mb-4">
      <div class="flex items-center justify-between mb-2 px-0.5">
        <div class="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
          <Radar :size="14" class="text-emerald-500" />
          雷达
        </div>
        <router-link to="/m/radar" class="text-[11px] text-emerald-600">全部 →</router-link>
      </div>
      <div class="flex gap-2 overflow-x-auto -mx-4 px-4 pb-1 snap-x">
        <button
          v-for="r in radarItems"
          :key="r.key"
          class="flex-shrink-0 snap-start rounded-2xl px-3 py-2.5 text-left text-white shadow-sm min-w-[148px] max-w-[180px] active:scale-[0.98] transition"
          :style="{ background: r.tone }"
          @click="goRadarItem(r)"
        >
          <div class="text-[10px] text-white/75 mb-0.5">{{ r.kindLabel }}</div>
          <div class="text-xs font-semibold line-clamp-1">{{ r.title }}</div>
          <div class="text-[10px] text-white/80 mt-1">{{ r.meta }}</div>
        </button>
      </div>
    </section>

    <!-- 一句话：订刊 / 盯事 -->
    <section class="mb-4 rounded-2xl bg-white border border-slate-200/80 p-3.5 shadow-sm">
      <div class="flex items-center gap-1.5 mb-2">
        <span class="inline-flex w-6 h-6 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white">
          <Sparkles :size="13" />
        </span>
        <span class="text-sm font-semibold text-slate-900">一句话情报</span>
      </div>
      <input
        v-model="nl"
        type="text"
        placeholder="例：盯特斯拉和比亚迪 / 每天 9 点 AI 早报"
        class="w-full px-3 py-2.5 text-sm rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-300 mb-2"
        :disabled="!!nlBusy"
        @keyup.enter="onRadar"
      />
      <div class="flex gap-2">
        <button
          class="flex-1 py-2 rounded-xl text-xs font-semibold bg-slate-900 text-white active:scale-[0.98] disabled:opacity-50"
          :disabled="!!nlBusy || !nl.trim()"
          @click="onRadar"
        >
          {{ nlBusy === 'radar' ? '建雷达…' : '建雷达 · 盯 7 天' }}
        </button>
        <button
          class="flex-1 py-2 rounded-xl text-xs font-semibold bg-emerald-500 text-white active:scale-[0.98] disabled:opacity-50"
          :disabled="!!nlBusy || !nl.trim()"
          @click="onSubscribe"
        >
          {{ nlBusy === 'sub' ? '跳转…' : '订成频道' }}
        </button>
      </div>
      <p class="text-[10px] text-slate-400 mt-2 leading-relaxed">
        雷达 = 临时聚合 24h 相关资讯；订成频道 = 长期定时推送。
      </p>
    </section>

    <!-- 冲击榜 TOP3 擂台 -->
    <section v-if="hotTop.length" class="mb-4">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
          <Trophy :size="14" class="text-amber-500" />
          今日冲击榜
        </div>
        <router-link to="/m/hot" class="text-[11px] text-emerald-600">完整榜单 →</router-link>
      </div>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="(it, idx) in hotTop"
          :key="it.id"
          class="rounded-2xl p-2.5 text-left text-white shadow-sm active:scale-[0.98] transition min-h-[112px] flex flex-col"
          :style="{ background: podiumTone(idx) }"
          @click="openItem(it.id)"
        >
          <div class="text-lg font-black opacity-90 mb-1">{{ ['🥇', '🥈', '🥉'][idx] }}</div>
          <div class="text-[11px] font-semibold leading-snug line-clamp-3 flex-1">{{ it.title }}</div>
          <div class="text-[10px] text-white/70 mt-1.5">{{ it.category_l1 || '其他' }}</div>
        </button>
      </div>
    </section>

    <!-- L1 筛选 -->
    <div class="flex gap-1.5 overflow-x-auto pb-2 -mx-4 px-4 sticky top-0 z-10 bg-slate-100/95 backdrop-blur-sm">
      <button
        v-for="cat in l1Tabs"
        :key="cat"
        class="text-[11px] px-3 py-1.5 rounded-full whitespace-nowrap flex-shrink-0 font-medium transition"
        :class="activeL1 === cat
          ? 'bg-slate-900 text-white shadow'
          : 'bg-white border border-slate-200 text-slate-600'"
        @click="selectL1(cat)"
      >
        {{ cat }}
      </button>
    </div>

    <!-- 杂志封面流 -->
    <section class="mt-2 space-y-3">
      <div class="flex items-center justify-between px-0.5">
        <h2 class="text-sm font-bold text-slate-900">杂志流</h2>
        <span class="text-[10px] text-slate-400">{{ feed.length ? `${feed.length} 篇` : '' }}</span>
      </div>

      <div v-if="loading && !feed.length" class="text-center text-slate-400 py-10 text-sm">加载简报…</div>
      <div v-else-if="!feed.length" class="text-center text-slate-400 py-10 text-sm">暂无今日内容</div>

      <!-- 头图大卡 -->
      <article
        v-if="hero"
        class="relative rounded-3xl overflow-hidden shadow-md active:scale-[0.99] transition cursor-pointer min-h-[220px]"
        :style="{ background: coverTone(hero.id || hero.title) }"
        @click="openItem(hero.id)"
      >
        <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-black/25 to-transparent" />
        <div class="relative p-4 pt-8 flex flex-col justify-end min-h-[220px]">
          <div class="flex items-center gap-1.5 mb-2">
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white backdrop-blur">
              {{ hero.category_l1 || hero.category || '头条' }}
            </span>
            <span class="text-[10px] text-white/70">{{ sourceLabel(hero.source) }}</span>
            <span v-if="hero.relevance" class="text-[10px] text-amber-300 ml-auto flex items-center gap-0.5">
              <Flame :size="10" /> {{ formatRelScore(hero.relevance) }}
            </span>
          </div>
          <h3 class="text-lg font-bold text-white leading-snug line-clamp-3 mb-2">{{ hero.title }}</h3>
          <p v-if="oneLiner(hero.summary)" class="text-xs text-white/85 leading-relaxed line-clamp-2">
            {{ oneLiner(hero.summary, 64) }}
          </p>
          <div class="text-[10px] text-white/55 mt-2">{{ formatRelativeTime(hero.published_at || hero.fetched_at) }} · 点击沉浸阅读</div>
        </div>
      </article>

      <!-- 常规杂志卡 -->
      <article
        v-for="(item, idx) in restFeed"
        :key="item.id"
        class="rounded-2xl overflow-hidden bg-white border border-slate-200/80 shadow-sm active:scale-[0.99] transition cursor-pointer"
        @click="openItem(item.id)"
      >
        <div
          class="h-1.5"
          :style="{ background: l1Solid(item.category_l1 || item.category) }"
        />
        <div class="p-3.5">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span
              class="text-[10px] px-1.5 py-0.5 rounded-md text-white font-medium"
              :style="{ background: l1Solid(item.category_l1 || item.category) }"
            >
              {{ item.category_l1 || item.category || '其他' }}
            </span>
            <span class="text-[10px] text-slate-400 truncate">{{ sourceLabel(item.source) }}</span>
            <span class="text-[10px] text-slate-400 ml-auto flex-shrink-0">
              {{ formatRelativeTime(item.published_at || item.fetched_at) }}
            </span>
          </div>
          <h3 class="text-[15px] font-semibold text-slate-900 leading-snug line-clamp-2 mb-1.5">
            {{ item.title }}
          </h3>
          <p v-if="oneLiner(item.summary)" class="text-xs text-slate-500 leading-relaxed line-clamp-2">
            <span class="text-emerald-600 font-medium">一句话 · </span>{{ oneLiner(item.summary, 56) }}
          </p>
          <div v-if="idx === 0 && item.relevance" class="mt-2 text-[10px] text-amber-600 flex items-center gap-1">
            <Flame :size="11" /> 热度 {{ formatRelScore(item.relevance) }}
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Search, Sparkles, Trophy, Flame, Radar } from 'lucide-vue-next'
import { api, createTopicNow, listTopics } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import type { Subscription, TopicListItem } from '@/types/api'
import {
  coverTone,
  formatRelativeTime,
  formatRelScore,
  formatRemain,
  l1Solid,
  oneLiner,
  saveFeedIds,
  sourceLabel,
} from '@/lib/mobile-ui'

const router = useRouter()
const auth = useAuthStore()

const q = ref('')
const nl = ref('')
const nlBusy = ref<false | 'radar' | 'sub'>(false)

const l1Tabs = ['全部', '科技', 'AI', '财经', '体育', '娱乐', '汽车', '其他']
const activeL1 = ref('全部')

const feed = ref<any[]>([])
const hotTop = ref<any[]>([])
const loading = ref(false)
const radarItems = ref<{
  key: string
  title: string
  meta: string
  kind: 'topic' | 'track'
  kindLabel: string
  tone: string
  path: string
}[]>([])

const dateLabel = computed(() => dayjs().format('M月D日 dddd'))
const greeting = computed(() => {
  const h = dayjs().hour()
  if (h < 11) return '早上好，今日简报'
  if (h < 14) return '中午好，快速扫一眼'
  if (h < 18) return '下午好，情报更新'
  return '晚上好，3 分钟刷完'
})

const hero = computed(() => feed.value[0] || null)
const restFeed = computed(() => feed.value.slice(1))

function podiumTone(idx: number) {
  return [
    'linear-gradient(145deg,#f59e0b,#b45309)',
    'linear-gradient(145deg,#94a3b8,#475569)',
    'linear-gradient(145deg,#d97706,#78350f)',
  ][idx] || 'linear-gradient(145deg,#64748b,#334155)'
}

function onSearch() {
  if (!q.value.trim()) return
  router.push({ path: '/m/search', query: { q: q.value.trim() } })
}

function openItem(id: string) {
  if (!id) return
  saveFeedIds(feed.value.map((x) => x.id))
  router.push(`/m/items/${id}`)
}

function selectL1(cat: string) {
  activeL1.value = cat
  loadFeed()
}

async function loadFeed() {
  loading.value = true
  try {
    const params: Record<string, any> = { limit: 24 }
    if (activeL1.value !== '全部') params.category = activeL1.value
    const r = await api<any>('/today', { query: params })
    feed.value = r?.items || []
  } catch (e) {
    console.error(e)
    feed.value = []
  } finally {
    loading.value = false
  }
}

async function loadHot() {
  try {
    const r = await api<any>('/hot', { query: { limit: 10, hours: 24 } })
    const items = r?.items || r?.results || []
    hotTop.value = items.slice(0, 3)
  } catch {
    hotTop.value = []
  }
}

async function loadRadar() {
  if (!auth.isLoggedIn) {
    radarItems.value = []
    return
  }
  try {
    const [topicsR, subsR] = await Promise.all([
      listTopics(true).catch(() => ({ items: [] as TopicListItem[] })),
      api<{ items: Subscription[] }>('/subs').catch(() => ({ items: [] as Subscription[] })),
    ])
    const topics = (topicsR.items || []).slice(0, 4)
    const tracks = (subsR.items || [])
      .filter((s) => s.track_mode === 'short' && s.is_active)
      .slice(0, 4)

    const out: typeof radarItems.value = []
    for (const t of topics) {
      out.push({
        key: `t-${t.tid}`,
        title: t.title || t.nl_query,
        meta: `${t.item_count || 0} 条 · ${formatRemain(t.expires_at)}`,
        kind: 'topic',
        kindLabel: '临时话题',
        tone: coverTone(t.tid),
        path: `/m/topic/${t.tid}`,
      })
    }
    for (const s of tracks) {
      out.push({
        key: `s-${s.id}`,
        title: s.track_entity || s.title,
        meta: `跟踪 · ${formatRemain(s.expires_at)}`,
        kind: 'track',
        kindLabel: '短期订阅',
        tone: 'linear-gradient(145deg,#0f766e,#134e4a)',
        path: `/m/subs/edit/${s.id}`,
      })
    }
    radarItems.value = out.slice(0, 6)
  } catch {
    radarItems.value = []
  }
}

function goRadarItem(r: (typeof radarItems.value)[0]) {
  router.push(r.path)
}

async function onRadar() {
  const text = nl.value.trim()
  if (!text) return
  if (!auth.isLoggedIn) {
    router.push({ path: '/m/login', query: { redirect: '/m' } })
    return
  }
  nlBusy.value = 'radar'
  try {
    const r = await createTopicNow(text, 12, 48)
    const tid = (r as any)?.tid || (r as any)?.id
    if (tid) router.push(`/m/topic/${tid}`)
    else alert('创建成功但未返回 id')
  } catch (e: any) {
    alert(e?.data?.detail || e?.message || '创建雷达失败')
  } finally {
    nlBusy.value = false
  }
}

function onSubscribe() {
  const text = nl.value.trim()
  if (!text) return
  if (!auth.isLoggedIn) {
    router.push({ path: '/m/login', query: { redirect: '/m/subs/new' } })
    return
  }
  nlBusy.value = 'sub'
  router.push({ path: '/m/subs/new', query: { nl: text } })
  nlBusy.value = false
}

onMounted(() => {
  loadFeed()
  loadHot()
  loadRadar()
})
</script>
