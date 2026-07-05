<template>
  <div
    class="bg-white rounded-xl border-2 p-4 transition-all"
    :class="[
      cardBorder,
      cardShadow,
    ]"
  >
    <!-- 标题行 -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <span class="text-xl">{{ icon }}</span>
        <span class="font-semibold text-slate-800">{{ title }}</span>
      </div>
      <span
        class="px-2 py-0.5 rounded text-xs font-bold"
        :class="badgeBg"
      >
        {{ statusLabel }}
      </span>
    </div>

    <!-- 状态描述 -->
    <div class="text-sm text-slate-600 mb-2 truncate" :title="comp?.detail">
      {{ comp?.detail || '-' }}
    </div>

    <!-- Latency -->
    <div class="text-xs text-slate-400 mb-3">
      响应: {{ comp?.latency_ms ?? 0 }} ms
      <span v-if="latencyColor" :class="latencyColor" class="ml-2">
        {{ latencyLabel }}
      </span>
    </div>

    <!-- 关键 extras -->
    <div class="space-y-1 text-xs">
      <slot name="extras" :comp="comp" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  name: string
  comp: any
}>()

const emit = defineEmits<{
  (e: 'enable-source', sourceId: string): void
}>()

const titles: Record<string, string> = {
  mongo: 'MongoDB',
  redis: 'Redis',
  api_server: 'API Server',
  web: '前端 Web',
  docs: '文档站',
  daemon: '后台 Daemon',
  ingest_daemon: 'ingest_daemon',
  subs_scheduler: 'subs_scheduler',
  sources: '数据源',
  tasks: '抓取任务',
  llm: 'LLM 路由',
}

const icons: Record<string, string> = {
  mongo: '·DB',
  redis: '·RDB',
  api_server: '·API',
  web: '·WEB',
  docs: '·DOC',
  daemon: '·DAM',
  ingest_daemon: '·ING',
  subs_scheduler: '·SUB',
  sources: '·SRC',
  tasks: '·TSK',
  llm: '·LLM',
}

const title = computed(() => titles[props.name] ?? props.name)
const icon = computed(() => icons[props.name] ?? '·?')

const cardBorder = computed(() => {
  switch (props.comp?.status) {
    case 'ok':   return 'border-emerald-300'
    case 'warn': return 'border-amber-300'
    case 'fail': return 'border-red-400'
    default:     return 'border-slate-200'
  }
})
const cardShadow = computed(() => {
  switch (props.comp?.status) {
    case 'ok':   return 'shadow-sm'
    case 'warn': return 'shadow-md shadow-amber-100'
    case 'fail': return 'shadow-lg shadow-red-100 animate-pulse'
    default:     return 'shadow-sm'
  }
})
const badgeBg = computed(() => {
  switch (props.comp?.status) {
    case 'ok':   return 'bg-emerald-100 text-emerald-700'
    case 'warn': return 'bg-amber-100 text-amber-700'
    case 'fail': return 'bg-red-100 text-red-700'
    default:     return 'bg-slate-100 text-slate-500'
  }
})
const statusLabel = computed(() => {
  switch (props.comp?.status) {
    case 'ok':   return 'OK'
    case 'warn': return 'WARN'
    case 'fail': return 'FAIL'
    default:     return '?'
  }
})

const latencyColor = computed(() => {
  const lat = props.comp?.latency_ms ?? 0
  if (lat > 1000) return 'text-red-500 font-semibold'
  if (lat > 300) return 'text-amber-600'
  return ''
})
const latencyLabel = computed(() => {
  const lat = props.comp?.latency_ms ?? 0
  if (lat > 1000) return '慢'
  if (lat > 300) return '一般'
  return ''
})
</script>
