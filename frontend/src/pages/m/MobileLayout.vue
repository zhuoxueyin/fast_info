<template>
  <div class="ml-shell">
    <!-- 顶 header -->
    <header class="ml-header">
      <div class="flex items-center gap-2">
        <BrandLogo size="sm" />
      </div>
      <button v-if="auth.isLoggedIn" class="text-sm text-slate-500" @click="logout">退出</button>
    </header>

    <!-- 子路由出口 -->
    <main class="ml-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 底 tab - 用 fixed bottom-0, 不随内容滚走 -->
    <nav class="ml-tabbar">
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
/* 外壳: 全屏, 内容用 flex 布局, header 固定高度, main 自适应, nav 固定底部 */
.ml-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 28rem;   /* max-w-md = 448px */
  margin: 0 auto;
  min-height: 100vh;
  min-height: 100dvh;   /* iOS Safari 兼容, 动态视口高度 */
  background: #f8fafc;  /* bg-slate-50 */
  position: relative;
}

/* 顶 header: sticky 顶部 */
.ml-header {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;  /* slate-200 */
  flex-shrink: 0;
}

/* 中间 main: flex-1 自动填充 */
.ml-main {
  flex: 1 1 auto;
  padding: 12px 16px;
  overflow-y: auto;
  /* 关键: 给 main 自己一个滚动容器, 而不是 window 滚 */
  /* 这样 fixed 底 tab 永远不会消失 */
  -webkit-overflow-scrolling: touch;
}

/* 底 tab: fixed bottom-0 */
.ml-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 30;
  display: flex;
  justify-content: space-around;
  padding: 8px 0;
  background: #fff;
  border-top: 1px solid #e2e8f0;
  /* 关键: 配合 max-w-md 的视觉宽度, 用 padding 模拟居中 */
  /* 但 fixed 元素无法被父 max-w 约束, 所以用 inset + box-shadow 边界 */
}

/* tab 项样式 */
.tab-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 10px;
  color: #64748b;  /* slate-500 */
  transition: color 0.15s;
  padding: 2px 12px;
}
.tab-link:active {
  transform: scale(0.95);
}
.tab-active {
  color: #10B981 !important;
}

/* fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.12s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 大屏(narrower): 不限制 max-w, 让 tabbar 全宽 */
@media (min-width: 28rem) {
  .ml-shell {
    box-shadow: 0 0 0 1px #e2e8f0;
  }
}
</style>