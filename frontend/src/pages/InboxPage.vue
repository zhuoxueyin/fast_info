<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-slate-900">✉️ 晨报信封</h1>
      <div class="flex gap-2">
        <n-button @click="$router.push('/me/push-history')" size="small">晨报记录 →</n-button>
        <n-button @click="$router.push('/me')" size="small">← 我的情报</n-button>
      </div>
    </div>

    <!-- ==================== 晨报记录时间线 ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-4 mb-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold text-slate-900 flex items-center gap-2">
          🕐 晨报记录
          <n-tag v-if="historyStats.total" size="small" :bordered="false">{{ historyStats.total }}</n-tag>
        </h2>
        <div class="flex items-center gap-2">
          <n-radio-group v-model:value="historyFilter" size="small" @update:value="loadHistory">
            <n-radio-button value="">全部</n-radio-button>
            <n-radio-button value="manual">手动</n-radio-button>
            <n-radio-button value="schedule">调度</n-radio-button>
          </n-radio-group>
          <n-button size="tiny" @click="loadHistory">🔄</n-button>
        </div>
      </div>

      <div v-if="historyLoading" class="text-xs text-slate-400 py-2">加载中…</div>
      <div v-else-if="!history.length" class="text-xs text-slate-400 py-3">
        还没有晨报记录。频道跑起来后，这里会出现推送渠道与内容来源。
      </div>
      <ul v-else class="divide-y divide-slate-100">
        <li
          v-for="r in history"
          :key="r.id"
          class="py-3 flex items-start gap-3 cursor-pointer hover:bg-slate-50 -mx-4 px-4 rounded transition"
          @click="toggleExpand(r.id)"
        >
          <span class="text-lg leading-none mt-0.5">{{ triggerIcon(r.trigger) }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-medium text-slate-900 truncate">
                {{ r.subscription_title || '(频道已删)' }}
              </span>
              <n-tag size="tiny" :type="triggerTagType(r.trigger)" :bordered="false">
                {{ triggerLabel(r.trigger) }}
              </n-tag>
              <n-tag
                v-for="ch in r.channels_ok"
                :key="'ok-'+ch"
                size="tiny"
                :bordered="false"
                type="success"
              >✓ {{ chLabel(ch) }}</n-tag>
              <n-tag
                v-for="ch in r.channels_fail"
                :key="'fail-'+ch"
                size="tiny"
                :bordered="false"
                type="error"
              >✗ {{ chLabel(ch) }}</n-tag>
              <span v-if="r.operator && r.operator !== 'auto'" class="text-xs text-slate-400">by {{ r.operator }}</span>
            </div>
            <div class="text-xs text-slate-400 mt-1">
              🕒 {{ formatTime(r.sent_at) }} ·
              <b class="text-slate-700">{{ r.item_count }}</b> 条 ·
              ⏱ {{ r.duration_ms }}ms
            </div>
            <div v-if="expandedId === r.id && r.items.length" class="mt-2 space-y-1">
              <a
                v-for="(it, idx) in r.items"
                :key="idx"
                :href="it.url || '#'"
                target="_blank"
                class="block text-xs text-slate-700 hover:text-emerald-600 truncate"
                @click.stop
              >
                · {{ it.title || '(无标题)' }}
                <span v-if="it.source" class="text-slate-400"> · {{ it.source }}</span>
              </a>
            </div>
            <div v-if="expandedId === r.id && r.error" class="mt-2 text-xs text-rose-500">
              ⚠ {{ r.error }}
            </div>
          </div>
          <span class="text-slate-300 text-sm mt-0.5">{{ expandedId === r.id ? '▾' : '▸' }}</span>
        </li>
      </ul>

      <div v-if="historyStats.by_trigger && Object.keys(historyStats.by_trigger).length"
           class="text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-3">
        <span v-for="(n, k) in historyStats.by_trigger" :key="k">
          <b class="text-slate-700">{{ n }}</b> 条 {{ triggerLabel(k) }}
        </span>
      </div>
    </section>

    <!-- ==================== 推送内容 items:按订阅维度汇总(Day 9+) ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex gap-3 items-center flex-wrap">
      <h2 class="text-sm font-medium text-slate-700">
        📄 按频道汇总
        <span class="text-slate-400">({{ total }} 条 / {{ subscriptionGroups.length }} 个频道)</span>
      </h2>
      <div class="flex-1 flex gap-3 items-center justify-end flex-wrap">
        <n-select v-model:value="filterCategory" :options="categoryOpts" placeholder="类目" clearable class="!w-32" />
        <n-select v-model:value="sort" :options="sortOpts" class="!w-28" />
        <n-button size="small" @click="load">🔄 刷新</n-button>
      </div>
    </section>

    <div v-if="loading" class="text-center text-slate-400 py-8">加载中…</div>
    <div v-else-if="!subscriptionGroups.length" class="text-center py-12 bg-white rounded-xl border border-slate-200">
      <div class="text-5xl mb-3">📭</div>
      <div class="text-slate-500">还没有晨报内容</div>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="grp in subscriptionGroups"
        :key="grp.subscriptionId"
        class="bg-white rounded-xl border border-slate-200 overflow-hidden"
      >
        <n-collapse
          arrow-placement="right"
          :default-expanded-names="defaultExpandedGroups.includes(grp.subscriptionId) ? [grp.subscriptionId] : []"
        >
          <n-collapse-item :name="grp.subscriptionId">
            <template #header>
              <div class="flex items-center gap-2 flex-1 min-w-0 pr-2">
                <span class="text-base flex-shrink-0">📡</span>
                <span class="font-semibold text-slate-900 truncate">
                  {{ grp.title }}
                </span>
                <n-tag size="small" :bordered="false" type="info" class="flex-shrink-0">
                  {{ grp.items.length }} 条
                </n-tag>
                <span class="text-xs text-slate-400 ml-auto truncate flex-shrink-0">
                  最新 {{ grp.latestLabel }}
                </span>
              </div>
            </template>

            <!-- 折叠面板体:订阅内 item 列表 -->
            <ul class="divide-y divide-slate-100">
              <li
                v-for="r in grp.items"
                :key="r.item.id"
                class="py-3 flex items-start gap-3 hover:bg-slate-50 px-1 rounded transition"
              >
                <n-tag size="tiny" :bordered="false" type="success" class="flex-shrink-0 mt-0.5">
                  {{ r.item.category_l1 || r.item.category || '-' }}
                </n-tag>
                <div class="flex-1 min-w-0">
                  <router-link
                    :to="`/items/${r.item.id}`"
                    class="text-sm text-slate-900 hover:text-emerald-600 line-clamp-2 leading-snug block"
                  >
                    {{ r.item.title }}
                  </router-link>
                  <div class="text-xs text-slate-400 mt-1 flex items-center gap-2 flex-wrap">
                    <span>相关度 <b class="text-slate-700">{{ r.item.relevance !== undefined ? r.item.relevance.toFixed(1) : '-' }}</b></span>
                    <span class="text-slate-300">·</span>
                    <span>推送 {{ formatTime(r.delivered_at) }}</span>
                  </div>
                </div>
              </li>
            </ul>
          </n-collapse-item>
        </n-collapse>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  NSelect, NButton, NTag,
  NCollapse, NCollapseItem,
  NRadioGroup, NRadioButton, useMessage,
} from 'naive-ui'
import { api, listPushHistory, getPushHistoryStats } from '@/lib/api'
import type { InboxResponse, InboxItem, PushHistoryRecord } from '@/types/api'

