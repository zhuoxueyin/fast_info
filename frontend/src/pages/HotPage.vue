<template>
  <div>
    <!-- ===================== 顶部 header ===================== -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <span class="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-br from-yellow-400 to-orange-500 text-white shadow">
            <Trophy :size="20" />
          </span>
          今日排行
        </h1>
        <p class="text-xs text-slate-500 mt-1.5 ml-11">
          综合 <b>类目内百分位</b> + <b>时间衰减</b> 打分 · TOP 跨类均衡
        </p>
      </div>
      <div class="flex items-center gap-3">
        <n-dropdown :options="hourOptions" @select="onHourSelect" trigger="click">
          <span class="text-sm text-slate-600 cursor-pointer hover:text-emerald-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-emerald-300 bg-white">
            最近 {{ hours }}h ▾
          </span>
        </n-dropdown>
        <button
          class="text-sm text-slate-600 hover:text-emerald-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-emerald-300 bg-white cursor-pointer flex items-center gap-1.5"
          @click="loadAll"
          :disabled="loadingAll"
        >
          <RefreshCw :size="14" :class="loadingAll ? 'animate-spin' : ''" />
          <span>{{ loadingAll ? '刷新中…' : '刷新榜单' }}</span>
        </button>
      </div>
    </div>

    <!-- ===================== 总榜区 ===================== -->
    <section class="mb-10">
      <div class="flex items-end justify-between mb-3">
        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
          <span class="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-yellow-400 to-orange-500"></span>
          全站总榜 TOP {{ Math.min(10, overall.length) }}
        </h2>
        <span class="text-xs text-slate-400">每类目均衡 · 共 {{ overall.length }} 条</span>
      </div>

      <n-empty v-if="!overall.length && !loadingOverall" description="暂无数据,试试拉长时间窗口" />

      <!-- TOP 3 加冕区 -->
      <div v-if="overall.length" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div
          v-for="(it, idx) in overall.slice(0, 3)"
          :key="it.id"
          class="relative rounded-2xl p-5 text-white shadow-lg overflow-hidden cursor-pointer hover:scale-[1.02] transition"
          :class="rankBg(idx)"
          @click="$router.push(`/items/${it.id}`)"
        >
          <!-- 大数字水印 -->
          <div class="absolute -top-4 -right-2 text-[140px] font-black opacity-10 leading-none pointer-events-none">
            {{ idx + 1 }}
          </div>
          <!-- 奖牌 -->
          <div class="flex items-center gap-2 mb-3 relative z-10">
            <span class="inline-flex items-center justify-center w-9 h-9 rounded-full bg-white/25 backdrop-blur font-black text-lg shadow">
              {{ idx + 1 }}
            </span>
            <span class="text-xs px-2 py-0.5 rounded bg-white/20 backdrop-blur flex items-center gap-1">
              <component :is="l1Icon(it.category_l1 || '')" :size="12" />
              {{ it.category_l1 || '其他' }}
            </span>
            <span class="text-xs px-2 py-0.5 rounded bg-white/20 backdrop-blur ml-auto">
              热度 {{ fmtRel(it.relevance) }}
            </span>
          </div>
          <h3 class="font-bold text-base mb-2 leading-snug line-clamp-2 relative z-10" :title="it.title">
            {{ it.title }}
          </h3>
          <p v-if="it.summary" class="text-xs text-white/80 leading-relaxed line-clamp-3 mb-3 relative z-10" :title="it.summary">
            {{ it.summary }}
          </p>
          <div class="flex items-center justify-between text-xs text-white/70 relative z-10">
            <span>{{ sourceLabel(it.source) }}</span>
            <span>{{ timeLabel(it.published_at || it.fetched_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 4-10 名紧凑列表 -->
      <div v-if="overall.length > 3" class="bg-white rounded-2xl border border-slate-200 overflow-hidden divide-y divide-slate-100">
        <router-link
          v-for="(it, idx) in overall.slice(3, 10)"
          :key="it.id"
          :to="`/items/${it.id}`"
          class="flex items-start gap-4 p-3.5 hover:bg-slate-50 transition group"
        >
          <span class="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm text-slate-500 bg-slate-100 group-hover:bg-slate-200">
            {{ idx + 4 }}
          </span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 flex items-center gap-1">
                <component :is="l1Icon(it.category_l1 || '')" :size="11" />
                {{ it.category_l1 || '其他' }}
              </span>
              <span class="text-xs text-slate-400 truncate">{{ sourceLabel(it.source) }}</span>
              <span class="text-xs text-orange-500 ml-auto flex-shrink-0 font-medium">🔥 {{ fmtRel(it.relevance) }}</span>
            </div>
            <h4 class="text-sm font-medium text-slate-800 leading-snug line-clamp-2 group-hover:text-emerald-700" :title="it.title">
              {{ it.title }}
            </h4>
          </div>
        </router-link>
      </div>
    </section>

    <!-- ===================== 分榜汇总区 ===================== -->
    <section>
      <div class="flex items-end justify-between mb-3">
        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
          <span class="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-emerald-400 to-teal-500"></span>
          分榜汇总
        </h2>
        <span class="text-xs text-slate-400">{{ categoriesData.length }} 个类目 · 各 TOP {{ categoriesData[0]?.items?.length || 0 }}</span>
      </div>

      <n-empty v-if="!categoriesData.length && !loadingCats" description="分榜无数据" />

      <div v-if="categoriesData.length" class="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-5">
        <!-- 左侧 L1 导航 -->
        <aside class="bg-white rounded-2xl border border-slate-200 p-2 h-fit lg:sticky lg:top-4">
          <button
            v-for="c in categoriesData"
            :key="c.category"
            class="w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-2 transition cursor-pointer mb-1 last:mb-0"
            :class="activeCat === c.category
              ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow'
              : 'text-slate-700 hover:bg-slate-50'"
            @click="activeCat = c.category"
          >
            <span
              class="inline-flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0"
              :class="activeCat === c.category ? 'bg-white/25' : 'bg-slate-100'"
            >
              <component :is="l1Icon(c.category)" :size="14" :class="activeCat === c.category ? 'text-white' : 'text-slate-600'" />
            </span>
            <span class="font-medium text-sm">{{ c.category }}</span>
            <span
              class="ml-auto text-xs px-1.5 py-0.5 rounded"
              :class="activeCat === c.category
                ? 'bg-white/25 text-white'
                : 'bg-slate-100 text-slate-500'"
            >
              {{ c.total_in_window }}
            </span>
          </button>
        </aside>

        <!-- 右侧该分类榜单 -->
        <div>
          <div
            v-for="c in categoriesData"
            :key="c.category"
            v-show="activeCat === c.category"
          >
            <div class="bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-2xl p-4 mb-4 flex items-center gap-3">
              <span class="inline-flex items-center justify-center w-11 h-11 rounded-xl bg-white/20 backdrop-blur">
                <component :is="l1Icon(c.category)" :size="22" />
              </span>
              <div>
                <h3 class="font-bold text-lg">{{ c.category }} 分类榜</h3>
                <p class="text-xs text-white/80">最近 {{ hours }}h · 共 {{ c.total_in_window }} 条上榜</p>
              </div>
            </div>

            <n-empty v-if="!c.items.length" description="该类目暂无上榜数据" />

            <div v-if="c.items.length" class="space-y-2.5">
              <router-link
                v-for="(it, idx) in c.items"
                :key="it.id"
                :to="`/items/${it.id}`"
                class="block bg-white rounded-xl border border-slate-200 hover:border-emerald-300 hover:shadow-md transition p-4"
              >
                <div class="flex items-start gap-3">
                  <span
                    class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-bold text-base"
                    :class="idx < 3 ? rankBgSolid(idx) : 'bg-slate-100 text-slate-500'"
                  >
                    {{ idx + 1 }}
                  </span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                        {{ it.category || '其他' }}
                      </span>
                      <span class="text-xs text-slate-400 truncate">{{ sourceLabel(it.source) }}</span>
                      <span class="text-xs text-orange-500 ml-auto flex-shrink-0 font-medium">🔥 {{ fmtRel(it.relevance) }}</span>
                    </div>
                    <h4 class="text-sm font-semibold text-slate-900 leading-snug mb-1 line-clamp-2 hover:text-emerald-700" :title="it.title">
                      {{ it.title }}
                    </h4>
                    <p v-if="it.summary" class="text-xs text-slate-500 leading-relaxed line-clamp-2" :title="it.summary">
                      {{ it.summary }}
                    </p>
                    <div class="text-xs text-slate-400 mt-1.5">{{ timeLabel(it.published_at || it.fetched_at) }}</div>
                  </div>
                </div>
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type FunctionalComponent } from 'vue'
import dayjs from 'dayjs'
import { NDropdown, NEmpty } from 'naive-ui'
import {
  Trophy, RefreshCw, Cpu, Bot, Trophy as SportIcon, Film,
  DollarSign, Car, Folder,
} from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Item } from '@/types/api'

// ===================== state =====================
const hours = ref(48)
const overall = ref<Item[]>([])
const categoriesData = ref<Array<{ category: string; icon: string; total_in_window: number; items: Item[] }>>([])
const activeCat = ref<string>('')
const loadingOverall = ref(false)
const loadingCats = ref(false)
const loadingAll = computed(() => loadingOverall.value || loadingCats.value)

// ===================== 常量 =====================
const hourOptions = [
  { label: '最近 12h', key: 12 },
  { label: '最近 24h', key: 24 },
  { label: '最近 48h', key: 48 },
  { label: '最近 7 天', key: 168 },
]

// L1 → lucide icon(无 emoji 字体也能显示)
const l1IconMap: Record<string, FunctionalComponent> = {
  科技: Cpu,
  AI: Bot,
  体育: SportIcon,
  娱乐: Film,
  财经: DollarSign,
  汽车: Car,
  其他: Folder,
}
const l1Icon = (c: string): FunctionalComponent => l1IconMap[c] || Folder

const SOURCE_MAP: Record<string, string> = {
  ithome: 'IT之家', '36kr': '36氪', sspai: '少数派', infoq: 'InfoQ',
  qbitai: '量子位', ifanr: '爱范儿', huxiu: '虎嗅', douban: '豆瓣',
  espn_soccer: 'ESPN足球', 'weibo:hot': '微博热搜', zhihu_hot: '知乎热榜',
  bilibili: 'B站', cls: '财联社', wallstreetcn: '华尔街见闻',
}
const sourceLabel = (s: string) => SOURCE_MAP[s] || s

const fmtRel = (v: number | undefined | null) =>
  typeof v === 'number' ? v.toFixed(1) : '-'

const rankBg = (idx: number) =>
  [
    'bg-gradient-to-br from-yellow-400 via-orange-500 to-red-500',  // TOP1: 金红
    'bg-gradient-to-br from-slate-300 via-slate-400 to-slate-500',  // TOP2: 银
    'bg-gradient-to-br from-orange-300 via-orange-400 to-amber-600', // TOP3: 铜
  ][idx] || 'bg-slate-200'

const rankBgSolid = (idx: number) =>
  [
    'bg-gradient-to-br from-yellow-400 to-orange-500 text-white',
    'bg-gradient-to-br from-slate-300 to-slate-400 text-white',
    'bg-gradient-to-br from-orange-300 to-amber-500 text-white',
  ][idx] || ''

const timeLabel = (t: string | undefined | null) => {
  if (!t) return ''
  const d = dayjs(t)
  const now = dayjs()
  const diffMin = now.diff(d, 'minute')
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.format('MM-DD HH:mm')
}

// ===================== 数据加载 =====================
async function loadOverall() {
  loadingOverall.value = true
  try {
    const r = await api<{ items: Item[]; total: number }>('/hot', {
      query: { limit: 10, hours: hours.value, threshold: 0 },
    })
    overall.value = r.items
  } catch {
    overall.value = []
  } finally {
    loadingOverall.value = false
  }
}

async function loadCategories() {
  loadingCats.value = true
  try {
    const r = await api<{ categories: typeof categoriesData.value }>(
      '/hot/categories',
      { query: { limit: 8, hours: hours.value, threshold: 0 } },
    )
    categoriesData.value = r.categories
    if (!activeCat.value && r.categories.length) {
      activeCat.value = r.categories[0].category
    }
  } catch {
    categoriesData.value = []
  } finally {
    loadingCats.value = false
  }
}

async function loadAll() {
  await Promise.all([loadOverall(), loadCategories()])
}

function onHourSelect(key: number) {
  hours.value = key
  loadAll()
}

onMounted(loadAll)
</script>