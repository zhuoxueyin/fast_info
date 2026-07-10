<template>
  <div class="ml-shell" :class="{ 'ml-shell--immersive': immersive }">
    <!-- 顶 header -->
    <header v-if="!immersive" class="ml-header">
      <div class="flex items-center gap-2 min-w-0">
        <BrandLogo size="sm" />
        <div class="min-w-0">
          <div class="text-[13px] font-semibold text-slate-800 leading-tight truncate">{{ headerTitle }}</div>
          <div class="text-[10px] text-slate-400 leading-tight truncate">{{ headerSub }}</div>
        </div>
      </div>
      <button
        v-if="auth.isLoggedIn"
        class="text-xs text-slate-400 active:text-slate-600 px-2 py-1"
        @click="logout"
      >
        退出
      </button>
      <router-link
        v-else
        to="/m/login"
        class="text-xs font-medium text-emerald-600 px-2 py-1"
      >
        登录
      </router-link>
    </header>

    <!-- 中间 main -->
    <div class="ml-main-wrap">
      <main class="ml-main" :class="{ 'ml-main--immersive': immersive, 'ml-main--flush': flush }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- 底 Tab：今日 / 频道 / 雷达 / 我的 -->
    <nav v-if="!immersive" class="ml-tabbar">
      <router-link to="/m" class="tab-link" :class="{ 'tab-active': isTab('today') }">
        <Newspaper :size="20" stroke-width="2" />
        <span>今日</span>
      </router-link>
      <router-link
        :to="auth.isLoggedIn ? '/m/channels' : '/m/login'"
        class="tab-link"
        :class="{ 'tab-active': isTab('channels') }"
      >
        <Library :size="20" stroke-width="2" />
        <span>频道</span>
      </router-link>
      <router-link
        :to="auth.isLoggedIn ? '/m/radar' : '/m/login'"
        class="tab-link"
        :class="{ 'tab-active': isTab('radar') }"
      >
        <Radar :size="20" stroke-width="2" />
        <span>雷达</span>
      </router-link>
      <router-link
        :to="auth.isLoggedIn ? '/m/me' : '/m/login'"
        class="tab-link"
        :class="{ 'tab-active': isTab('me') }"
      >
        <User :size="20" stroke-width="2" />
        <span>{{ auth.isLoggedIn ? '我的' : '登录' }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Newspaper, Library, Radar, User } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import BrandLogo from '@/components/BrandLogo.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const immersive = computed(() => !!route.meta?.immersive)
const flush = computed(() => !!route.meta?.flush)

const headerTitle = computed(() => {
  const p = route.path
  if (p === '/m' || p === '/m/') return '今日简报'
  if (p.startsWith('/m/channels') || p.startsWith('/m/me/subs')) return '我的频道'
  if (p.startsWith('/m/radar') || p.startsWith('/m/topics')) return '情报雷达'
  if (p.startsWith('/m/hot')) return '冲击榜'
  if (p.startsWith('/m/me/inbox')) return '晨报'
  if (p.startsWith('/m/me/settings')) return '设置'
  if (p.startsWith('/m/me/push-history')) return '推送历史'
  if (p.startsWith('/m/subs')) return '订阅'
  if (p.startsWith('/m/search')) return '搜索'
  if (p.startsWith('/m/me')) return '个人中心'
  if (p.startsWith('/m/login')) return '登录'
  return 'fastInfo'
})

const headerSub = computed(() => {
  const p = route.path
  if (p === '/m' || p === '/m/') return '3 分钟刷完今日情报'
  if (p.startsWith('/m/channels')) return '你的订阅杂志'
  if (p.startsWith('/m/radar')) return '盯人 · 盯事 · 短期跟踪'
  if (p.startsWith('/m/hot')) return '全站热度擂台'
  if (p.startsWith('/m/me/inbox')) return '推送回看台'
  return '个人化 AI 情报中枢'
})

function isTab(name: 'today' | 'channels' | 'radar' | 'me'): boolean {
  const p = route.path
  if (name === 'today') return p === '/m' || p === '/m/' || p.startsWith('/m/hot') || p.startsWith('/m/search')
  if (name === 'channels') return p.startsWith('/m/channels') || p.startsWith('/m/me/subs') || p.startsWith('/m/subs')
  if (name === 'radar') return p.startsWith('/m/radar') || p.startsWith('/m/topics') || p.startsWith('/m/topic')
  if (name === 'me') {
    if (p.startsWith('/m/me/subs')) return false
    return p === '/m/me' || p.startsWith('/m/me/') || p.startsWith('/m/login')
  }
  return false
}

function logout() {
  if (!confirm('确定要退出登录吗?')) return
  auth.logout()
  router.push('/m')
}
</script>

<style scoped>
.ml-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 28rem;
  margin: 0 auto;
  height: 100vh;
  height: 100dvh;
  background: #f1f5f9;
  position: relative;
  overflow: hidden;
}

.ml-shell--immersive {
  background: #0f172a;
}

.ml-header {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  min-height: 56px;
}

.ml-main-wrap {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

.ml-main {
  position: absolute;
  inset: 0;
  padding: 12px 16px calc(72px + env(safe-area-inset-bottom, 0px));
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}

.ml-main--flush {
  padding-left: 0;
  padding-right: 0;
  padding-top: 0;
}

.ml-main--immersive {
  padding: 0;
  background: #0f172a;
}

.ml-tabbar {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 28rem;
  z-index: 30;
  display: flex;
  justify-content: space-around;
  padding: 6px 0 max(8px, env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border-top: 1px solid #e2e8f0;
  min-height: 56px;
  box-sizing: border-box;
}

.tab-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  color: #94a3b8;
  transition: color 0.15s;
  padding: 4px 14px;
  text-decoration: none;
  font-weight: 500;
}
.tab-link:active { transform: scale(0.95); }
.tab-active { color: #10b981 !important; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.12s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