const msg = useMessage()

// ==================== 推送历史 (顶部 timeline) ====================
const history = ref<PushHistoryRecord[]>([])
const historyLoading = ref(false)
const historyFilter = ref('')
const historyStats = ref({ total: 0, by_trigger: {} as Record<string, number>, last_24h: 0 })
const expandedId = ref<string | null>(null)

const TRIGGER_META: Record<string, { label: string; icon: string; tagType: 'default' | 'info' | 'success' | 'warning' }> = {
  manual:   { label: '手动',   icon: '🖱', tagType: 'info' },
  schedule: { label: '调度',   icon: '⏰', tagType: 'success' },
  test:     { label: '测试',   icon: '🧪', tagType: 'warning' },
  cli:      { label: 'CLI',   icon: '💻', tagType: 'default' },
  unknown:  { label: '未知',   icon: '❔', tagType: 'default' },
}

function triggerLabel(t: string) { return TRIGGER_META[t]?.label ?? t }
function triggerIcon(t: string)  { return TRIGGER_META[t]?.icon ?? '❔' }
function triggerTagType(t: string) { return TRIGGER_META[t]?.tagType ?? 'default' }

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

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const r = await listPushHistory({
      limit: 50,
      trigger: historyFilter.value || undefined,
    })
    history.value = r.items
  } catch (e: any) {
    msg.error(e?.data?.detail || '推送历史加载失败')
  } finally {
    historyLoading.value = false
  }
}

