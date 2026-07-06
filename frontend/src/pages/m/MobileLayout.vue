<template>
  <div class="min-h-screen bg-slate-50 max-w-md mx-auto pb-16">
    <header class="sticky top-0 bg-white border-b z-10 px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <BrandLogo size="sm" />
      </div>
      <button v-if="auth.isLoggedIn" class="text-sm text-slate-500" @click="logout">退出</button>
    </header>

    <main class="px-4 py-3">
      <router-view />
    </main>

    <!-- 底 tab · 5 个核心入口(登录态切换"我的"/"登录") -->
    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around py-2 z-10 max-w-md mx-auto">
      <router-link to="/m" class="flex flex-col items-center text-xs text-slate-500" active-class="!text-emerald-600">
        <Home :size="20" />
        <span>推荐</span>
      </router-link>
      <router-link to="/m/hot" class="flex flex-col items-center text-xs text-slate-500" active-class="!text-emerald-600">
        <Flame :size="20" />
        <span>热门</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/me/inbox" class="flex flex-col items-center text-xs text-slate-500" active-class="!text-emerald-600">
        <Bell :size="20" />
        <span>推送</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/topics" class="flex flex-col items-center text-xs text-slate-500" active-class="!text-emerald-600">
        <Sparkles :size="20" />
        <span>话题</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/me" class="flex flex-col items-center text-xs text-slate-500" active-class="!text-emerald-600">
        <User :size="20" />
        <span>我的</span>
      </router-link>
      <router-link v-else to="/m/login" class="flex flex-col items-center text-xs text-slate-500" active-class="!text-emerald-600">
        <LogIn :size="20" />
        <span>登录</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Home, Flame, Bell, Sparkles, User, LogIn } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import BrandLogo from '@/components/BrandLogo.vue'
const auth = useAuthStore()
const router = useRouter()
function logout() {
  if (!confirm('确定要退出登录吗?')) return
  auth.logout()
  router.push('/m')
}
</script>

<style>
.router-link-active { color: #10B981 !important; }
</style>