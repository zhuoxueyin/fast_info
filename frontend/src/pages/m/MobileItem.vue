<template>
  <div class="mi-root" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
    <!-- 顶栏 -->
    <div class="mi-top">
      <button class="mi-icon-btn" @click="goBack" aria-label="返回">
        <ChevronLeft :size="22" />
      </button>
      <div class="text-[11px] text-white/60">
        <span v-if="feedIds.length">{{ positionLabel }}</span>
        <span v-else>沉浸阅读</span>
      </div>
      <a
        v-if="item?.url"
        :href="item.url"
        target="_blank"
        rel="noopener"
        class="mi-icon-btn text-[11px] font-medium px-2"
      >
        原文
      </a>
      <span v-else class="w-9" />
    </div>

    <div v-if="loading" class="mi-center text-white/50">加载中…</div>
    <div v-else-if="!item" class="mi-center text-white/50">文章不存在</div>

    <div v-else class="mi-body">
      <!-- 封面区 -->
      <div class="mi-cover" :style="{ background: coverTone(item.id || item.title) }">
        <div class="mi-cover-fade" />
        <div class="mi-cover-content">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">
              {{ item.category_l1 || item.category || '其他' }}
            </span>
            <span class="text-[10px] text-white/65">{{ sourceLabel(item.source) }}</span>
            <span v-if="item.relevance" class="text-[10px] text-amber-300 ml-auto flex items-center gap-0.5">
              <Flame :size="11" /> {{ formatRelScore(item.relevance) }}
            </span>
          </div>
          <h1 class="text-[22px] font-bold text-white leading-snug mb-3">{{ item.title }}</h1>
          <div class="text-[11px] text-white/55">{{ timeLabel }}</div>
        </div>
      </div>

      <!-- 正文卡 -->
      <div class="mi-card">
        <div v-if="oneLiner(item.summary)" class="mi-oneliner">
          <span class="text-emerald-600 font-semibold">一句话 · </span>
          {{ oneLiner(item.summary, 80) }}
        </div>

        <p v-if="item.summary" class="text-[15px] text-slate-700 leading-relaxed whitespace-pre-wrap">
          {{ item.summary }}
        </p>

        <ul v-if="item.key_points?.length" class="mt-4 space-y-2">
          <li
            v-for="(p, i) in item.key_points"
            :key="i"
            class="flex gap-2 text-sm text-slate-700 leading-relaxed"
          >
            <span class="text-emerald-500 font-bold flex-shrink-0">{{ i + 1 }}.</span>
            <span>{{ p }}</span>
          </li>
        </ul>

        <a
          v-if="item.url"
          :href="item.url"
          target="_blank"
          rel="noopener"
          class="mt-6 flex items-center justify-center gap-1 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium active:scale-[0.99]"
        >
          查看原文 <ExternalLink :size="14" />
        </a>
      </div>

      <!-- 上下篇提示 -->
      <div v-if="feedIds.length > 1" class="mi-nav-hint">
        <button
          class="mi-nav-btn"
          :disabled="!prevId"
          @click="goNeighbor(prevId)"
        >
          <ChevronUp :size="16" /> 上一条
        </button>
        <button
          class="mi-nav-btn"
          :disabled="!nextId"
          @click="goNeighbor(nextId)"
        >
          下一条 <ChevronDown :size="16" />
        </button>
      </div>
      <p v-if="feedIds.length > 1" class="text-center text-[10px] text-white/35 pb-6">
        上下滑动也可切换
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ChevronLeft, ChevronUp, ChevronDown, ExternalLink, Flame } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Item } from '@/types/api'
import {
  coverTone,
  formatRelScore,
  loadFeedIds,
  oneLiner,
  sourceLabel,
} from '@/lib/mobile-ui'

const route = useRoute()
const router = useRouter()
const item = ref<Item | null>(null)
const loading = ref(true)
const feedIds = ref<string[]>([])

const timeLabel = computed(() => {
  if (!item.value) return ''
  const t = item.value.published_at || item.value.fetched_at
  return t ? dayjs(t).format('MM-DD HH:mm') : ''
})

const currentIdx = computed(() => {
  const id = String(route.params.id || '')
  return feedIds.value.indexOf(id)
})

const positionLabel = computed(() => {
  if (currentIdx.value < 0) return '沉浸阅读'
  return `${currentIdx.value + 1} / ${feedIds.value.length}`
})

const prevId = computed(() =>
  currentIdx.value > 0 ? feedIds.value[currentIdx.value - 1] : null,
)
const nextId = computed(() =>
  currentIdx.value >= 0 && currentIdx.value < feedIds.value.length - 1
    ? feedIds.value[currentIdx.value + 1]
    : null,
)

async function load(id: string) {
  loading.value = true
  item.value = null
  try {
    const r = await api<Item[]>('/items', { query: { ids: id } })
    if (r?.length) item.value = r[0]
  } finally {
    loading.value = false
  }
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/m')
}

function goNeighbor(id: string | null) {
  if (!id) return
  router.replace(`/m/items/${id}`)
}

// 轻量上下滑切条
let touchY0 = 0
function onTouchStart(e: TouchEvent) {
  touchY0 = e.changedTouches[0]?.clientY ?? 0
}
function onTouchEnd(e: TouchEvent) {
  const y1 = e.changedTouches[0]?.clientY ?? 0
  const dy = y1 - touchY0
  if (Math.abs(dy) < 70) return
  if (dy < 0 && nextId.value) goNeighbor(nextId.value)
  else if (dy > 0 && prevId.value) goNeighbor(prevId.value)
}

watch(
  () => route.params.id,
  (id) => {
    if (id) load(String(id))
  },
)

onMounted(() => {
  feedIds.value = loadFeedIds()
  load(String(route.params.id || ''))
})
</script>

<style scoped>
.mi-root {
  min-height: 100%;
  background: #0f172a;
  color: #fff;
}

.mi-top {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  padding-top: max(10px, env(safe-area-inset-top));
  background: linear-gradient(to bottom, rgba(15, 23, 42, 0.95), rgba(15, 23, 42, 0.4));
}

.mi-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 36px;
  border-radius: 999px;
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.mi-center {
  padding: 80px 16px;
  text-align: center;
  font-size: 14px;
}

.mi-cover {
  position: relative;
  min-height: 240px;
  padding: 24px 20px 48px;
}

.mi-cover-fade {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, #0f172a 0%, transparent 55%);
}

.mi-cover-content {
  position: relative;
  z-index: 1;
  padding-top: 12px;
}

.mi-card {
  margin: -28px 12px 0;
  position: relative;
  z-index: 2;
  background: #fff;
  border-radius: 20px;
  padding: 20px 18px 24px;
  color: #0f172a;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
}

.mi-oneliner {
  font-size: 13px;
  line-height: 1.55;
  color: #475569;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 14px;
}

.mi-nav-hint {
  display: flex;
  gap: 10px;
  padding: 16px 12px 8px;
}

.mi-nav-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  font-weight: 500;
}
.mi-nav-btn:disabled {
  opacity: 0.3;
}
</style>
