<template>
  <div class="ml-shell">
    <!-- 顶 header - sticky 在视口顶部 -->
    <header class="ml-header">
      <div class="flex items-center gap-2">
        <BrandLogo size="sm" />
      </div>
      <button v-if="auth.isLoggedIn" class="text-sm text-slate-500" @click="logout">退出</button>
    </header>

    <!-- 中间 main - 独立滚动容器 -->
    <div class="ml-main-wrap">
      <main class="ml-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- 底 tab - fixed 视口底部 -->
    <nav class="ml-tabbar">
      <router-link to="/m" class="tab-link" :class="{ 'tab-active': isActive('/m', true) }">
        <Home :size="20" /><span>推荐</span>
      </router-link>
      <router-link to="/m/hot" class="tab-link" :class="{ 'tab-active': isActive('/m/hot') }">
        <Flame :size="20" /><span>热门</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/me/inbox" class="tab-link" :class="{ 'tab-active': isActive('/m/me/inbox') }">
        <Bell :size="20" /><span>推送</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/topics" class="tab-link" :class="{ 'tab-active': isActive('/m/topics') }">
        <Sparkles :size="20" /><span>话题</span>
      </router-link>
      <router-link v-if="auth.isLoggedIn" to="/m/me" class="tab-link" :class="{ 'tab-active': isActive('/m/me', true) }">
        <User :size="20" /><span>我的</span>
      </router-link>
      <router-link v-else to="/m/login" class="tab-link" :class="{ 'tab-active': isActive('/m/login') }">
        <LogIn :size="20" /><span>登录</span>
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
/*
 * 关键策略:
 * - .ml-shell 是外层固定视口容器(100dvh)
 * - header sticky top
 * - .ml-main-wrap flex:1 填充中间, 自己有 overflow:hidden
 * - .ml-main 在 .ml-main-wrap 内 overflow-y:auto, 自己滚动
 * - nav fixed bottom-0, 在视口底部, 永远不消失
 *
 * 这样:
 *   - body 不滚(被 .ml-shell 锁住)
 *   - 只有 main 内部滚
 *   - nav 在 viewport 永远贴底
 */
.ml-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 28rem;
  margin: 0 auto;
  height: 100vh;
  height: 100dvh;       /* iOS 动态视口 */
  background: #f8fafc;
  position: relative;
  overflow: hidden;     /* 关键: 锁住 shell 不让外层滚 */
}

.ml-header {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  height: 56px;        /* 固定 header 高度 */
}

.ml-main-wrap {
  flex: 1 1 0;          /* flex 短语法: grow=1 shrink=1 basis=0 */
  min-height: 0;        /* 关键: 让 flex 子元素允许收缩 */
  overflow: hidden;
  position: relative;
}

.ml-main {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px 16px;   /* 底部 padding 给 nav 让位 */
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}

.ml-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 30;
  display: flex;
  justify-content: space-around;
  padding: 8px 0 max(8px, env(safe-area-inset-bottom));  /* iOS 底部安全区 */
  background: #fff;
  border-top: 1px solid #e2e8f0;
  height: 56px;        /* 固定 tabbar 高度 */
  /* 让 tabbar 在 max-w-md 范围内居中 */
  pointer-events: auto;
}

/* tabbar 在宽屏(<28rem) 也要左右对齐 */
@media (min-width: 28rem) {
  .ml-tabbar {
    /* 中间区域对齐: 用 inset + max-width 模拟居中 */
    max-width: 28rem;
    margin: 0 auto;
    /* 但 fixed 元素 margin auto 不工作, 用 left/right 调整 */
    /* 用 box-shadow 替代边框线 */
    border-left: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
  }
}

.tab-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 10px;
  color: #64748b;
  transition: color 0.15s;
  padding: 2px 12px;
  text-decoration: none;
}
.tab-link:active { transform: scale(0.95); }
.tab-active { color: #10B981 !important; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.12s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>