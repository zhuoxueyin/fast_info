import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { detectDevice } from '@/lib/device'

const routes: RouteRecordRaw[] = [
  // ============ Desktop 主路由 ============
  { path: '/', component: () => import('@/pages/HomePage.vue'), name: 'home' },
  { path: '/hot', component: () => import('@/pages/HotPage.vue'), name: 'hot' },
  { path: '/search', component: () => import('@/pages/SearchPage.vue'), name: 'search' },
  { path: '/items/:id', component: () => import('@/pages/ItemDetailPage.vue'), name: 'item-detail', props: true },
  { path: '/login', component: () => import('@/pages/LoginPage.vue'), name: 'login' },
  { path: '/register', component: () => import('@/pages/RegisterPage.vue'), name: 'register' },
  { path: '/me', component: () => import('@/pages/MePage.vue'), name: 'me', meta: { auth: true } },
  { path: '/me/inbox', component: () => import('@/pages/InboxPage.vue'), name: 'inbox', meta: { auth: true } },
  { path: '/me/subs', component: () => import('@/pages/SubsPage.vue'), name: 'subs', meta: { auth: true } },
  { path: '/me/settings', component: () => import('@/pages/SettingsPage.vue'), name: 'settings', meta: { auth: true } },
  { path: '/subs/new', component: () => import('@/pages/NewSubPage.vue'), name: 'sub-new', meta: { auth: true } },
  { path: '/subs/edit/:id', component: () => import('@/pages/NewSubPage.vue'), name: 'sub-edit', meta: { auth: true }, props: true },
  { path: '/me/push-history', component: () => import('@/pages/PushHistoryPage.vue'), name: 'push-history', meta: { auth: true } },
  { path: '/settings', redirect: '/me/settings' },
  { path: '/topic/:tid', component: () => import('@/pages/TopicDetail.vue'), name: 'topic-detail', props: true },
  { path: '/topics', component: () => import('@/pages/TopicsPage.vue'), name: 'topics', meta: { auth: true } },
  // Admin（保留桌面版,不在 mobile 适配范围内）
  { path: '/admin', component: () => import('@/pages/admin/AdminHome.vue'), name: 'admin', meta: { auth: true, admin: true } },
  { path: '/admin/monitoring', component: () => import('@/pages/admin/MonitoringPage.vue'), name: 'admin-monitoring', meta: { auth: true, admin: true } },
  { path: '/admin/tasks', component: () => import('@/pages/admin/TasksPage.vue'), name: 'admin-tasks', meta: { auth: true, admin: true } },
  { path: '/admin/sources', component: () => import('@/pages/admin/SourcesPage.vue'), name: 'admin-sources', meta: { auth: true, admin: true } },
  { path: '/admin/banner', component: () => import('@/pages/admin/BannerConfigPage.vue'), name: 'admin-banner', meta: { auth: true, admin: true } },

  // ============ Mobile /m/* 路由 ============
  { path: '/m', component: () => import('@/pages/m/MobileLayout.vue') },
  { path: '/m/hot', component: () => import('@/pages/m/MobileHot.vue') },
  { path: '/m/search', component: () => import('@/pages/m/MobileSearch.vue') },
  { path: '/m/items/:id', component: () => import('@/pages/m/MobileItem.vue'), props: true },
  { path: '/m/topics', component: () => import('@/pages/m/MobileTopicsPage.vue'), meta: { auth: true } },
  { path: '/m/topic/:tid', component: () => import('@/pages/m/MobileTopicDetail.vue'), props: true },
  { path: '/m/me', component: () => import('@/pages/m/MobileMe.vue'), meta: { auth: true } },
  { path: '/m/me/inbox', component: () => import('@/pages/m/MobileInbox.vue'), meta: { auth: true } },
  { path: '/m/me/subs', component: () => import('@/pages/m/MobileSubs.vue'), meta: { auth: true } },
  { path: '/m/me/settings', component: () => import('@/pages/m/MobileSettings.vue'), meta: { auth: true } },
  { path: '/m/subs/new', component: () => import('@/pages/m/MobileNewSub.vue'), meta: { auth: true } },
  { path: '/m/subs/edit/:id', component: () => import('@/pages/m/MobileNewSub.vue'), meta: { auth: true }, props: true },
  { path: '/m/login', component: () => import('@/pages/m/MobileLogin.vue') },

  // ============ 404 ============
  { path: '/:pathMatch(.*)*', component: () => import('@/pages/NotFoundPage.vue'), name: '404' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

// ============ Guard 1 · 鉴权 ============
router.beforeEach(async (to, _from, next) => {
  if (to.meta?.auth) {
    const token = localStorage.getItem('token')
    if (!token) return next({ path: '/login', query: { redirect: to.fullPath } })
    if (to.meta?.admin) {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      if (user?.role !== 'admin') return next({ path: '/me' })
    }
  }
  next()
})

// ============ Guard 2 · 移动端自适应路由 ============
// 同一访问地址,手机 UA 自动渲染 mobile 版本
// 例: 手机访问 "/" → 跳 "/m"; 桌面访问 "/m" → 跳 "/"
router.beforeEach((to, _from, next) => {
  // 跳过 admin / 404 / 静态资源
  if (to.path.startsWith('/admin') || to.name === '404') return next()
  // 显式 ?desktop=1 强制桌面
  if (to.query.desktop === '1') return next()

  const device = detectDevice()

  if (device === 'mobile' && !to.path.startsWith('/m')) {
    // 手机访问 desktop 路径 → 重定向到 /m 对应路径
    const mobilePath = to.path === '/' ? '/m' : `/m${to.path}`
    // 保留 query / hash
    return next({ path: mobilePath, query: to.query, hash: to.hash, replace: true })
  }

  if (device === 'desktop' && to.path.startsWith('/m')) {
    // 桌面访问 /m/* 路径 → 跳回 desktop 版本
    let desktopPath = to.path.replace(/^\/m/, '') || '/'
    // 处理特殊映射:/m/login → /login; /m/me/* → /me/*; /m/subs/* → /subs/*
    desktopPath = desktopPath.replace(/^\/me\/inbox/, '/me/inbox')
    desktopPath = desktopPath.replace(/^\/me\/subs/, '/me/subs')
    desktopPath = desktopPath.replace(/^\/me\/settings/, '/me/settings')
    desktopPath = desktopPath.replace(/^\/subs\/new/, '/subs/new')
    desktopPath = desktopPath.replace(/^\/subs\/edit\//, '/subs/edit/')
    return next({ path: desktopPath, query: to.query, hash: to.hash, replace: true })
  }

  next()
})

export default router