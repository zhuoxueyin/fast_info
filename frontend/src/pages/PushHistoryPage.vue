<template>
  <div class="max-w-4xl mx-auto pb-12">
    <div class="flex items-center gap-3 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📬 推送历史</h1>
      <button class="text-slate-400 hover:text-slate-700 text-xl leading-none ml-auto" @click="$router.back()">×</button>
    </div>

    <!-- 触发类型筛选 + 统计 -->
    <section class="bg-white rounded-xl border border-slate-200 p-5 mb-6">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <span class="text-sm text-slate-600">触发类型:</span>
        <n-radio-group v-model:value="filterTrigger" size="small" @update:value="loadList">
          <n-radio-button value="">全部</n-radio-button>
          <n-radio-button value="manual">🖱 手动</n-radio-button>
          <n-radio-button value="schedule">⏰ 自动调度</n-radio-button>
          <n-radio-button value="test">🧪 测试</n-radio-button>
          <n-radio-button value="cli">💻 CLI</n-radio-button>
        </n-radio-group>
        <n-button size="small" :loading="loading" @click="loadList">🔄 刷新</n-button>
      </div>
      <div v-if="stats" class="text-xs text-slate-500 flex flex-wrap gap-3">
        <span>总推送: <b class="text-slate-900">{{ stats.total }}</b></span>
        <span v-for="(n, k) in stats.by_trigger" :key="k">
          · <b class="text-slate-900">{{ n }}</b> 条 {{ triggerLabel(k) }}
        </span>
      </div>
    </section>

    <!-- 加载状态 -->
    <div v-if="loading" class="text-center text-slate-400 py-10">加载中…</div>
    <div v-else-if="!records.length" class="text-center py-16 bg-white rounded-xl border border-slate-200">
      <div class="text-5xl mb-3">📭</div>
      <div class="text-slate-500">还没有推送记录</div>
    </div>

    <!-- 推送历史记录 -->
    <section v-else class="space-y-3">
      <div
        v-for="r in records"
        :key="r.id"
        class="bg-white rounded-xl border border-slate-200 p-5"
      >
        <!-- 头: 触发类型 + 时间 + 标题 -->
        <div class="flex items-start gap-3 mb-3">
          <div class="text-2xl">{{ triggerIcon(r.trigger) }}</div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-base font-semibold text-slate-900 truncate">
                {{ r.subscription_title || '订阅推送' }}
              </span>
              <n-tag size="small" :type="triggerType(r.trigger)" :bordered="false">
                {{ triggerLabel(r.trigger) }}
              </n-tag>
              <n-tag v-if="r.operator && r.operator !== 'auto'" size="small" :bordered="false">
                by {{ r.operator }}
              </n-tag>
              <span v-if="r.error" class="text-xs text-rose-500 ml-2">⚠ {{ r.error }}</span>
            </div>
            <div class="text-xs text-slate-400 mt-1">
              🕒 {{ formatTime(r.sent_at) }} ·
              <b class="text-slate-700">{{ r.item_count }}</b> 条 ·
              ⏱ {{ r.duration_ms }}ms
            </div>
          </div>
        </div>

        <!-- 渠道结果 -->
        <div class="flex flex-wrap gap-2 mb-3 text-xs">
          <span
            v-for="(res, ch) in r.channel_results"
            :key="ch"
            class="flex items-center gap-1 px-2 py-1 rounded border"
            :class="res.ok
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-rose-200 bg-rose-50 text-rose-700'"
          >
            {{ res.ok ? '✓' : '✗' }} {{ chLabel(ch) }}
            <span v-if="res.error" class="text-slate-500 ml-1" :title="res.error">{{ res.error }}</span>
          </span>
        </div>

        <!-- 推送的 items -->
        <details v-if="r.items.length" class="text-sm">
          <summary class="cursor-pointer text-slate-500 hover:text-slate-900 select-none">
            📄 看了 {{ r.items.length }} 条内容
          </summary>
          <ul class="mt-2 space-y-1 text-xs">
            <li
              v-for="(it, idx) in r.items"
              :key="idx"
              class="text-slate-700 truncate"
            >
              <a :href="it.url || '#'" target="_blank" class="hover:text-emerald-600">
                {{ it.title || '(无标题)' }}
              </a>
              <span v-if="it.source" class="text-slate-400"> · {{ it.source }}</span>
            </li>
          </ul>
        </details>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NButton, NTag, NRadioGroup, NRadioButton, useMessage,
} from 'naive-ui'
import { listPushHistory, getPushHistoryStats } from '@/lib/api'
import type { PushHistoryRecord } from '@/types/api'

const msg = useMessage()
const records = ref<PushHistoryRecord[]>([])
const stats = ref<{ total: number; by_trigger: Record<string, number>; last_24h: number } | null>(null)
const filterTrigger = ref('')
const loading = ref(false)

const TRIGGER_META: Record<string, { label: string; icon: string; tagType: 'default' | 'info' | 'success' | 'warning' }> = {
  manual:   { label: '手动', icon: '🖱', tagType: 'info' },
  schedule: { label: '自动调度', icon: '⏰', tagType: 'success' },
  test:     { label: '测试', icon: '🧪', tagType: 'warning' },
  cli:      { label: 'CLI', icon: '💻', tagType: 'default' },
  unknown:  { label: '未知', icon: '❔', tagType: 'default' },
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
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false })
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
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
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

onMounted(() => {
  loadList()
  loadStats()
})
</script>
