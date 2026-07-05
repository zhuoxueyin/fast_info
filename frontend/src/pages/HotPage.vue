<template>
  <div>
    <!-- 顶部独立搜索栏(突出搜索能力) -->
    <section class="mb-5">
      <div class="bg-gradient-to-r from-emerald-500 to-teal-500 rounded-xl p-5 shadow-sm">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-xl">🔍</span>
          <h2 class="text-lg font-semibold text-white">资讯搜索</h2>
          <span class="text-xs text-emerald-50 bg-white/20 rounded-full px-2 py-0.5">全站可搜</span>
        </div>
        <div class="flex gap-2">
          <n-input
            v-model:value="searchQ"
            size="large"
            placeholder="搜索关键词,例如:大模型 / 世界杯 / iPhone 16 / 量子位 …"
            clearable
            @keyup.enter="goSearch"
          >
            <template #prefix>
              <span class="text-slate-400 text-base">🔎</span>
            </template>
          </n-input>
          <n-button type="default" size="large" class="bg-white text-emerald-700 font-medium" @click="goSearch">
            搜索
          </n-button>
        </div>
        <p class="text-xs text-emerald-50 mt-2">按 Enter 或点「搜索」跳转到搜索结果页 · 空格表示 OR,例如「AI 芯片」</p>
      </div>
    </section>

    <!-- 标题 + 时间窗 + 排序切换(单行) -->
    <div class="flex items-center justify-between mb-4 gap-3 flex-wrap">
      <h1 class="text-2xl font-bold text-slate-900">
        {{ sortBy === 'hot' ? '📊 今日排行' : '🕐 最新资讯' }}
      </h1>
      <div class="flex items-center gap-3">
        <div class="flex bg-slate-100 rounded-full p-0.5 text-xs">
          <button
            class="px-3 py-1 rounded-full transition"
            :class="sortBy === 'hot' ? 'bg-white shadow text-emerald-600 font-medium' : 'text-slate-500'"
            @click="onSortChange('hot')"
          >🔥 热度</button>
          <button
            class="px-3 py-1 rounded-full transition"
            :class="sortBy === 'time' ? 'bg-white shadow text-emerald-600 font-medium' : 'text-slate-500'"
            @click="onSortChange('time')"
          >🕐 时间</button>
        </div>
        <n-dropdown :options="hourOptions" @select="onHourSelect" trigger="click" v-if="sortBy === 'hot'">
          <span class="text-sm text-slate-500 cursor-pointer hover:text-emerald-600">
            最近 {{ hours }}h ▾
          </span>
        </n-dropdown>
      </div>
    </div>

    <div class="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-6 text-xs text-blue-700 flex items-start gap-2">
      <span>💡</span>
      <span v-if="sortBy === 'hot'">按 <b>热度分</b>(relevance)排序:综合考虑来源权重、发布时间新鲜度、关键词命中度。点击类目可查看对应榜单。</span>
      <span v-else>按 <b>抓取时间</b>倒序展示,可作为「资讯流」使用,适合查看最新动态。</span>
    </div>

    <n-tabs v-model:value="activeCategory" type="line" animated @update:value="onCatChange">
      <n-tab-pane name="" tab="全部">
        <div v-if="items.length" class="space-y-2 mt-4">
          <div v-for="(it, idx) in items" :key="it.id" class="flex items-start gap-3">
            <span v-if="sortBy === 'hot'" class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white"
              :class="idx < 3 ? 'bg-gradient-to-br from-red-500 to-orange-500' : 'bg-slate-300'">{{ idx + 1 }}</span>
            <span v-else class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm text-slate-400">
              🕐
            </span>
            <div class="flex-1 min-w-0">
              <ItemCard :item="it" compact />
            </div>
          </div>
        </div>
        <n-empty v-else description="暂无数据" />
      </n-tab-pane>
      <n-tab-pane v-for="cat in l1Categories" :key="cat" :name="cat" :tab="`${l1Icon(cat)} ${cat}`">
        <div v-if="(itemsByCatL1[cat] || []).length" class="space-y-2 mt-4">
          <div v-for="(it, idx) in itemsByCatL1[cat]" :key="it.id" class="flex items-start gap-3">
            <span v-if="sortBy === 'hot'" class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white"
              :class="idx < 3 ? 'bg-gradient-to-br from-red-500 to-orange-500' : 'bg-slate-300'">{{ idx + 1 }}</span>
            <span v-else class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm text-slate-400">
              🕐
            </span>
            <div class="flex-1 min-w-0">
              <ItemCard :item="it" compact />
            </div>
          </div>
        </div>
        <n-empty v-else size="small" :description="`${cat} 暂无数据`" />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NTabs, NTabPane, NDropdown, NEmpty, NInput, NButton } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import type { Item, HotResponse, TodayResponse } from '@/types/api'
