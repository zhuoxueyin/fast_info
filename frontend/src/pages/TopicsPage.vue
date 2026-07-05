<template>
  <div class="max-w-5xl mx-auto p-6">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-2 text-sm text-slate-500">
      <router-link to="/" class="hover:text-emerald-600">🏠 首页</router-link>
      <span>›</span>
      <span>临时话题</span>
    </div>

    <header class="mb-6 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-6 text-white shadow-lg">
      <div class="text-xs uppercase tracking-wider opacity-80 mb-2">🪜 我的临时话题</div>
      <h1 class="text-2xl font-bold mb-2">24h 临时工作区</h1>
      <p class="text-sm opacity-90 mb-4">短期诉求快速建 dashboard,过期自动清。需要长期跟进 → 一键转订阅。</p>
      <div class="flex flex-wrap gap-3 items-center">
        <n-input
          v-model:value="newNl"
          placeholder="试用例:「世界杯」「AI 资讯」「王力宏动态」……"
          size="medium"
          :disabled="creating"
          class="flex-1 min-w-[200px]"
          @keyup.enter="quickCreate"
        >
          <template #prefix><span class="text-slate-400">💭</span></template>
        </n-input>
        <n-button type="primary" size="medium" :loading="creating" @click="quickCreate">➕ 创建</n-button>
      </div>
    </header>

    <!-- Filter -->
    <div class="mb-4 flex items-center gap-3">
      <n-radio-group v-model:value="showAll" @update:value="load">
        <n-radio :value="false">仅活跃 ({{ activeCount }})</n-radio>
        <n-radio :value="true">含已过期 ({{ totalCount }})</n-radio>
      </n-radio-group>
      <span class="text-xs text-slate-400 ml-auto">{{ filtered.length }} 条</span>
    </div>

    <!-- List -->
    <div v-if="loading" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">⏳</div>
      加载中…
    </div>
    <div v-else-if="!filtered.length" class="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <div class="text-4xl mb-3">🪜</div>
      <p class="text-slate-600 mb-2">还没有临时话题</p>
      <p class="text-xs text-slate-400 mb-4">在上面输入一句话,例如「王力宏动态」「世界杯」「火星探测」</p>
      <p class="text-xs text-slate-400">也可以在 <router-link to="/" class="text-emerald-600 hover:underline">首页</router-link> 创建</p>
    </div>
    <div v-else class="grid gap-3 md:grid-cols-2">
      <article
        v-for="t in filtered"
        :key="t.tid"
        class="bg-white rounded-xl border border-slate-200 p-4 hover:border-emerald-400 hover:shadow-md transition cursor-pointer"
        @click="$router.push(`/topic/${t.tid}`)"
      >
        <div class="flex items-start justify-between gap-2 mb-2">
          <h3 class="font-semibold text-slate-900 text-base line-clamp-1 flex-1">
            {{ t.title || t.nl_query }}
          </h3>
          <n-tag v-if="t.converted_to_sub_id" type="success" size="small">✓ 已转订阅</n-tag>
          <n-tag v-else-if="isExpired(t.expires_at)" type="warning" size="small">⏰ 已过期</n-tag>
          <n-tag v-else type="info" size="small">{{ formatRemain(t.expires_at) }}</n-tag>
        </div>
        <p class="text-xs text-slate-500 mb-3 line-clamp-1">"{{ t.nl_query }}"</p>
        <div class="flex items-center gap-3 text-xs text-slate-400">
          <span>📦 {{ t.item_count }} 命中</span>
          <span>·</span>
          <span>🕐 {{ formatTime(t.created_at) }}</span>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NInput, NButton, NTag, NRadioGroup, NRadio, useMessage } from 'naive-ui'
import { createTopicNow, listTopics } from '@/lib/api'
import type { TopicListItem } from '@/types/api'

const router = useRouter()
const msg = useMessage()
const loading = ref(true)
const creating = ref(false)
const topics = ref<TopicListItem[]>([])
const showAll = ref(false)
const newNl = ref('')

const activeCount = computed(() => topics.value.filter((t) => !isExpired(t.expires_at)).length)
const totalCount = computed(() => topics.value.length)
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
  if (diffH <= 0) return '已过期'
  if (diffH < 1) return `${Math.floor(diffH * 60)} 分钟后过期`
  return `剩 ${Math.floor(diffH)} 小时`
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function load() {
  loading.value = true
  try {
    const r = await listTopics(!showAll.value)
    topics.value = r.items
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
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
    router.push(`/topic/${r.tid}`)
  } catch (e: any) {
    msg.error(e?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>