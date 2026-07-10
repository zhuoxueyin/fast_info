<template>
  <div class="pb-2">
    <div class="flex items-start justify-between gap-3 mb-4">
      <div>
        <h1 class="text-xl font-bold text-slate-900">我的频道</h1>
        <p class="text-[11px] text-slate-400 mt-0.5">每个订阅 = 一本杂志</p>
      </div>
      <router-link
        to="/m/subs/new"
        class="inline-flex items-center gap-1 px-3 py-2 rounded-xl bg-emerald-500 text-white text-xs font-semibold shadow-sm active:scale-95"
      >
        <Plus :size="14" /> 订刊
      </router-link>
    </div>

    <div v-if="loading" class="text-center text-slate-400 py-12 text-sm">加载频道…</div>

    <div v-else-if="!subs.length" class="rounded-3xl bg-white border border-dashed border-slate-300 p-8 text-center">
      <div class="text-3xl mb-2">📚</div>
      <p class="text-sm text-slate-600 font-medium mb-1">还没有频道</p>
      <p class="text-xs text-slate-400 mb-4">用一句话订一本你的情报杂志</p>
      <router-link
        to="/m/subs/new"
        class="inline-block px-4 py-2.5 rounded-xl bg-slate-900 text-white text-xs font-semibold"
      >
        创建第一个频道
      </router-link>
    </div>

    <div v-else class="grid grid-cols-2 gap-3">
      <article
        v-for="s in subs"
        :key="s.id"
        class="relative rounded-2xl overflow-hidden shadow-md min-h-[168px] cursor-pointer active:scale-[0.98] transition"
        :style="{ background: coverTone(s.id + s.title) }"
        @click="openChannel(s)"
      >
        <div class="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-black/10" />
        <div class="relative p-3 flex flex-col h-full min-h-[168px]">
          <div class="flex items-center gap-1 mb-auto">
            <span
              v-if="s.track_mode === 'short'"
              class="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-400/90 text-amber-950 font-semibold"
            >
              短期 {{ formatRemain(s.expires_at) }}
            </span>
            <span
              v-else
              class="text-[9px] px-1.5 py-0.5 rounded-full bg-white/20 text-white font-medium"
            >
              {{ s.is_active ? '连载中' : '已停刊' }}
            </span>
          </div>

          <div class="mt-6">
            <h3 class="text-sm font-bold text-white leading-snug line-clamp-2 mb-1">
              {{ s.title }}
            </h3>
            <p v-if="s.track_entity" class="text-[10px] text-emerald-200 mb-1">
              📌 {{ s.track_entity }}
            </p>
            <p class="text-[10px] text-white/70 line-clamp-2 leading-relaxed">
              {{ s.nl_query || (s.keywords || []).slice(0, 3).join(' · ') || '智能订阅' }}
            </p>
            <div class="flex items-center justify-between mt-2 text-[10px] text-white/60">
              <span>{{ scheduleLabel(s) }}</span>
              <span>最多 {{ s.max_items }} 条</span>
            </div>
          </div>
        </div>
      </article>

      <!-- 添加卡 -->
      <router-link
        to="/m/subs/new"
        class="rounded-2xl border-2 border-dashed border-slate-300 bg-white/60 min-h-[168px] flex flex-col items-center justify-center text-slate-400 active:bg-white"
      >
        <Plus :size="28" class="mb-2 opacity-60" />
        <span class="text-xs font-medium">新增频道</span>
      </router-link>
    </div>

    <!-- 底部入口：晨报信封 -->
    <router-link
      to="/m/me/inbox"
      class="mt-5 flex items-center gap-3 rounded-2xl bg-white border border-slate-200 p-3.5 shadow-sm active:scale-[0.99]"
    >
      <span class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
        <Mail :size="18" />
      </span>
      <div class="flex-1 min-w-0">
        <div class="text-sm font-semibold text-slate-800">晨报信封</div>
        <div class="text-[11px] text-slate-400">查看已推送的简报回看台</div>
      </div>
      <ChevronRight :size="16" class="text-slate-300" />
    </router-link>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Mail, ChevronRight } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Subscription } from '@/types/api'
import { coverTone, formatRemain } from '@/lib/mobile-ui'

const router = useRouter()
const subs = ref<Subscription[]>([])
const loading = ref(true)

function scheduleLabel(s: Subscription) {
  if (s.interval_min) return `每 ${s.interval_min}m`
  return s.cron_expr || '定时'
}

function openChannel(s: Subscription) {
  router.push(`/m/subs/edit/${s.id}`)
}

onMounted(async () => {
  try {
    const r = await api<{ items: Subscription[] }>('/subs')
    subs.value = r.items || []
  } finally {
    loading.value = false
  }
})
</script>
