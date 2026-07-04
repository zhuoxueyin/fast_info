<template>
  <n-layout class="min-h-screen bg-slate-50">
    <n-layout-header bordered class="bg-white shadow-sm">
      <div class="max-w-[1280px] mx-auto px-6 py-3 flex items-center gap-5">
        <router-link to="/" class="text-xl font-bold text-slate-900 flex items-center gap-2 flex-shrink-0">
          <span class="inline-block w-7 h-7 rounded-md bg-emerald-500 text-white text-center leading-7">⚡</span>
          fastInfo
        </router-link>

        <div class="flex-1 max-w-md">
          <n-input
            v-model:value="searchQ"
            size="small"
            placeholder="搜索资讯 / AI / 量子位"
            clearable
            @keyup.enter="goSearch"
            @clear="onSearchClear"
          >
            <template #prefix>
              <span class="text-slate-400">🔍</span>
            </template>
          </n-input>
        </div>

        <nav class="flex items-center gap-4 text-sm flex-shrink-0">
          <router-link to="/hot" class="text-slate-700 hover:text-emerald-600 font-medium">📊 今日排行</router-link>
          <router-link v-if="auth.isLoggedIn" to="/me/inbox" class="text-slate-700 hover:text-emerald-600 font-medium">⭐ 个人关注</router-link>
          <router-link v-if="auth.isLoggedIn" to="/subs/new" class="text-slate-700 hover:text-emerald-600 font-medium">＋ 新订阅</router-link>
          <router-link v-if="auth.isLoggedIn" to="/settings" class="text-slate-700 hover:text-emerald-600 font-medium" title="推送配置(绑定飞书个人 / 邮箱 SMTP / Webhook)">⚙️ 推送</router-link>
        </nav>

        <div class="flex-1"></div>

        <nav class="flex items-center gap-3 text-sm flex-shrink-0">
          <a href="/docs/" target="_blank" class="text-slate-400 hover:text-slate-600 text-xs">📖 文档</a>
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
        fastInfo · 个人化 AI 情报中枢 ·
        <a href="/docs/" class="text-emerald-600 hover:underline" target="_blank">文档</a> ·
        <a href="/swagger" class="text-emerald-600 hover:underline" target="_blank">Swagger UI</a>
      </div>
    </n-layout-footer>
  </n-layout>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NInput, NButton, NDropdown, NLayout, NLayoutHeader, NLayoutContent, NLayoutFooter } from 'naive-ui'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const searchQ = ref('')

watch(() => route.query.q, (v) => {
  const newQ = (v as string) || ''
  if (newQ !== searchQ.value) searchQ.value = newQ
}, { immediate: true })

function goSearch() {
  const q = searchQ.value.trim()
  if (q) {
    router.push({ path: '/search', query: { q } })
  } else {
    router.push({ path: '/' })
  }
}

function onSearchClear() {
  searchQ.value = ''
  if (route.path === '/search') {
    router.push({ path: '/' })
  }
}

const userMenuOptions = [
  { label: '个人中心', key: 'me' },
  { label: '我的推送', key: 'inbox' },
  { label: '创建订阅', key: 'sub_new' },
  { type: 'divider', key: 'd1' },
  { label: '退出登录', key: 'logout' },
]

function onUserMenu(key: string) {
  if (key === 'me') router.push('/me')
  else if (key === 'inbox') router.push('/me/inbox')
  else if (key === 'sub_new') router.push('/subs/new')
  else if (key === 'logout') {
    auth.logout()
    router.push('/')
  }
}
</script>
