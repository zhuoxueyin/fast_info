<template>
  <div>
    <!-- 顶部 header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-400 to-orange-500 text-white shadow">
          <Trophy :size="18" />
        </span>
        <div>
          <h1 class="text-lg font-bold text-slate-900">今日排行</h1>
          <p class="text-[10px] text-slate-500">最近 {{ hours }}h · 跨类均衡</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="hours"
          class="text-xs border border-slate-200 rounded px-2 py-1 bg-white"
          @change="loadAll"
        >
          <option :value="12">12h</option>
          <option :value="24">24h</option>
          <option :value="48">48h</option>
          <option :value="168">7天</option>
        </select>
        <button
          class="text-xs px-2 py-1 rounded border border-slate-200 bg-white text-slate-600 active:scale-95"
          :disabled="loadingAll"
          @click="loadAll"
        >
          <RefreshCw :size="13" :class="loadingAll ? 'animate-spin inline' : 'hidden'" />
          <span v-if="!loadingAll">刷新</span>
          <span v-else>加载中</span>
        </button>
      </div>
    </div>

    <!-- 总榜区 -->
    <section class="mb-6">
      <h2 class="text-sm font-bold text-slate-900 mb-2 flex items-center gap-1.5">
        <span class="inline-block w-1 h-3.5 rounded-full bg-gradient-to-b from-yellow-400 to-orange-500"></span>
        全站总榜 TOP {{ Math.min(10, overall.length) }}
      </h2>

      <div v-if="overall.length" class="space-y-2">
        <router-link
          v-for="(it, idx) in overall"
          :key="it.id"
          :to="`/m/items/${it.id}`"
          class="block bg-white rounded-xl border border-slate-200 overflow-hidden active:scale-[0.99] transition"
        >
          <div
            v-if="idx < 3"
            class="h-1.5"
            :class="rankBar(idx)"
          ></div>
          <div class="p-3 flex items-start gap-3">
            <span
              class="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm"
              :class="idx < 3 ? rankBgSolid(idx) : 'bg-slate-100 text-slate-500'"
            >
              {{ idx + 1 }}
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 mb-0.5">
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                  {{ it.category_l1 || '其他' }}
                </span>
                <span class="text-[10px] text-slate-400 truncate">{{ sourceLabel(it.source) }}</span>
                <span class="text-[10px] text-orange-500 ml-auto flex-shrink-0">🔥 {{ fmtRel(it.relevance) }}</span>
              </div>
              <h3 class="text-sm font-medium text-slate-900 leading-snug line-clamp-2">{{ it.title }}</h3>
              <p v-if="it.summary && idx < 3" class="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                {{ it.summary }}
              </p>
            </div>
          </div>
        </router-link>
      </div>
      <div v-else-if="!loadingOverall" class="text-center text-slate-400 py-6 text-sm">暂无数据</div>
    </section>

    <!-- 分榜汇总区(横滑 tabs) -->
    <section>
      <h2 class="text-sm font-bold text-slate-900 mb-2 flex items-center gap-1.5">
        <span class="inline-block w-1 h-3.5 rounded-full bg-gradient-to-b from-emerald-400 to-teal-500"></span>
        分榜汇总
      </h2>

      <!-- 横向 tab 切换 -->
      <div class="flex gap-2 overflow-x-auto pb-2 mb-3 -mx-4 px-4 sticky top-0 bg-slate-50 z-10">
        <button
          v-for="c in categoriesData"
          :key="c.category"
          class="flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition flex items-center gap-1"
          :class="activeCat === c.category
            ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow'
            : 'bg-white border border-slate-200 text-slate-600'"
          @click="activeCat = c.category"
        >
          <component :is="l1Icon(c.category)" :size="11" />
          {{ c.category }}
          <span
            class="px-1 rounded text-[10px]"
            :class="activeCat === c.category ? 'bg-white/25 text-white' : 'bg-slate-100 text-slate-500'"
          >
            {{ c.total_in_window }}
          </span>
        </button>
      </div>

      <!-- 当前类榜单 -->
      <div v-if="activeCategory">
        <div class="bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-xl p-3 mb-3 flex items-center gap-2">
          <span class="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-white/20">
            <component :is="l1Icon(activeCategory.category)" :size="18" />
          </span>
          <div class="flex-1">
            <div class="font-bold text-sm">{{ activeCategory.category }} 榜</div>
            <div class="text-[11px] text-white/80">{{ activeCategory.total_in_window }} 条上榜</div>
          </div>
        </div>

        <div v-if="activeCategory.items.length" class="space-y-2">
          <router-link
            v-for="(it, idx) in activeCategory.items"
            :key="it.id"
            :to="`/m/items/${it.id}`"
            class="block bg-white rounded-xl border border-slate-200 p-3 active:scale-[0.99] transition"
          >
            <div class="flex items-start gap-2.5">
              <span
                class="flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center font-bold text-xs"
                :class="idx < 3 ? rankBgSolid(idx) : 'bg-slate-100 text-slate-500'"
              >
                {{ idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5 mb-0.5">
                  <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                    {{ it.category || '其他' }}
                  </span>
                  <span class="text-[10px] text-orange-500 ml-auto">🔥 {{ fmtRel(it.relevance) }}</span>
                </div>
                <h4 class="text-sm font-medium text-slate-900 line-clamp-2">{{ it.title }}</h4>
                <p v-if="it.summary && idx < 3" class="text-xs text-slate-500 mt-1 line-clamp-2">{{ it.summary }}</p>
                <div class="text-[10px] text-slate-400 mt-1">{{ timeLabel(it.published_at || it.fetched_at) }}</div>
              </div>
            </div>
          </router-link>
        </div>
        <div v-else class="text-center text-slate-400 py-6 text-sm">该类目暂无上榜数据</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type FunctionalComponent } from 'vue'
import {
  Trophy, RefreshCw, Cpu, Bot, Trophy as SportIcon, Film,
  DollarSign, Car, Folder,
} from 'lucide-vue-next'
import dayjs from 'dayjs'
import { api } from '@/lib/api'
import type { Item } from '@/types/api'

const hours = ref(48)
const overall = ref<Item[]>([])
const categoriesData = ref<Array<{ category: string; icon: string; total_in_window: number; items: Item[] }>>([])
const activeCat = ref<string>('')
const loadingOverall = ref(false)
const loadingCats = ref(false)
const loadingAll = computed(() => loadingOverall.value || loadingCats.value)

const l1IconMap: Record<string, FunctionalComponent> = {
  科技: Cpu, AI: Bot, 体育: SportIcon, 娱乐: Film,
  财经: DollarSign, 汽车: Car, 其他: Folder,
}
const l1Icon = (c: string): FunctionalComponent => l1IconMap[c] || Folder

const SRC: Record<string, string> = {
  ithome: 'IT之家', '36kr': '36氪', sspai: '少数派', infoq: 'InfoQ',
  qbitai: '量子位', ifanr: '爱范儿', huxiu: '虎嗅', douban: '豆瓣',
  espn_soccer: 'ESPN足球', 'weibo:hot': '微博热搜', zhihu_hot: '知乎热榜',
  bilibili: 'B站', cls: '财联社', wallstreetcn: '华尔街见闻',
}
const sourceLabel = (s: string) => SRC[s] || s

const fmtRel = (v: number | undefined | null) =>
  typeof v === 'number' ? v.toFixed(1) : '-'

const timeLabel = (t: string | undefined | null) => {
  if (!t) return ''
  const d = dayjs(t)
  const now = dayjs()
  const diffMin = now.diff(d, 'minute')
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.format('MM-DD HH:mm')
}

const rankBgSolid = (idx: number) =>
  [
    'bg-gradient-to-br from-yellow-400 to-orange-500 text-white',
    'bg-gradient-to-br from-slate-300 to-slate-400 text-white',
    'bg-gradient-to-br from-orange-300 to-amber-500 text-white',
  ][idx] || ''

const rankBar = (idx: number) =>
  [
    'bg-gradient-to-r from-yellow-400 via-orange-500 to-red-500',
    'bg-gradient-to-r from-slate-300 to-slate-500',
    'bg-gradient-to-r from-orange-300 to-amber-500',
  ][idx] || ''

const activeCategory = computed(() =>
  categoriesData.value.find((c) => c.category === activeCat.value) || null,
)

async function loadOverall() {
  loadingOverall.value = true
  try {
    const r = await api<{ items: Item[] }>('/hot', {
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

onMounted(loadAll)
</script>