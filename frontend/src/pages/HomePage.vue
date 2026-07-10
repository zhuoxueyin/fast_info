<template>
  <div>
    <section class="pt-8 pb-10">
      <div class="relative max-w-2xl mx-auto">
        <span class="absolute left-6 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">🔍</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索情报 · 关键词 · 实体"
          class="w-full pl-14 pr-6 py-4 text-base rounded-full bg-white border border-slate-200 shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:border-emerald-400 transition placeholder:text-slate-400"
          @keyup.enter="goSearch"
        />
      </div>
    </section>

    <section v-if="bannerReady && bannerGroups.length" class="mb-8">
      <div class="grid gap-3" :class="bannerGridClass">
        <article
          v-for="group in bannerGroups"
          :key="group.category"
          class="rounded-xl p-4 text-white shadow-sm overflow-hidden relative cursor-pointer hover:shadow-lg transition-shadow"
          :style="{ background: PALETTE[group.category] || PALETTE['其他'] }"
          @click="selectL1(group.category)"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm font-semibold">{{ iconOf(group.category) }} {{ group.category }}</div>
            <router-link
              :to="`/hot?category=${encodeURIComponent(group.category)}`"
              class="text-xs bg-white/20 hover:bg-white/30 rounded-full px-2 py-0.5 transition"
              @click.stop
            >
              更多 →
            </router-link>
          </div>
          <ul v-if="group.items.length" class="space-y-1">
            <li v-for="(item, idx) in group.items" :key="item.id">
              <router-link
                :to="`/items/${item.id}`"
                class="block text-xs text-white/90 hover:text-white leading-snug line-clamp-1"
                @click.stop
              >
                <span class="inline-block w-4 text-white/50 font-mono">{{ idx + 1 }}.</span>
                {{ item.title }}
              </router-link>
            </li>
          </ul>
          <div v-else class="text-xs text-white/50">暂无数据</div>
        </article>
      </div>
    </section>

    <section class="mb-6">
      <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xl">📡</span>
          <span class="font-semibold text-slate-900">一句话情报</span>
        </div>
        <p class="text-xs text-slate-400 mb-3 ml-8">建雷达 = 临时聚合 24h 相关资讯；要长期推送可到「我的频道」订刊</p>
        <div class="flex gap-2">
          <n-input
            v-model:value="topicQuery"
            placeholder="例：盯特斯拉和比亚迪 / 王力宏 / 英伟达财报"
            size="medium"
            :disabled="topicCreating"
            @keyup.enter="createNowTopic"
          >
            <template #prefix><span class="text-slate-400">📡</span></template>
          </n-input>
          <n-button type="primary" size="medium" :loading="topicCreating" @click="createNowTopic">
            {{ topicCreating ? '锁定中…' : '建雷达' }}
          </n-button>
          <n-button
            size="medium"
            :disabled="topicCreating || !topicQuery.trim()"
            @click="goSubscribe"
          >
            订成频道
          </n-button>
        </div>
      </div>
    </section>

    <section class="mb-3">
      <div class="flex gap-2 overflow-x-auto pb-2 -mx-2 px-2">
        <button
          v-for="cat in l1Tabs"
          :key="cat"
          class="text-sm px-4 py-1.5 rounded-full whitespace-nowrap transition flex-shrink-0"
          :class="activeL1 === cat
            ? 'bg-emerald-500 text-white'
            : 'bg-white border border-slate-200 text-slate-700 hover:border-emerald-300'"
          @click="selectL1(cat)"
        >
          {{ l1Icon(cat) }} {{ cat }}
        </button>
      </div>
    </section>

    <section v-if="availableL2.length && activeL1 !== '全部'" class="mb-4">
      <div class="flex gap-1.5 overflow-x-auto pb-1 -mx-2 px-2">
        <button
          class="text-xs px-3 py-1 rounded-full whitespace-nowrap transition flex-shrink-0"
          :class="!activeL2
            ? 'bg-blue-500 text-white'
            : 'bg-slate-50 border border-slate-200 text-slate-600 hover:border-blue-300'"
          @click="activeL2 = ''"
        >
          全部
        </button>
        <button
          v-for="l2 in availableL2"
          :key="l2"
          class="text-xs px-3 py-1 rounded-full whitespace-nowrap transition flex-shrink-0"
          :class="activeL2 === l2
            ? 'bg-blue-500 text-white'
            : 'bg-slate-50 border border-slate-200 text-slate-600 hover:border-blue-300'"
          @click="activeL2 = l2"
        >
          {{ l2 }}
        </button>
      </div>
    </section>

    <section class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <h2 class="text-xl font-bold text-slate-900">
            {{ l1Icon(activeL1) }} {{ activeL1 }}
            <span v-if="activeL2 && activeL1 !== '全部'"> · {{ activeL2 }}</span>
            <span v-if="activeL1 === '全部' && feedMode === 'personalized'" class="text-xs text-emerald-600 font-normal ml-2">✨ 按你的频道偏好排序</span>
            <span v-else-if="activeL1 === '全部' && feedMode === 'random'" class="text-xs text-slate-500 font-normal ml-2">🎲 随机打散 · 还没订频道?</span>
          </h2>
          <div class="flex bg-slate-100 rounded-full p-0.5 text-xs">
            <button
              class="px-3 py-1 rounded-full transition"
              :class="sortBy === 'hot' ? 'bg-white shadow text-emerald-600 font-medium' : 'text-slate-500'"
              @click="sortBy = 'hot'"
            >🔥 热度</button>
            <button
              class="px-3 py-1 rounded-full transition"
              :class="sortBy === 'time' ? 'bg-white shadow text-emerald-600 font-medium' : 'text-slate-500'"
              @click="sortBy = 'time'"
            >🕐 时间</button>
          </div>
        </div>
      </div>
      <div v-if="displayItems.length" class="grid gap-4 md:grid-cols-2">
        <ItemCard v-for="(item, idx) in displayItems" :key="item.id" :item="item">
          <template v-if="sortBy === 'hot' && item.relevance" #prefix>
            <span class="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white mr-1"
              :class="idx < 3 ? 'bg-red-500' : 'bg-slate-400'">{{ idx + 1 }}</span>
          </template>
        </ItemCard>
      </div>
      <n-empty v-else :description="`${activeL1}${activeL2 ? ' · ' + activeL2 : ''} 暂无数据`" />
    </section>

    <section>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold text-slate-900">📰 最新情报</h2>
      </div>
      <div v-if="latestItems.length" class="grid gap-4 md:grid-cols-3">
        <ItemCard v-for="item in latestItems" :key="item.id" :item="item" compact />
      </div>
      <n-empty v-else description="暂无数据" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { NEmpty, NInput, NButton, useMessage } from 'naive-ui'
