<template>
  <n-layout class="min-h-screen bg-slate-50">
    <n-layout-header bordered class="bg-white shadow-sm">
      <div class="max-w-[1280px] mx-auto px-6 py-3 flex items-center gap-5">
        <router-link to="/" class="flex items-center flex-shrink-0">
          <BrandLogo size="sm" />
        </router-link>

        <nav class="flex items-center gap-4 text-sm flex-shrink-0 ml-6">
          <router-link to="/" class="text-slate-700 hover:text-emerald-600 font-medium">📰 今日简报</router-link>
          <router-link to="/hot" class="text-slate-700 hover:text-emerald-600 font-medium">🏆 冲击榜</router-link>
          <router-link v-if="auth.isLoggedIn" to="/me/inbox" class="text-slate-700 hover:text-emerald-600 font-medium">✉️ 晨报信封</router-link>
          <router-link v-if="auth.isLoggedIn" to="/topics" class="text-slate-700 hover:text-emerald-600 font-medium">📡 情报雷达</router-link>
          <router-link v-if="auth.isLoggedIn" to="/me/subs" class="text-slate-700 hover:text-emerald-600 font-medium">📚 我的频道</router-link>
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
        <!-- App.vue 通过 slot 传入 <router-view />,不要在这里再嵌一层 router-view -->
        <slot />
      </div>
    </n-layout-content>

    <n-layout-footer class="bg-white border-t">
      <div class="max-w-[1280px] mx-auto px-6 py-4 text-center text-xs text-slate-500">
        <span class="font-semibold text-slate-700">fastInfo</span> · 个人化 AI 情报中枢 · 3 分钟刷完今日情报 ·
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
  { label: '我的情报', key: 'me' },
  { type: 'divider', key: 'd1' },
  { label: '退出登录', key: 'logout' },
]

function onUserMenu(key: string) {
  if (key === 'me') {
    router.push({ name: 'me' })
  } else if (key === 'logout') {
    auth.logout()
    router.push('/')
  }
}
</script>
