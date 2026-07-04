<template>
  <div class="max-w-5xl mx-auto p-6">
    <div class="mb-4 flex items-center gap-2 text-sm text-slate-500">
      <router-link to="/" class="hover:text-emerald-600">🏠 首页</router-link>
      <span>›</span>
      <span>临时话题</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">⏳</div>
      加载中…
    </div>

    <!-- Not found / expired -->
    <div v-else-if="!topic" class="text-center text-slate-400 py-12">
      <div class="text-2xl mb-2">🪦</div>
      <p class="mb-2">话题不存在或已过期(24h TTL 自动清)</p>
      <n-button @click="$router.push('/')">返回首页</n-button>
    </div>

    <template v-else>
      <!-- 头部 -->
      <header class="mb-6 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-6 text-white shadow-lg">
        <div class="text-xs uppercase tracking-wider opacity-80 mb-2">🪜 24h 临时话题 · 过期后失效</div>
        <h1 class="text-2xl font-bold mb-2">{{ topic.parsed.title || topic.nl_query }}</h1>
        <p class="text-sm opacity-90 mb-3">“{{ topic.nl_query }}”</p>
        <div class="flex flex-wrap gap-2 text-xs mb-4">
          <span v-for="kw in topic.parsed.keywords?.slice(0, 6)" :key="kw" class="bg-white/20 rounded-full px-2 py-0.5">{{ kw }}</span>
          <span v-for="cat in topic.parsed.categories_l1" :key="cat" class="bg-blue-400/30 rounded-full px-2 py-0.5">{{ cat }}</span>
        </div>
        <div class="flex flex-wrap gap-2 text-xs items-center">
          <span class="opacity-80">📦 {{ topic.item_count }} 条命中</span>
          <span class="opacity-50">·</span>
          <span class="opacity-80">⏳ 过期于 {{ formatExpiry(topic.expires_at) }}</span>
          <n-button v-if="!topic.converted_to_sub_id" type="primary" size="small" :loading="converting" @click="convertToSubscription" class="ml-auto">
            🔄 持续关注(转订阅)
          </n-button>
          <n-tag v-else type="success" size="large" class="ml-auto">✓ 已转为订阅 #{{ topic.converted_to_sub_id }}</n-tag>
        </div>
      </header>

      <!-- Items 列表 -->
      <div v-if="topic.items.length">
        <h2 class="text-lg font-semibold mb-3 text-slate-900">📰 命中内容({{ topic.items.length }})</h2>
        <div class="grid gap-4 md:grid-cols-2">
          <ItemCard v-for="item in topic.items" :key="item.id" :item="item" />
        </div>
      </div>
      <n-empty v-else description="没命中内容,试试换个说法?" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NEmpty, NTag, useMessage } from 'naive-ui'
import { getTopic, convertTopic } from '@/lib/api'
import ItemCard from '@/components/ItemCard.vue'

const route = useRoute()
const msg = useMessage()
const loading = ref(true)
const converting = ref(false)
const topic = ref<any>(null)

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

async function convertToSubscription() {
  converting.value = true
  try {
    const r = await convertTopic(route.params.tid as string)
    if (r.converted) {
      msg.success('✓ 已转为订阅,以后会一直推送给你')
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

onMounted(load)
</script>