import { api, createTopicNow } from '@/lib/api'
import type { Item, HotResponse, TodayResponse, BannerConfig } from '@/types/api'
import ItemCard from '@/components/ItemCard.vue'

const l1Tabs = ['全部', '科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他']
const l1IconMap: Record<string, string> = {
  全部: '🌐', 科技: '🔬', AI: '🤖', 体育: '⚽', 娱乐: '🎬', 财经: '💰', 汽车: '🚗', 其他: '📂',
}
const l1Icon = (c: string) => l1IconMap[c] || '📂'
const iconOf = l1Icon

const l2Map: Record<string, string[]> = {
  科技: ['互联网', '硬件', '数码评测', '科技融资', '开源'],
  AI: ['大模型', 'AI芯片', 'AI应用', 'AI框架', '机器人'],
  体育: ['足球', '篮球', '电竞'],
  娱乐: ['影视', '音乐', '综艺', '动漫'],
  财经: ['宏观', 'A股', '美股', '港股', '币圈', '创业'],
  汽车: ['新能源', '自动驾驶', '新势力', '传统车企'],
  其他: [],
}

const PALETTE: Record<string, string> = {
  AI: 'linear-gradient(135deg, #0F172A 0%, #1E40AF 100%)',
  科技: 'linear-gradient(135deg, #134E4A 0%, #047857 100%)',
  财经: 'linear-gradient(135deg, #4C1D95 0%, #6D28D9 100%)',
  汽车: 'linear-gradient(135deg, #7C2D12 0%, #C2410C 100%)',
  娱乐: 'linear-gradient(135deg, #9F1239 0%, #DB2777 100%)',
  体育: 'linear-gradient(135deg, #064E3B 0%, #10B981 100%)',
  其他: 'linear-gradient(135deg, #334155 0%, #64748B 100%)',
}

const activeL1 = ref('全部')
const activeL2 = ref('')
const sortBy = ref<'hot' | 'time'>('hot')
const hotItems = ref<Item[]>([])
const feedItems = ref<Item[]>([])
const feedMode = ref<'personalized' | 'random'>('random')   // 后端用偏好加权还是稳定打散
const latestItems = ref<Item[]>([])
const bannerReady = ref(false)

const searchQuery = ref('')
const $router = useRouter()
function goSearch() {
  const q = searchQuery.value.trim()
  if (q) $router.push({ path: '/search', query: { q } })
  else $router.push({ path: '/search' })
}

const topicQuery = ref('')
const topicCreating = ref(false)
const topicMsg = useMessage()

async function createNowTopic() {
  const nl = topicQuery.value.trim()
  if (!nl) return
  topicCreating.value = true
  try {
    const r = await createTopicNow(nl, 12, 48)
    const tid = r.tid
    $router.push(`/topic/${tid}`)
  } catch (e: any) {
    topicMsg.error(e?.data?.detail || '锁定雷达失败')
  } finally {
    topicCreating.value = false
  }
}

