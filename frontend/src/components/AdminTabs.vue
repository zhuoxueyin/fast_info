<template>
  <nav class="flex gap-2 text-sm">
    <router-link
      v-for="t in tabs"
      :key="t.to"
      :to="t.to"
      class="px-3 py-1 rounded transition"
      :class="isActive(t.to)
        ? 'bg-emerald-50 text-emerald-700'
        : 'hover:bg-slate-100 text-slate-600'"
    >
      {{ t.label }}
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { to: '/admin', label: '总览' },
  { to: '/admin/monitoring', label: '实时监控' },
  { to: '/admin/tasks', label: '任务' },
  { to: '/admin/sources', label: '数据源' },
  { to: '/admin/banner', label: 'Banner 配置' },
]

function isActive(to: string) {
  return route.path === to
}
</script>
