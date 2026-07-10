<template>
  <div class="max-w-5xl mx-auto p-6">
    <div class="mb-4 flex items-center gap-2 text-sm text-slate-500">
      <router-link to="/" class="hover:text-emerald-600">🏠 今日简报</router-link>
      <span>›</span>
      <router-link to="/topics" class="hover:text-emerald-600">情报雷达</router-link>
      <span>›</span>
      <span class="line-clamp-1">{{ topic?.parsed?.title || topic?.nl_query || '...' }}</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">⏳</div>
      加载中…
    </div>

    <!-- Not found / expired -->
    <div v-else-if="!topic" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">🪦</div>
      <p class="mb-2">雷达目标不存在或已过期(24h TTL 自动清)</p>
      <div class="flex gap-2 justify-center">
        <n-button @click="$router.push('/topics')">返回雷达</n-button>
        <n-button @click="$router.push('/')">今日简报</n-button>
      </div>
    </div>

    <template v-else>
      <!-- 头部 -->
      <header class="mb-6 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-6 text-white shadow-lg">
        <div class="text-xs uppercase tracking-wider opacity-80 mb-2">📡 情报雷达 · 24h 锁定 · 过期后失效</div>
        <h1 class="text-2xl font-bold mb-2">{{ topic.parsed.title || topic.nl_query }}</h1>
        <p class="text-sm opacity-90 mb-3">"{{ topic.nl_query }}"</p>
        <div class="flex flex-wrap gap-2 text-xs mb-4">
          <span v-for="kw in topic.parsed.keywords?.slice(0, 6)" :key="kw" class="bg-white/20 rounded-full px-2 py-0.5">{{ kw }}</span>
          <span v-for="cat in topic.parsed.categories_l1" :key="cat" class="bg-blue-400/30 rounded-full px-2 py-0.5">{{ cat }}</span>
        </div>
        <div class="flex flex-wrap gap-2 text-xs items-center">
          <span class="opacity-80">📦 {{ topic.item_count }} 条命中</span>
          <span class="opacity-50">·</span>
          <span class="opacity-80">⏳ 过期于 {{ formatExpiry(topic.expires_at) }}</span>
          <n-button v-if="!topic.converted_to_sub_id" type="primary" size="small" :loading="converting" @click="openConvertModal" class="ml-auto">
            🔄 持续关注(转频道)
          </n-button>
          <n-tag v-else type="success" size="large" class="ml-auto">✓ 已转频道 #{{ topic.converted_to_sub_id }}</n-tag>
        </div>
      </header>

      <!-- Items 列表 -->
      <div v-if="topic.items.length">
        <h2 class="text-lg font-semibold mb-3 text-slate-900">📰 雷达命中({{ topic.items.length }})</h2>
        <div class="grid gap-4 md:grid-cols-2">
          <ItemCard v-for="item in topic.items" :key="item.id" :item="item" />
        </div>
      </div>
      <n-empty v-else description="没命中内容,试试换个说法?" />
    </template>

    <!-- 转订阅 Modal(Day 9) -->
    <n-modal v-model:show="convertModal" preset="card" title="🔄 把雷达转成频道" style="max-width: 540px">
      <div class="space-y-4">
        <!-- 实体识别提示 -->
        <div class="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
          <div class="text-xs text-emerald-700 mb-1">📌 LLM 识别的事件/人物</div>
          <div class="text-sm font-semibold text-emerald-900">
            {{ topic?.parsed?.title || topic?.nl_query || '(无)' }}
          </div>
          <div class="text-xs text-emerald-600 mt-1">短期跟踪会围绕这个实体自动收紧关键词</div>
        </div>

        <!-- 选项 -->
        <div>
          <div class="text-sm font-semibold text-slate-900 mb-2">跟踪方式</div>
          <n-radio-group v-model:value="trackMode" class="flex flex-col gap-2">
            <n-radio value="short">
              <div class="flex items-center gap-2">
                <span>⏰ 短期跟踪</span>
                <n-tag size="tiny" type="warning">推荐 · 事件类热点</n-tag>
              </div>
              <div class="text-xs text-slate-500 ml-6 mt-1">设个过期时间,过期自动停;cron 缩短到 6h 一次</div>
            </n-radio>
            <n-radio value="long">
              <div class="flex items-center gap-2">
                <span>📡 长期频道</span>
                <n-tag size="tiny">每天 9 点推送</n-tag>
              </div>
              <div class="text-xs text-slate-500 ml-6 mt-1">一直推,直到你手动停</div>
            </n-radio>
          </n-radio-group>
        </div>

        <!-- 短期天数(仅 short 时显示) -->
        <div v-if="trackMode === 'short'">
          <div class="text-sm font-semibold text-slate-900 mb-2">跟踪天数</div>
          <n-radio-group v-model:value="durationDays">
            <n-radio :value="3">3 天</n-radio>
            <n-radio :value="7">7 天</n-radio>
            <n-radio :value="14">14 天</n-radio>
            <n-radio :value="30">30 天</n-radio>
          </n-radio-group>
          <div class="text-xs text-slate-500 mt-1">
            到期自动停 → 到 {{ formatFuture(durationDays) }} 结束
          </div>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="convertModal = false">取消</n-button>
          <n-button type="primary" :loading="converting" @click="confirmConvert">
            {{ trackMode === 'short' ? `⏰ 转 ${durationDays} 天短期跟踪` : '📡 转长期频道' }}
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NEmpty, NTag, NModal, NRadioGroup, NRadio, useMessage } from 'naive-ui'
import { getTopic, convertTopic } from '@/lib/api'
import ItemCard from '@/components/ItemCard.vue'

const route = useRoute()
const router = useRouter()
const msg = useMessage()
const loading = ref(true)
const converting = ref(false)
const topic = ref<any>(null)
const convertModal = ref(false)
const trackMode = ref<'short' | 'long'>('short')
const durationDays = ref(7)

async function load() {
  loading.value = true
  topic.value = null
  try {
    const r = await getTopic(route.params.tid as string)
    topic.value = r
  } catch (e: any) {
    if (e?.response?.status === 404) topic.value = null
    else msg.error('加载失败')
  } finally {
    loading.value = false
  }
}

function openConvertModal() {
  // 默认 7 天短期,显示选项让用户改
  convertModal.value = true
  trackMode.value = 'short'
  durationDays.value = 7
}

async function confirmConvert() {
  if (!topic.value) return
  converting.value = true
  try {
    const opts: { track_mode?: 'short' | 'long'; duration_days?: number } = {
      track_mode: trackMode.value,
    }
    if (trackMode.value === 'short') opts.duration_days = durationDays.value
    const r = await convertTopic(topic.value.tid, opts)
    if (r.converted) {
      const msg2 = r.idempotent
        ? '↻ 之前已经转过频道了'
        : trackMode.value === 'short'
          ? `✓ 已建短期跟踪频道 #${r.subscription_id},${opts.duration_days} 天后自动停`
          : `✓ 已建长期频道 #${r.subscription_id}`
      msg.success(msg2)
      convertModal.value = false
      await load()
    }
  } catch (e: any) {
    msg.error(e?.data?.detail || '转换失败')
  } finally {
    converting.value = false
  }
}

function formatExpiry(iso: string) {
  if (!iso) return '-'
  const dt = new Date(iso)
  const now = new Date()
  const diffH = Math.max(0, Math.floor((dt.getTime() - now.getTime()) / 3600000))
  if (diffH <= 0) return '即将过期'
  return `${diffH} 小时后`
}

function formatFuture(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function goList() {
  router.push('/topics')
}

onMounted(load)
</script>