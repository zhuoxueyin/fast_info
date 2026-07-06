<template>
  <component :is="layoutComponent">
    <router-view />
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import MobileLayout from '@/pages/m/MobileLayout.vue'

const route = useRoute()

// 根据路由 meta.layout 决定用哪个 layout
// mobile 路径以 /m 开头 → MobileLayout,否则 → DefaultLayout
const layoutComponent = computed(() => {
  if (route.path.startsWith('/m')) return MobileLayout
  return DefaultLayout
})

const themeOverrides = {
  common: {
    primaryColor: '#10B981',
    primaryColorHover: '#059669',
    primaryColorPressed: '#047857',
    primaryColorSuppl: '#10B981',
  },
}
</script>