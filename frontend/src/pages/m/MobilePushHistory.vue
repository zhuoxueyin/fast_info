<template>
  <div>
    <div class="flex items-center gap-2 mb-4">
      <button class="p-1 -ml-1" @click="goBack">
        <ChevronLeft :size="22" />
      </button>
      <h1 class="text-lg font-bold text-slate-900">📬 推送历史</h1>
    </div>

    <!-- 触发筛选 -->
    <div class="bg-white rounded-xl border border-slate-200 p-3 mb-4">
      <select
        v-model="filterTrigger"
        class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white"
        @change="loadList"
      >
        <option value="">全部触发类型</option>
        <option value="manual">🖱 手动</option>
        <option value="schedule">⏰ 自动调度</option>
        <option value="test">🧪 测试</option>
        <option value="cli">💻 CLI</option>
      </select>
      <div v-if="stats" class="text-xs text-slate-500 mt-2 flex flex-wrap gap-2">
        <span>总推送: <b class="text-slate-900">{{ stats.total }}</b></span>
        <span v-for="(n, k) in stats.by_trigger" :key="k">
          · <b class="text-slate-900">{{ n }}</b> {{ triggerLabel(k) }}
        </span>
      </div>
    </div>

    <!-- 加载/空态 -->
    <div v-if="loading" class="text-center text-slate-400 py-10 text-sm">加载中…</div>
    <div v-else-if="!records.length" class="text-center py-12 bg-white rounded-xl border border-slate-200">
      <div class="text-4xl mb-2">📭</div>
      <div class="text-slate-500 text-sm">还没有推送记录</div>
    </div>

    <!-- 记录列表 -->
    <div v-else class="space-y-3">
      <div
        v-for="r in records"
        :key="r.id"
        class="bg-white rounded-xl border border-slate-200 p-4"
      >
        <div class="flex items-start gap-2 mb-2">
          <div class="text-xl">{{ triggerIcon(r.trigger) }}</div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-semibold text-slate-900 truncate">
              {{ r.subscription_title || '订阅推送' }}
            </div>
            <div class="flex flex-wrap items-center gap-1 mt-1">
              <n-tag size="tiny" :type="triggerType(r.trigger)" :bordered="false">
                {{ triggerLabel(r.trigger) }}
              </n-tag>
              <n-tag v-if="r.operator && r.operator !== 'auto'" size="tiny" :bordered="false">
                by {{ r.operator }}
              </n-tag>
            </div>
            <div class="text-xs text-slate-400 mt-1">
              🕒 {{ formatTime(r.sent_at) }} · {{ r.item_count }} 条 · {{ r.duration_ms }}ms
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-1.5 mb-2">
          <span
            v-for="(res, ch) in r.channel_results"
            :key="ch"
            class="text-[10px] px-1.5 py-0.5 rounded border"
            :class="res.ok
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-rose-200 bg-rose-50 text-rose-700'"
          >
            {{ res.ok ? '✓' : '✗' }} {{ chLabel(ch) }}
          </span>
        </div>

        <details v-if="r.items.length" class="text-xs">
          <summary class="cursor-pointer text-slate-500 hover:text-slate-900 select-none">
            📄 看了 {{ r.items.length }} 条内容
          </summary>
          <ul class="mt-2 space-y-1">
            <li
              v-for="(it, idx) in r.items"
              :key="idx"
              class="text-slate-700 truncate"
            >
              <a :href="it.url || '#'" target="_blank" class="hover:text-emerald-600">
                {{ it.title || '(无标题)' }}
              </a>
            </li>
          </ul>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NTag } from 'naive-ui'
import { ChevronLeft } from 'lucide-vue-next'
import { listPushHistory, getPushHistoryStats } from '@/lib/api'
import type { PushHistoryRecord } from '@/types/api'

const router = useRouter()

const records = ref<PushHistoryRecord[]>([])
const stats = ref<{ total: number; by_trigger: Record<string, number>; last_24h: number } | null>(null)
const filterTrigger = ref('')
const loading = ref(false)

const TRIGGER_META: Record<string, { label: string; icon: string; tagType: 'default' | 'info' | 'success' | 'warning' }> = {
  manual:   { label: '手动',   icon: '🖱', tagType: 'info' },
  schedule: { label: '自动调度', icon: '⏰', tagType: 'success' },
  test:     { label: '测试',   icon: '🧪', tagType: 'warning' },
  cli:      { label: 'CLI',   icon: '💻', tagType: 'default' },
  unknown:  { label: '未知',   icon: '❔', tagType: 'default' },
}

function triggerLabel(t: string) { return TRIGGER_META[t]?.label ?? t }
function triggerIcon(t: string)  { return TRIGGER_META[t]?.icon ?? '❔' }
function triggerType(t: string)  { return TRIGGER_META[t]?.tagType ?? 'default' }

const CH_LABEL: Record<string, string> = {
  inbox: '站内', feishu: '飞书群', email: '邮件', wechat: '企业微信', webhook: 'Webhook',
}
function chLabel(c: string) { return CH_LABEL[c] ?? c }

function formatTime(iso?: string | null) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

async function loadList() {
  loading.value = true
  try {
    const r = await listPushHistory({
      limit: 100,
      trigger: filterTrigger.value || undefined,
    })
    records.value = r.items
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getPushHistoryStats()
  } catch {
    // ignore
  }
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/m/me')
}

onMounted(() => {
  loadList()
  loadStats()
})
</script>
