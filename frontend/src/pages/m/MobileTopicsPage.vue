<template>
  <div class="pb-4">
    <div class="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-4 text-white shadow mb-4">
      <div class="text-xs opacity-80 mb-1">🪜 24h 临时话题</div>
      <h1 class="text-lg font-bold mb-2">我的临时话题</h1>
      <div class="flex gap-2">
        <n-input
          v-model:value="newNl"
          placeholder="试:王力宏、世界杯…"
          size="small"
          :disabled="creating"
          class="flex-1"
          @keyup.enter="quickCreate"
        >
          <template #prefix><span class="text-slate-400 text-xs">💭</span></template>
        </n-input>
        <n-button type="primary" size="small" :loading="creating" @click="quickCreate">建</n-button>
      </div>
    </div>

    <div class="flex items-center gap-2 text-xs text-slate-500 mb-3 px-1">
      <span :class="!showAll ? 'font-bold text-emerald-600' : ''" @click="toggle(false)">活跃</span>
      <span>|</span>
      <span :class="showAll ? 'font-bold text-emerald-600' : ''" @click="toggle(true)">全部</span>
      <span class="ml-auto">{{ filtered.length }} 条</span>
    </div>

    <div v-if="loading" class="text-center text-slate-400 py-8">
      <div class="text-xl mb-1">⏳</div>
      <span class="text-xs">加载中…</span>
    </div>
    <div v-else-if="!filtered.length" class="bg-white rounded-xl border border-slate-200 p-8 text-center">
      <div class="text-2xl mb-2">🪜</div>
      <p class="text-xs text-slate-500">还没有临时话题,上面建一个</p>
    </div>
    <div v-else class="space-y-2">
      <article
        v-for="t in filtered"
        :key="t.tid"
        class="bg-white rounded-xl border border-slate-200 p-3 active:bg-slate-50"
        @click="$router.push(`/m/topic/${t.tid}`)"
      >
        <div class="flex items-start justify-between gap-2 mb-1">
          <h3 class="font-semibold text-slate-900 text-sm line-clamp-1 flex-1">
            {{ t.title || t.nl_query }}
          </h3>
          <n-tag v-if="t.converted_to_sub_id" type="success" size="tiny">已转</n-tag>
          <n-tag v-else-if="isExpired(t.expires_at)" type="warning" size="tiny">过期</n-tag>
          <n-tag v-else type="info" size="tiny">{{ formatRemain(t.expires_at) }}</n-tag>
        </div>
        <p class="text-xs text-slate-500 line-clamp-1 mb-2">"{{ t.nl_query }}"</p>
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <span>📦 {{ t.item_count }}</span>
          <span class="ml-auto">🕐 {{ formatTime(t.created_at) }}</span>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NInput, NButton, NTag, useMessage } from 'naive-ui'
import { createTopicNow, listTopics } from '@/lib/api'
import type { TopicListItem } from '@/types/api'

const router = useRouter()
const msg = useMessage()
const loading = ref(true)
const creating = ref(false)
const topics = ref<TopicListItem[]>([])
const showAll = ref(false)
const newNl = ref('')

const filtered = computed(() => {
  if (showAll.value) return topics.value
  return topics.value.filter((t) => !isExpired(t.expires_at))
})

function isExpired(iso: string): boolean {
  if (!iso) return true
  return new Date(iso).getTime() < Date.now()
}

function formatRemain(iso: string): string {
  if (!iso) return '-'
  const diffH = (new Date(iso).getTime() - Date.now()) / 3600000
  if (diffH <= 0) return '过期'
  if (diffH < 1) return `${Math.floor(diffH * 60)}m`
  return `${Math.floor(diffH)}h`
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function toggle(v: boolean) {
  showAll.value = v
  load()
}

async function load() {
  loading.value = true
  try {
    const r = await listTopics(!showAll.value)
    topics.value = r.items
  } catch {
  } finally {
    loading.value = false
  }
}

async function quickCreate() {
  const nl = newNl.value.trim()
  if (!nl) return
  creating.value = true
  try {
    const r = await createTopicNow(nl, 12, 48)
    newNl.value = ''
    router.push(`/m/topic/${r.tid}`)
  } catch (e: any) {
    msg.error(e?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>