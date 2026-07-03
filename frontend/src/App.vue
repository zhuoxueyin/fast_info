<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <DefaultLayout>
        <router-view />
      </DefaultLayout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const themeOverrides = {
  common: {
    primaryColor: '#10B981',
    primaryColorHover: '#059669',
    primaryColorPressed: '#047857',
    primaryColorSuppl: '#10B981',
  },
}
</script>