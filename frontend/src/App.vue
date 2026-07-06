<template>
  <component :is="layoutComponent">
    <router-view />
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import MobileLayout from '@/pages/m/MobileLayout.vue'

const route = useRoute()

// 根据路由 meta.layout 决定 layout
// mobile 路径以 /m 开头 → MobileLayout,否则 → DefaultLayout
const layoutComponent = computed(() => {
  // 优先级 1: meta.layout
  if (route.meta?.layout === 'mobile') return MobileLayout
  if (route.meta?.layout === 'desktop') return DefaultLayout
  // 优先级 2: 路径判断(兜底)
  if (route.path.startsWith('/m')) return MobileLayout
  return DefaultLayout
})
</script>