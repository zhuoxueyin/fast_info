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
        class="relative rounded-2xl overflow-hidden shadow-md min-h-[168px] cursor-pointer active:scale-[0.98] transition select-none"
        :style="{ background: coverTone(s.id + s.title) }"
        @click="openChannel(s)"
        @touchstart.passive="onLongPressStart(s, $event)"
        @touchend.passive="onLongPressEnd"
        @touchmove.passive="onLongPressEnd"
      >
        <!-- 长按出现的红底删除覆盖层 -->
        <transition name="fade">
          <div
            v-if="longPressTarget?.id === s.id"
            class="absolute inset-0 bg-rose-500/85 backdrop-blur-sm flex flex-col items-center justify-center text-white"
          >
            <Trash2 :size="32" class="mb-1.5" />
            <p class="text-sm font-semibold">松开取消订阅</p>
            <p class="text-[10px] text-white/80 mt-0.5">「{{ s.title }}」</p>
          </div>
        </transition>

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

    <!-- 删除确认底部 sheet -->
    <div
      v-if="confirmDelete"
      class="fixed inset-x-0 bottom-0 z-50 px-3 pb-3 animate-[slideUp_0.2s_ease-out]"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 p-4 max-w-md mx-auto">
        <p class="text-sm font-semibold text-slate-900 mb-1">确认取消订阅？</p>
        <p class="text-xs text-slate-500 mb-3">「{{ confirmDelete.title }}」将停止推送,推送历史保留</p>
        <div class="flex gap-2">
          <button
            class="flex-1 py-2.5 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium active:bg-slate-200"
            @click="confirmDelete = null"
          >再想想</button>
          <button
            class="flex-1 py-2.5 rounded-xl bg-rose-500 text-white text-sm font-semibold active:bg-rose-600"
            :disabled="deleting"
            @click="doDelete"
          >{{ deleting ? '取消中…' : '确认取消' }}</button>
        </div>
      </div>
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
import { Plus, Mail, ChevronRight, Trash2 } from 'lucide-vue-next'
import { useMessage } from 'naive-ui'
import { api, deleteSub } from '@/lib/api'
import type { Subscription } from '@/types/api'
import { coverTone, formatRemain } from '@/lib/mobile-ui'

const router = useRouter()
const msg = useMessage()
const subs = ref<Subscription[]>([])
const loading = ref(true)

function scheduleLabel(s: Subscription) {
  if (s.interval_min) return `每 ${s.interval_min}m`
  // interval 模式在存储中可能 cron_expr='* * * * *',还原为"实时"
  if (s.cron_expr === '* * * * *') return '实时'
  return s.cron_expr || '定时'
}

function openChannel(s: Subscription) {
  // 长按触发了删除确认时,屏蔽掉"误点"的 click
  if (longPressTarget.value) return
  router.push(`/m/subs/edit/${s.id}`)
}

// 长按删除手势(800ms 触发;移动 5px 取消)
let longPressTimer: ReturnType<typeof setTimeout> | null = null
const longPressTarget = ref<Subscription | null>(null)
let pressStartX = 0
let pressStartY = 0
function onLongPressStart(s: Subscription, e: TouchEvent) {
  pressStartX = e.touches[0].clientX
  pressStartY = e.touches[0].clientY
  longPressTarget.value = s
  longPressTimer = setTimeout(() => {
    longPressTarget.value = s  // 确认进入"待确认"状态,显示红底
  }, 500)
}
function onLongPressEnd() {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
  // 如果已经进入了长按状态 → 弹出底部确认 sheet
  if (longPressTarget.value) {
    confirmDelete.value = longPressTarget.value
    longPressTarget.value = null
  }
}

const confirmDelete = ref<Subscription | null>(null)
const deleting = ref(false)
async function doDelete() {
  if (!confirmDelete.value || deleting.value) return
  deleting.value = true
  try {
    await deleteSub(confirmDelete.value.id)
    msg.success('已取消订阅')
    subs.value = subs.value.filter(s => s.id !== confirmDelete.value!.id)
  } catch (e: any) {
    msg.error(e?.data?.detail || '取消失败')
  } finally {
    deleting.value = false
    confirmDelete.value = null
  }
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

<style scoped>
@keyframes slideUp {
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }
</style>
