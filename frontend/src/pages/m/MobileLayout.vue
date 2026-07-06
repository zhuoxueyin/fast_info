<template>
  <div class="min-h-screen bg-slate-50 max-w-md mx-auto pb-20">
    <!-- 顶 header(只在 MobileLayout 自己显示,不在子页面再渲染) -->
    <header class="sticky top-0 bg-white border-b z-20 px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <BrandLogo size="sm" />
      </div>
      <button v-if="auth.isLoggedIn" class="text-sm text-slate-500" @click="logout">退出</button>
    </header>

    <!-- 子路由出口(由 router-view 决定渲染哪个 mobile 页面) -->
    <main class="px-4 py-3">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 底 tab · 5 个核心入口(登录态切换"我的"/"登录") -->
    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around py-2 z-20 max-w-md mx-auto">
      <router-link
        to="/m"
        class="tab-link"
        :class="{ 'tab-active': isActive('/m', true) }"
      >
        <Home :size="20" />
        <span>推荐</span>
      </router-link>
      <router-link
        to="/m/hot"
        class="tab-link"
        :class="{ 'tab-active': isActive('/m/hot') }"
      >
        <Flame :size="20" />
        <span>热门</span>
      </router-link>
      <router-link
        v-if="auth.isLoggedIn"
        to="/m/me/inbox"
        class="tab-link"
        :class="{ 'tab-active': isActive('/m/me/inbox') }"
      >
        <Bell :size="20" />
        <span>推送</span>
      </router-link>
      <router-link
        v-if="auth.isLoggedIn"
        to="/m/topics"
        class="tab-link"
        :class="{ 'tab-active': isActive('/m/topics') }"
      >
        <Sparkles :size="20" />
        <span>话题</span>
      </router-link>
      <router-link
        v-if="auth.isLoggedIn"
        to="/m/me"
        class="tab-link"
        :class="{ 'tab-active': isActive('/m/me', true) }"
      >
        <User :size="20" />
        <span>我的</span>
      </router-link>
      <router-link
        v-else
        to="/m/login"
        class="tab-link"
        :class="{ 'tab-active': isActive('/m/login') }"
      >
        <LogIn :size="20" />
        <span>登录</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Home, Flame, Bell, Sparkles, User, LogIn } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import BrandLogo from '@/components/BrandLogo.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

/**
 * 判断当前 tab 是否高亮
 * - exact=true 表示要精确匹配(用于 /m 和 /m/me)
 * - 否则前缀匹配(用于 /m/hot 匹配 /m/hot/...)
 */
function isActive(path: string, exact = false): boolean {
  if (exact) return route.path === path
  return route.path === path || route.path.startsWith(path + '/')
}

function logout() {
  if (!confirm('确定要退出登录吗?')) return
  auth.logout()
  router.push('/m')
}
</script>

<style scoped>
.tab-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 10px;
  color: #64748b;  /* slate-500 */
  transition: color 0.15s;
  padding: 2px 8px;
}
.tab-link:active {
  transform: scale(0.95);
}
.tab-active {
  color: #10B981 !important;  /* emerald-500 */
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.12s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>