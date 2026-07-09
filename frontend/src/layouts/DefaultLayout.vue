<template>
  <n-layout class="min-h-screen bg-slate-50">
    <n-layout-header bordered class="bg-white shadow-sm">
      <div class="max-w-[1280px] mx-auto px-6 py-3 flex items-center gap-5">
        <router-link to="/" class="flex items-center flex-shrink-0">
          <BrandLogo size="sm" />
        </router-link>

        <nav class="flex items-center gap-4 text-sm flex-shrink-0 ml-6">
          <router-link to="/" class="text-slate-700 hover:text-emerald-600 font-medium">🔥 热点资讯</router-link>
          <router-link to="/hot" class="text-slate-700 hover:text-emerald-600 font-medium">📊 今日排行</router-link>
          <router-link v-if="auth.isLoggedIn" to="/me/inbox" class="text-slate-700 hover:text-emerald-600 font-medium">📥 我的推送</router-link>
          <router-link v-if="auth.isLoggedIn" to="/topics" class="text-slate-700 hover:text-emerald-600 font-medium">🪜 临时话题</router-link>
        </nav>

        <div class="flex-1"></div>

        <nav class="flex items-center gap-3 text-sm flex-shrink-0">
          <template v-if="auth.isLoggedIn">
            <router-link v-if="auth.isAdmin" to="/admin" class="text-amber-600 hover:text-amber-700">🔧 管理</router-link>
            <n-dropdown :options="userMenuOptions" @select="onUserMenu">
              <span class="text-slate-600 cursor-pointer hover:text-emerald-600">👤 {{ auth.user?.username }}</span>
            </n-dropdown>
          </template>
          <template v-else>
            <router-link to="/login" class="text-slate-600 hover:text-emerald-600">登录</router-link>
            <router-link to="/register" class="px-3 py-1 rounded bg-emerald-500 text-white text-sm hover:bg-emerald-600">注册</router-link>
          </template>
        </nav>
      </div>
    </n-layout-header>

    <n-layout-content>
      <div class="max-w-[1280px] mx-auto px-6 py-6">
        <router-view />
      </div>
    </n-layout-content>

    <n-layout-footer class="bg-white border-t">
      <div class="max-w-[1280px] mx-auto px-6 py-4 text-center text-xs text-slate-500">
        <span class="font-semibold text-slate-700">fastInfo</span> · 个人化 AI 情报中枢 ·
        <a href="/swagger" class="text-emerald-600 hover:underline" target="_blank">Swagger UI</a>
      </div>
    </n-layout-footer>
  </n-layout>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NDropdown, NLayout, NLayoutHeader, NLayoutContent, NLayoutFooter } from 'naive-ui'
import { useAuthStore } from '@/store/auth'
import BrandLogo from '@/components/BrandLogo.vue'

const router = useRouter()
const auth = useAuthStore()

const userMenuOptions = [
  { label: '个人中心', key: 'me' },
  { type: 'divider', key: 'd1' },
  { label: '退出登录', key: 'logout' },
]

function onUserMenu(key: string) {
  console.log('[DEBUG] user menu selected key:', key)
  if (key === 'me') {
    console.log('[DEBUG] navigating to route name: me')
    router.push({ name: 'me' })
  } else if (key === 'logout') {
    auth.logout()
    router.push('/')
  }
}
</script>
