<template>
  <div class="p-4 pb-20">
    <div v-if="loading" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">⏳</div>
      加载中…
    </div>

    <div v-else-if="!topic" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">🪦</div>
      <p class="mb-2 text-sm">话题不存在或已过期(24h 自动清)</p>
      <button class="text-emerald-600 underline text-sm" @click="$router.replace('/m/topics')">← 我的临时话题</button>
    </div>

    <template v-else>
      <header class="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-4 text-white shadow mb-4">
        <div class="text-xs opacity-80 mb-1">🪜 24h 临时话题</div>
        <h1 class="text-lg font-bold mb-1">{{ topic.parsed.title || topic.nl_query }}</h1>
        <p class="text-xs opacity-80 mb-2">"{{ topic.nl_query }}"</p>
        <div class="flex flex-wrap gap-1 text-xs mb-2">
          <span v-for="kw in topic.parsed.keywords?.slice(0, 4)" :key="kw" class="bg-white/20 rounded-full px-2 py-0.5">{{ kw }}</span>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <span class="opacity-80">{{ topic.item_count }} 条</span>
          <span class="opacity-50">·</span>
          <span class="opacity-80">⏳ {{ formatExpiry(topic.expires_at) }}</span>
        </div>
        <button v-if="!topic.converted_to_sub_id" :disabled="converting" class="mt-3 w-full bg-white text-emerald-700 px-4 py-2 rounded-full text-sm font-medium disabled:opacity-50" @click="openConvertSheet">
          {{ converting ? '转换中…' : '🔄 持续关注(转订阅)' }}
        </button>
        <div v-else class="mt-3 text-xs bg-white/20 rounded p-2">✓ 已转为订阅 #{{ topic.converted_to_sub_id }}</div>
      </header>

      <div v-if="topic.items.length" class="space-y-2">
        <a v-for="item in topic.items" :key="item.id" :href="item.url" target="_blank" class="block bg-white rounded-lg border p-3">
          <div class="font-medium text-sm text-slate-900 line-clamp-2 mb-1">{{ item.title }}</div>
          <div class="text-xs text-slate-500 line-clamp-2 mb-1">{{ item.summary }}</div>
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span class="bg-slate-100 px-1.5 py-0.5 rounded">{{ item.source }}</span>
            <span class="bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded">{{ item.category }}</span>
          </div>
        </a>
      </div>
      <div v-else class="text-center text-slate-400 py-8 text-sm">没命中内容,换个说法试试?</div>
    </template>

    <!-- 转订阅 Sheet(Day 9:弹底部面板选短期/长期) -->
    <n-modal v-model:show="convertSheet" preset="card" :bordered="false" style="max-width: 480px" title="🔄 持续关注">
      <div class="space-y-4">
        <div class="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
          <div class="text-xs text-emerald-700 mb-1">📌 LLM 识别实体</div>
          <div class="text-sm font-semibold text-emerald-900">{{ topic?.parsed?.title || topic?.nl_query || '(无)' }}</div>
        </div>

        <div>
          <div class="text-xs font-semibold text-slate-700 mb-2">跟踪方式</div>
          <n-radio-group v-model:value="trackMode" class="flex flex-col gap-2">
            <n-radio value="short">
              <span>⏰ 短期跟踪(事件类)</span>
            </n-radio>
            <n-radio value="long">
              <span>📡 长期订阅</span>
            </n-radio>
          </n-radio-group>
        </div>

        <div v-if="trackMode === 'short'">
          <div class="text-xs font-semibold text-slate-700 mb-2">天数</div>
          <n-radio-group v-model:value="durationDays">
            <n-radio :value="3">3 天</n-radio>
            <n-radio :value="7">7 天</n-radio>
            <n-radio :value="14">14 天</n-radio>
            <n-radio :value="30">30 天</n-radio>
          </n-radio-group>
        </div>
      </div>
      <template #footer>
        <div class="flex gap-2">
          <n-button class="flex-1" @click="convertSheet = false">取消</n-button>
          <n-button class="flex-1" type="primary" :loading="converting" @click="confirmConvert">
            {{ trackMode === 'short' ? `${durationDays} 天` : '长期' }}
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NModal, NRadioGroup, NRadio, NButton, useMessage } from 'naive-ui'
import { getTopic, convertTopic } from '@/lib/api'

const route = useRoute()
const msg = useMessage()
const loading = ref(true)
const converting = ref(false)
const topic = ref<any>(null)
const convertSheet = ref(false)
const trackMode = ref<'short' | 'long'>('short')
const durationDays = ref(7)

async function load() {
  loading.value = true
  topic.value = null
  try {
    topic.value = await getTopic(route.params.tid as string)
  } catch {
    topic.value = null
  } finally {
    loading.value = false
  }
}

function openConvertSheet() {
  convertSheet.value = true
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
      msg.success(
        r.idempotent
          ? '已转过订阅'
          : trackMode.value === 'short'
            ? `✓ ${opts.duration_days} 天短期跟踪`
            : '✓ 长期订阅',
      )
      convertSheet.value = false
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
  const diffH = Math.max(0, Math.floor((dt.getTime() - Date.now()) / 3600000))
  return diffH <= 0 ? '即将过期' : `${diffH}h 后过期`
}

onMounted(load)
</script>