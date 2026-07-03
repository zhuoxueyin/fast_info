<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">📡 数据源管理</h1>
      <n-button @click="load">🔄 刷新</n-button>
      <nav class="flex gap-2 text-sm ml-auto">
        <router-link to="/admin" class="px-3 py-1 rounded hover:bg-slate-100">汇总</router-link>
        <router-link to="/admin/tasks" class="px-3 py-1 rounded hover:bg-slate-100">任务</router-link>
        <router-link to="/admin/sources" class="px-3 py-1 rounded bg-emerald-50 text-emerald-700">源</router-link>
        <router-link to="/admin/banner" class="px-3 py-1 rounded hover:bg-slate-100">Banner</router-link>
      </nav>
    </div>

    <n-alert v-if="!data?.all_enabled" type="info" :show-icon="false" class="mb-4">
      当前处于「白名单模式」,只有下面选中的源会被抓取。
      <n-button text type="primary" @click="resetAll">恢复全开</n-button>
    </n-alert>

    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h2 class="text-lg font-semibold mb-4">RSS 源 ({{ data?.rss.length || 0 }})</h2>
      <div class="grid gap-3 md:grid-cols-3">
        <div
          v-for="s in data?.rss"
          :key="s.id"
          class="border rounded-lg p-3 cursor-pointer transition"
          :class="s.enabled ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-slate-50 opacity-60'"
          @click="toggle(s.id)"
        >
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-slate-900">{{ s.name }}</span>
            <n-tag :type="s.enabled ? 'success' : 'default'" size="small">
              {{ s.enabled ? '启用' : '停用' }}
            </n-tag>
          </div>
          <div class="text-xs text-slate-500 truncate">{{ s.url }}</div>
          <div class="text-xs text-slate-400 mt-1">默认每 {{ Math.round(s.default_interval_sec / 60) }} 分钟</div>
        </div>
      </div>
    </section>

    <section class="bg-white rounded-xl border border-slate-200 p-6">
      <h2 class="text-lg font-semibold mb-4">大 V 跟踪 ({{ data?.kol.length || 0 }})</h2>
      <div class="grid gap-3 md:grid-cols-3">
        <div
          v-for="s in data?.kol"
          :key="s.id"
          class="border rounded-lg p-3 cursor-pointer transition"
          :class="s.enabled ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-slate-50 opacity-60'"
          @click="toggle(s.id)"
        >
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-slate-900">{{ s.name }}</span>
            <n-tag size="small" :type="s.kind === 'weibo_user' ? 'warning' : s.kind === 'x_user' ? 'info' : 'error'">
              {{ s.kind.split('_')[0] }}
            </n-tag>
          </div>
          <div class="text-xs text-slate-500">{{ s.id }}</div>
        </div>
      </div>
    </section>

    <div class="mt-4 sticky bottom-4 flex justify-end">
      <n-button type="primary" size="large" :loading="saving" @click="save">💾 保存 ({{ enabledIds.length }})</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NButton, NAlert, NTag, useMessage } from 'naive-ui'
import { api } from '@/lib/api'

interface SourceItem {
  id: string
  name: string
  kind: string
  url?: string
  default_interval_sec: number
  enabled: boolean
}

const msg = useMessage()
const saving = ref(false)
const data = ref<{ rss: SourceItem[]; kol: SourceItem[]; all_enabled: boolean } | null>(null)
const enabledIds = ref<string[]>([])

async function load() {
  try {
    const r = await api<any>('/admin/sources')
    data.value = r
    const s: string[] = []
    for (const it of r.rss) if (it.enabled) s.push(it.id)
    for (const it of r.kol) if (it.enabled) s.push(it.id)
    enabledIds.value = s
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

function toggle(id: string) {
  if (enabledIds.value.includes(id)) {
    enabledIds.value = enabledIds.value.filter(x => x !== id)
  } else {
    enabledIds.value = [...enabledIds.value, id]
  }
}

async function save() {
  saving.value = true
  try {
    await api('/admin/sources', { method: 'PUT', body: { enabled: enabledIds.value } })
    msg.success(`已保存,启用 ${enabledIds.value.length} 个源`)
    load()
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function resetAll() {
  await api('/admin/sources', { method: 'PUT', body: { enabled: [] } })
  msg.success('已恢复全开模式')
  load()
}

onMounted(load)
</script>