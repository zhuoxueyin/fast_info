<template>
  <div class="max-w-2xl">
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">🎨 Banner 配置</h1>
      <nav class="flex gap-2 text-sm ml-auto">
        <router-link to="/admin" class="px-3 py-1 rounded hover:bg-slate-100">汇总</router-link>
        <router-link to="/admin/tasks" class="px-3 py-1 rounded hover:bg-slate-100">任务</router-link>
        <router-link to="/admin/banner" class="px-3 py-1 rounded bg-emerald-50 text-emerald-700">Banner</router-link>
      </nav>
    </div>

    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <p class="text-sm text-slate-600 mb-4">
        选择公域首页要展示的类目(从 items.category 取),上限 {{ MAX }} 个。
      </p>

      <div class="mb-4">
        <div class="text-xs text-slate-500 mb-2">可用类目(点击添加)</div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="c in availableCategories"
            :key="c"
            class="text-sm px-3 py-1 rounded-full border border-slate-300 text-slate-700 hover:border-emerald-400 hover:text-emerald-700"
            @click="add(c)"
          >
            + {{ c }} <span class="text-xs text-slate-400">({{ catCount(c) }})</span>
          </button>
        </div>
      </div>

      <div class="mb-6">
        <div class="text-xs text-slate-500 mb-2">已选 ({{ selected.length }}/{{ MAX }},拖动排序)</div>
        <div v-if="selected.length" class="space-y-2">
          <div
            v-for="(c, i) in selected"
            :key="c"
            class="flex items-center gap-3 p-3 rounded-lg border border-emerald-200 bg-emerald-50"
          >
            <span class="cursor-grab text-slate-400 select-none">≡</span>
            <span class="font-medium text-emerald-900">{{ i + 1 }}. {{ c }}</span>
            <span class="text-xs text-slate-500">{{ catCount(c) }} 条</span>
            <button class="ml-auto text-red-500 text-sm hover:underline" @click="remove(i)">移除</button>
          </div>
        </div>
        <n-empty v-else description="还没选类目" />
      </div>

      <div class="flex items-center gap-3 mb-6">
        <span class="text-sm text-slate-700">每类目展示:</span>
        <n-input-number v-model:value="maxPerCategory" :min="1" :max="10" class="!w-24" />
        <span class="text-sm text-slate-500">条</span>
      </div>

      <n-button type="primary" :loading="saving" @click="save">保存</n-button>
    </section>

    <section class="bg-white rounded-xl border border-slate-200 p-6">
      <h2 class="text-sm font-semibold mb-3">预览</h2>
      <div v-if="selected.length" class="grid gap-3" :style="{ gridTemplateColumns: `repeat(${Math.min(selected.length, 3)}, 1fr)` }">
        <div
          v-for="cat in selected"
          :key="cat"
          class="rounded-xl p-4 text-white"
          :style="{ background: PALETTE[cat] || PALETTE['其他'] }"
        >
          <div class="text-xs uppercase opacity-80 mb-1">{{ cat }}</div>
          <div class="font-semibold mb-1">今日最热</div>
          <div class="text-xs opacity-60">展示 {{ maxPerCategory }} 条</div>
        </div>
      </div>
      <n-empty v-else size="small" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NInputNumber, NButton, NEmpty, useMessage } from 'naive-ui'
import { api } from '@/lib/api'
import type { BannerConfig, Stats } from '@/types/api'

const MAX = 5
const msg = useMessage()
const saving = ref(false)
const selected = ref<string[]>([])
const maxPerCategory = ref(3)
const stats = ref<Stats | null>(null)

const PALETTE: Record<string, string> = {
  AI: 'linear-gradient(135deg, #0F172A 0%, #1E40AF 100%)',
  科技: 'linear-gradient(135deg, #134E4A 0%, #047857 100%)',
  财经: 'linear-gradient(135deg, #4C1D95 0%, #6D28D9 100%)',
  汽车: 'linear-gradient(135deg, #7C2D12 0%, #C2410C 100%)',
  娱乐: 'linear-gradient(135deg, #9F1239 0%, #DB2777 100%)',
  体育: 'linear-gradient(135deg, #064E3B 0%, #10B981 100%)',
  其他: 'linear-gradient(135deg, #334155 0%, #64748B 100%)',
}

const availableCategories = computed(() => {
  const used = new Set(selected.value)
  const all = stats.value?.by_category?.map(c => c._id).filter(Boolean) || []
  return all.filter(c => !used.has(c))
})

function catCount(c: string): number {
  return stats.value?.by_category?.find(x => x._id === c)?.count || 0
}

function add(c: string) {
  if (selected.value.length >= MAX) {
    msg.warning(`最多 ${MAX} 个类目`)
    return
  }
  selected.value.push(c)
}

function remove(i: number) {
  selected.value.splice(i, 1)
}

async function load() {
  try {
    const [b, s] = await Promise.all([
      api<BannerConfig>('/banner'),
      api<Stats>('/admin/stats'),
    ])
    selected.value = b.categories
    maxPerCategory.value = b.max_per_category
    stats.value = s
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

async function save() {
  saving.value = true
  try {
    await api<BannerConfig>('/banner', {
      method: 'PUT',
      body: { categories: selected.value, max_per_category: maxPerCategory.value },
    })
    msg.success('已保存,公域首页将即时生效')
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>