import ItemCard from '@/components/ItemCard.vue'

const route = useRoute()
const router = useRouter()
const activeCategory = ref('')
const hours = ref(48)
const sortBy = ref<'hot' | 'time'>('hot')
const items = ref<Item[]>([])
const itemsByCatL1 = ref<Record<string, Item[]>>({})
const searchQ = ref('')

const l1Categories = ['科技', 'AI', '财经', '汽车', '娱乐', '体育', '其他']
const l1IconMap: Record<string, string> = {
  科技: '🔬', AI: '🤖', 体育: '⚽', 娱乐: '🎬', 财经: '💰', 汽车: '🚗', 其他: '📂',
}
const l1Icon = (c: string) => l1IconMap[c] || '📂'

const hourOptions = [
  { label: '最近 12h', key: 12 },
  { label: '最近 24h', key: 24 },
  { label: '最近 48h', key: 48 },
  { label: '最近 7 天', key: 168 },
]

function goSearch() {
  const q = searchQ.value.trim()
  if (!q) return
  router.push({ path: '/search', query: { q } })
}

function onHourSelect(key: number) {
  hours.value = key
  load()
}

function onSortChange(s: 'hot' | 'time') {
  if (sortBy.value === s) return
  sortBy.value = s
  // 同步到 URL,方便刷新保留状态
  router.replace({ query: { ...route.query, sort: s === 'time' ? 'time' : undefined } })
  load()
}

function onCatChange(cat: string) {
  if (cat) {
    router.replace({ query: { ...route.query, category: cat } })
  } else {
    const q = { ...route.query }
    delete q.category
    router.replace({ query: q })
  }
}

function groupByL1(list: Item[]): Record<string, Item[]> {
  const grouped: Record<string, Item[]> = {}
  for (const it of list) {
    const c = it.category_l1 || '其他'
    if (!grouped[c]) grouped[c] = []
    grouped[c].push(it)
  }
  return grouped
}

async function load() {
  try {
    if (sortBy.value === 'hot') {
      const cat = activeCategory.value
      if (cat) {
        // 当前类目 tab:拉该类目完整的 ranking
        const r = await api<HotResponse>('/hot', {
          query: { limit: 50, hours: hours.value, threshold: 0, category: cat },
        })
        items.value = r.items
        itemsByCatL1.value = { [cat]: r.items }
      } else {
        // 全部 tab:拉全类目 ranking,并按 L1 分组供子 tab 复用
        const r = await api<HotResponse>('/hot', {
          query: { limit: 50, hours: hours.value, threshold: 0 },
        })
        items.value = r.items
        itemsByCatL1.value = groupByL1(r.items)
      }
    } else {
      // 时间模式:走 /today,按抓取时间倒序;一次拉全量供 L1 子 tab 复用
      const r = await api<TodayResponse>('/today', { query: { limit: 100 } })
      items.value = r.items
      itemsByCatL1.value = groupByL1(r.items)
    }
  } catch {
    items.value = []
    itemsByCatL1.value = {}
  }
}

// 热度模式按类目 tab 切换需重新拉对应类目 ranking;时间模式数据已分组无需重拉
watch(() => activeCategory.value, () => {
  if (sortBy.value === 'hot') load()
})

onMounted(() => {
  const cat = route.query.category as string | undefined
  if (cat && l1Categories.includes(cat)) {
    activeCategory.value = cat
  }
  const sort = route.query.sort as string | undefined
  if (sort === 'time') sortBy.value = 'time'
  load()
})
</script>
