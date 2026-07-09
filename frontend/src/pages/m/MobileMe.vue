<template>
  <div>
    <div class="text-center py-4">
      <div class="w-16 h-16 mx-auto rounded-full bg-emerald-500 text-white text-2xl flex items-center justify-center font-bold">
        {{ auth.user?.username?.[0]?.toUpperCase() || '?' }}
      </div>
      <div class="text-lg font-bold mt-2">{{ auth.user?.username }}</div>
      <div class="text-xs text-slate-500">{{ auth.user?.email || '未设置邮箱' }}</div>
    </div>
    <div class="grid grid-cols-2 gap-2 mb-3">
      <router-link to="/m/me/inbox" class="bg-white rounded-lg border p-4 text-center">
        <div class="text-2xl">📥</div>
        <div class="text-sm mt-1">我的推送</div>
      </router-link>
      <router-link to="/m/me/subs" class="bg-white rounded-lg border p-4 text-center">
        <div class="text-2xl">📡</div>
        <div class="text-sm mt-1">订阅管理</div>
      </router-link>
    </div>
    <!-- 快捷操作 -->
    <div class="space-y-2">
      <router-link to="/m/me/settings" class="block bg-emerald-500 text-white rounded-lg py-3 text-center font-medium">
        ⚙️ 个人设置
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store/auth'
const auth = useAuthStore()
</script>
