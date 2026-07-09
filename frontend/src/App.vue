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
import { computed, defineComponent, h } from 'vue'
import { useRoute } from 'vue-router'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const route = useRoute()

const themeOverrides = {
  common: {
    primaryColor: '#10B981',
    primaryColorHover: '#059669',
    primaryColorPressed: '#047857',
    primaryColorSuppl: '#10B981',
  },
}

/** 透传壳:mobile 路由已自带 MobileLayout 父路由,App 层不再包一层避免双顶栏/双 tab */
const PassthroughLayout = defineComponent({
  name: 'PassthroughLayout',
  setup(_, { slots }) {
    return () => h('div', { class: 'app-passthrough' }, slots.default?.())
  },
})

// Desktop → DefaultLayout(顶 nav)
// Mobile  /m/* → Passthrough(由路由父组件 MobileLayout 负责顶/底栏)
// 不要用 startsWith('/m'),否则 /me 会被误判
const layoutComponent = computed(() => {
  if (route.meta?.layout === 'mobile') return PassthroughLayout
  if (route.meta?.layout === 'desktop') return DefaultLayout
  const isMobilePath = route.path === '/m' || route.path.startsWith('/m/')
  if (isMobilePath) return PassthroughLayout
  return DefaultLayout
})
</script>
