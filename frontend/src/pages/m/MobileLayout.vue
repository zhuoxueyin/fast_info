<template>
  <div class="min-h-screen bg-slate-50 max-w-md mx-auto pb-16">
    <header class="sticky top-0 bg-white border-b z-10 px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-7 h-7 rounded-md bg-emerald-500 text-white text-center leading-7 text-sm">⚡</span>
        <span class="font-bold text-slate-900">fastInfo</span>
      </div>
      <button v-if="auth.isLoggedIn" class="text-sm text-slate-500" @click="logout">退出</button>
    </header>

    <main class="px-4 py-3">
      <router-view />
    </main>

    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around py-2 z-10 max-w-md mx-auto">
      <router-link to="/m" class="flex flex-col items-center text-xs text-slate-500">
        <span class="text-xl">🏠</span>
        <span>推荐</span>
      </router-link>
      <router-link to="/m/hot" class="flex flex-col items-center text-xs text-slate-500">
        <span class="text-xl">🔥</span>
        <span>热门</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/me/inbox" class="flex flex-col items-center text-xs text-slate-500">
        <span class="text-xl">📥</span>
        <span>推送</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/me" class="flex flex-col items-center text-xs text-slate-500">
        <span class="text-xl">👤</span>
        <span>我的</span>
      </router-link>
      <router-link v-else to="/m/login" class="flex flex-col items-center text-xs text-slate-500">
        <span class="text-xl">🔑</span>
        <span>登录</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
const auth = useAuthStore()
const router = useRouter()
function logout() { auth.logout(); router.push('/m') }
</script>

<style>
.router-link-active { color: #10B981 !important; }
</style>