async function loadHistoryStats() {
  try {
    historyStats.value = await getPushHistoryStats()
  } catch {
    // ignore
  }
}

// ==================== inbox items:按订阅维度汇总 ====================
const total = ref(0)
const items = ref<InboxItem[]>([])
const loading = ref(false)
const filterCategory = ref<string | null>(null)
const sort = ref<'relevance' | 'time'>('relevance')
const categoryOpts = ref<{ label: string; value: string }[]>([])

const sortOpts = [
  { label: '按热度', value: 'relevance' },
  { label: '按时间', value: 'time' },
]

type SubGroup = {
  subscriptionId: string
  title: string
  items: InboxItem[]
  latestAt: string
  latestLabel: string
}

// 核心:按 subscription_id 分组;组内按当前 sort 排序;组之间按"最新推送时间"倒序
const subscriptionGroups = computed<SubGroup[]>(() => {
  const m = new Map<string, SubGroup>()
  for (const r of items.value) {
    const sid = r.subscription_id || '_unknown'
    if (!m.has(sid)) {
      m.set(sid, {
        subscriptionId: sid,
        title: r.subscription_title || '(订阅已删)',
        items: [],
        latestAt: '',
        latestLabel: '-',
      })
    }
    m.get(sid)!.items.push(r)
  }
  const cmp = sort.value === 'relevance'
    ? (a: InboxItem, b: InboxItem) => (b.item.relevance ?? 0) - (a.item.relevance ?? 0)
    : (a: InboxItem, b: InboxItem) => (b.delivered_at || '').localeCompare(a.delivered_at || '')
  const arr = Array.from(m.values()).map(g => {
    g.items = [...g.items].sort(cmp)
    g.latestAt = g.items.reduce((mx, x) => (x.delivered_at || '') > mx ? (x.delivered_at || '') : mx, '')
    g.latestLabel = formatTime(g.latestAt)
    return g
  })
  // 组间按最新推送时间倒序:活跃订阅靠前
  return arr.sort((a, b) => b.latestAt.localeCompare(a.latestAt))
})

// 默认展开前 3 个订阅(订阅多时避免屏太长),用户可手动展开其它
const defaultExpandedGroups = computed(() => subscriptionGroups.value.slice(0, 3).map(g => g.subscriptionId))

// 监听筛选/排序变化,重新请求
watch([filterCategory, sort], () => load())

async function load() {
  loading.value = true
  try {
    const r = await api<InboxResponse>('/inbox', {
      query: {
        sort: sort.value,
        category: filterCategory.value || undefined,
        page_size: 100,
      },
    })
    items.value = r.items
    total.value = r.total
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 先拉推送历史(stats 同步),拉完后再拉 inbox items
  await Promise.all([loadHistory(), loadHistoryStats()])
  try {
    const cats = await api<{ categories: string[] }>('/categories')
    categoryOpts.value = cats.categories.map(c => ({ label: c, value: c }))
  } catch {}
  load()
})
</script>
