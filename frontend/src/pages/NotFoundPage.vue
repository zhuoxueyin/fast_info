<template>
  <div class="text-center py-20">
    <div class="text-6xl mb-4">🤔</div>
    <h1 class="text-2xl font-bold text-slate-900 mb-2">404</h1>
    <p class="text-slate-500 mb-6">页面不存在</p>
    <n-button @click="$router.push('/')">回到首页</n-button>
  </div>
</template>

<script setup lang="ts">
import { NButton } from 'naive-ui'
</script>