<template>
  <div class="pb-2">
    <!-- 顶区：建雷达 -->
    <section class="rounded-3xl overflow-hidden mb-4 shadow-md" style="background: linear-gradient(145deg,#0f766e,#134e4a 50%,#1e1b4b)">
      <div class="p-4 text-white">
        <div class="text-[11px] text-white/70 mb-1">📡 情报雷达</div>
        <h1 class="text-lg font-bold mb-1">盯人 · 盯事</h1>
        <p class="text-[11px] text-white/75 mb-3 leading-relaxed">
          输入实体或事件，自动聚合相关资讯；可转成 3/7/14 天短期跟踪。
        </p>
        <div class="flex gap-2">
          <input
            v-model="newNl"
            type="text"
            placeholder="王力宏 / 世界杯 / 英伟达财报…"
            class="flex-1 px-3 py-2.5 text-sm rounded-xl border-0 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-300"
            :disabled="creating"
            @keyup.enter="quickCreate"
          />
          <button
            class="px-4 py-2.5 rounded-xl bg-white text-emerald-800 text-sm font-semibold active:scale-95 disabled:opacity-60"
            :disabled="creating || !newNl.trim()"
            @click="quickCreate"
          >
            {{ creating ? '…' : '锁定' }}
          </button>
        </div>
      </div>
    </section>

    <!-- 短期跟踪订阅 -->
    <section v-if="tracks.length" class="mb-5">
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-sm font-bold text-slate-900 flex items-center gap-1.5">
          <span class="w-1 h-3.5 rounded-full bg-amber-400" />
          短期跟踪
        </h2>
        <span class="text-[10px] text-slate-400">{{ tracks.length }} 个</span>
      </div>
      <div class="space-y-2">
        <article
          v-for="s in tracks"
          :key="s.id"
          class="rounded-2xl bg-white border border-amber-100 p-3.5 shadow-sm active:bg-amber-50/50 cursor-pointer"
          @click="$router.push(`/m/subs/edit/${s.id}`)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-slate-900 line-clamp-1">
                {{ s.track_entity || s.title }}
              </div>
              <div class="text-[11px] text-slate-500 mt-0.5 line-clamp-1">{{ s.title }}</div>
            </div>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium flex-shrink-0">
              {{ formatRemain(s.expires_at) }}
            </span>
          </div>
          <div class="flex flex-wrap gap-1 mt-2">
            <span
              v-for="kw in (s.keywords || []).slice(0, 4)"
              :key="kw"
              class="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600"
            >{{ kw }}</span>
          </div>
        </article>
      </div>
    </section>

    <!-- 临时话题列表 -->
    <section>
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-sm font-bold text-slate-900 flex items-center gap-1.5">
          <span class="w-1 h-3.5 rounded-full bg-emerald-400" />
          临时话题
        </h2>
        <div class="flex items-center gap-2 text-[11px] text-slate-500">
          <button :class="!showAll ? 'font-bold text-emerald-600' : ''" @click="toggle(false)">活跃</button>
          <span class="text-slate-300">|</span>
          <button :class="showAll ? 'font-bold text-emerald-600' : ''" @click="toggle(true)">全部</button>
        </div>
      </div>

      <div v-if="loading" class="text-center text-slate-400 py-10 text-sm">扫描中…</div>
      <div
        v-else-if="!filtered.length"
        class="rounded-2xl bg-white border border-dashed border-slate-300 p-8 text-center"
      >
        <div class="text-2xl mb-2">🛰️</div>
        <p class="text-xs text-slate-500">雷达空空，上面输入一个关键词锁定</p>
      </div>
      <div v-else class="space-y-2">
        <article
          v-for="t in filtered"
          :key="t.tid"
          class="rounded-2xl bg-white border border-slate-200/80 p-3.5 shadow-sm active:bg-slate-50 cursor-pointer"
          @click="$router.push(`/m/topic/${t.tid}`)"
        >
          <div class="flex items-start justify-between gap-2 mb-1">
            <h3 class="font-semibold text-slate-900 text-sm line-clamp-1 flex-1">
              {{ t.title || t.nl_query }}
            </h3>
            <span
              v-if="t.converted_to_sub_id"
              class="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 flex-shrink-0"
            >已转订阅</span>
            <span
              v-else-if="isExpired(t.expires_at)"
              class="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 flex-shrink-0"
            >过期</span>
            <span
              v-else
              class="text-[10px] px-1.5 py-0.5 rounded-full bg-sky-100 text-sky-700 flex-shrink-0"
            >{{ formatRemain(t.expires_at) }}</span>
          </div>
          <p class="text-[11px] text-slate-500 line-clamp-1 mb-2">"{{ t.nl_query }}"</p>
          <div class="flex items-center text-[11px] text-slate-400">
            <span>{{ t.item_count }} 条聚合</span>
            <span class="ml-auto">{{ formatRelativeTime(t.created_at) }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { createTopicNow, listTopics, api } from '@/lib/api'
import type { TopicListItem, Subscription } from '@/types/api'
import { formatRemain, formatRelativeTime } from '@/lib/mobile-ui'

const router = useRouter()
const loading = ref(true)
const creating = ref(false)
const topics = ref<TopicListItem[]>([])
const tracks = ref<Subscription[]>([])
const showAll = ref(false)
const newNl = ref('')

const filtered = computed(() => {
  if (showAll.value) return topics.value
  return topics.value.filter((t) => !isExpired(t.expires_at))
})

function isExpired(iso?: string): boolean {
  if (!iso) return true
  return new Date(iso).getTime() < Date.now()
}

function toggle(v: boolean) {
  showAll.value = v
  loadTopics()
}

async function loadTopics() {
  loading.value = true
  try {
    const r = await listTopics(!showAll.value)
    topics.value = r.items || []
  } catch {
    topics.value = []
  } finally {
    loading.value = false
  }
}

async function loadTracks() {
  try {
    const r = await api<{ items: Subscription[] }>('/subs')
    tracks.value = (r.items || []).filter((s) => s.track_mode === 'short')
  } catch {
    tracks.value = []
  }
}

async function quickCreate() {
  const nl = newNl.value.trim()
  if (!nl) return
  creating.value = true
  try {
    const r = await createTopicNow(nl, 12, 48)
    const tid = (r as any)?.tid || (r as any)?.id
    newNl.value = ''
    if (tid) router.push(`/m/topic/${tid}`)
    else await loadTopics()
  } catch (e: any) {
    alert(e?.data?.detail || e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  loadTopics()
  loadTracks()
})
</script>