function goSubscribe() {
  const nl = topicQuery.value.trim()
  if (!nl) return
  $router.push({ path: '/subs/new', query: { nl } })
}

interface BannerGroup {
  category: string
  items: Item[]
}
const bannerGroups = ref<BannerGroup[]>([])

const availableL2 = computed(() => l2Map[activeL1.value] || [])

const displayItems = computed(() => {
  // "全部" tab:走 feedItems(后端已按偏好加权 / 稳定打散)
  if (activeL1.value === '全部') {
    const items = feedItems.value
    if (sortBy.value === 'time') {
      return [...items].sort((a, b) => {
        const ta = a.published_at || a.fetched_at || ''
        const tb = b.published_at || b.fetched_at || ''
        return tb.localeCompare(ta)
      })
    }
    // 热度:沿用后端的 _feed_score / _hot_score → 但 view 不带这两个字段,就用 relevance
    return [...items].sort((a, b) => (b.relevance ?? 0) - (a.relevance ?? 0))
  }

  let items = hotItems.value
  if (activeL2.value) {
    items = items.filter((it) => {
      const cat = it.category || ''
      return cat === activeL2.value || cat.includes(activeL2.value) || activeL2.value.includes(cat)
    })
  }
  if (sortBy.value === 'time') {
    return [...items].sort((a, b) => {
      const ta = a.published_at || a.fetched_at || ''
      const tb = b.published_at || b.fetched_at || ''
      return tb.localeCompare(ta)
    })
  }
  return [...items].sort((a, b) => (b.relevance ?? 0) - (a.relevance ?? 0))
})

const bannerGridClass = computed(() => {
  const n = bannerGroups.value.length
  if (n <= 1) return 'grid-cols-1'
  if (n === 2) return 'grid-cols-1 md:grid-cols-2'
  if (n === 3) return 'grid-cols-1 md:grid-cols-3'
  if (n === 4) return 'grid-cols-2 md:grid-cols-4'
  return 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5'
})

function selectL1(cat: string) {
  activeL1.value = cat
  activeL2.value = ''
}

async function loadHot(cat: string) {
  try {
    const r = await api<HotResponse>('/hot', {
      // 必须显式 mode=category,否则后端会把 category 参数忽略,返回总榜跨类数据
      query: { limit: 20, hours: 168, mode: 'category', category: cat, threshold: 0 },
    })
    hotItems.value = r.items
  } catch {
    hotItems.value = []
  }
}

/**
 * Day 10:"全部" tab 的数据源。
 * 后端 mode=feed:登录用户按订阅偏好加权,匿名/无订阅稳定打散。
 * 用 sortBy 变化触发重排,但不重拉(后端结果已经按偏好排好了,只是 view 层切展示顺序)。
 */
async function loadFeed() {
  try {
    const r = await api<HotResponse & { personalized?: boolean }>('/hot', {
      query: { limit: 30, hours: 168, threshold: 0, mode: 'feed' },
    })
    feedItems.value = r.items
    // 后端返回时如果带 personalized 字段,前端用;否则默认 random
    feedMode.value = r.personalized ? 'personalized' : 'random'
    // 401 时 api.ts 会跳登录;这里只处理解析失败
    if (!localStorage.getItem('token')) {
      feedMode.value = 'random'
    }
  } catch {
    feedItems.value = []
    feedMode.value = 'random'
  }
}

async function loadLatest() {
  try {
    const r = await api<TodayResponse>('/today', { query: { limit: 30 } })
    latestItems.value = r.items
  } catch {
    latestItems.value = []
  }
}

async function loadBanner() {
  try {
    const cfg = await api<BannerConfig>('/banner')
    if (!cfg.categories?.length) {
      bannerGroups.value = []
      bannerReady.value = true
      return
    }
    const results = await Promise.all(
      cfg.categories.map(async (cat) => {
        try {
          const r = await api<HotResponse>('/hot', {
            query: { limit: cfg.max_per_category, hours: 168, mode: 'category', category: cat, threshold: 0 },
          })
          return { category: cat, items: r.items.slice(0, cfg.max_per_category) }
        } catch {
          return { category: cat, items: [] }
        }
      })
    )
    bannerGroups.value = results.filter((g) => g.items.length > 0)
  } catch {
    bannerGroups.value = []
  } finally {
    bannerReady.value = true
  }
}

watch(activeL1, (v) => {
  activeL2.value = ''
  if (v === '全部') {
    loadFeed()
  } else {
    loadHot(v)
  }
})
onMounted(() => {
  loadBanner()
  if (activeL1.value === '全部') {
    loadFeed()
  } else {
    loadHot(activeL1.value)
  }
  loadLatest()
})
</script>
