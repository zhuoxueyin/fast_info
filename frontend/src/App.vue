<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <component :is="layoutComponent">
        <router-view />
      </component>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import MobileLayout from '@/pages/m/MobileLayout.vue'

const route = useRoute()

const themeOverrides = {
  common: {
    primaryColor: '#10B981',
    primaryColorHover: '#059669',
    primaryColorPressed: '#047857',
    primaryColorSuppl: '#10B981',
  },
}

// 根据路由 meta.layout 决定 layout
// mobile 路径以 /m 开头 → MobileLayout,否则 → DefaultLayout
const layoutComponent = computed(() => {
  // 优先级 1: meta.layout
  if (route.meta?.layout === 'mobile') return MobileLayout
  if (route.meta?.layout === 'desktop') return DefaultLayout
  // 优先级 2: 路径判断(兜底)
  // 修正:不能用 startsWith('/m'),否则 /me /monitor 等会被误判为 mobile
  const isMobilePath = route.path === '/m' || route.path.startsWith('/m/')
  if (isMobilePath) return MobileLayout
  return DefaultLayout
})
</script>