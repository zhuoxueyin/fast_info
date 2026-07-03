<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-slate-900">📊 今日排行</h1>
      <n-dropdown :options="hourOptions" @select="onHourSelect" trigger="click">
        <span class="text-sm text-slate-500 cursor-pointer hover:text-emerald-600">
          最近 {{ hours }}h ▾
        </span>
      </n-dropdown>
    </div>

    <div class="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-6 text-xs text-blue-700 flex items-start gap-2">
      <span>💡</span>
      <span>按 <b>热度分</b>(relevance)排序:综合考虑来源权重、发布时间新鲜度、关键词命中度。点击类目可查看对应榜单。</span>
    </div>

    <n-tabs v-model:value="activeCategory" type="line" animated @update:value="onCatChange">
      <n-tab-pane name="" tab="全部">
        <div v-if="items.length" class="space-y-2 mt-4">
          <div v-for="(it, idx) in items" :key="it.id" class="flex items-start gap-3">
            <span class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white"
              :class="idx < 3 ? 'bg-gradient-to-br from-red-500 to-orange-500' : 'bg-slate-300'">{{ idx + 1 }}</span>
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
            <span class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white"
              :class="idx < 3 ? 'bg-gradient-to-br from-red-500 to-orange-500' : 'bg-slate-300'">{{ idx + 1 }}</span>
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
import { ref, onMounted } from 'vue'
import { NTabs, NTabPane, NDropdown, NEmpty } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import type { Item, HotResponse } from '@/types/api'
import ItemCard from '@/components/ItemCard.vue'

const route = useRoute()
const router = useRouter()
const activeCategory = ref('')
const hours = ref(48)
const items = ref<Item[]>([])
const itemsByCatL1 = ref<Record<string, Item[]>>({})

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

function onHourSelect(key: number) {
  hours.value = key
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

async function load() {
  try {
    const r = await api<HotResponse>('/hot', { query: { limit: 50, hours: hours.value, threshold: 0 } })
    items.value = r.items
    const grouped: Record<string, Item[]> = {}
    for (const it of r.items) {
      const c = it.category_l1 || '其他'
      if (!grouped[c]) grouped[c] = []
      grouped[c].push(it)
    }
    itemsByCatL1.value = grouped
  } catch {
    items.value = []
    itemsByCatL1.value = {}
  }
}

onMounted(() => {
  const cat = route.query.category as string | undefined
  if (cat && l1Categories.includes(cat)) {
    activeCategory.value = cat
  }
  load()
})
</script>
