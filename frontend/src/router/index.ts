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
  // Admin
  { path: '/admin', component: () => import('@/pages/admin/AdminHome.vue'), name: 'admin', meta: { auth: true, admin: true } },
  { path: '/admin/monitoring', component: () => import('@/pages/admin/MonitoringPage.vue'), name: 'admin-monitoring', meta: { auth: true, admin: true } },
  { path: '/admin/tasks', component: () => import('@/pages/admin/TasksPage.vue'), name: 'admin-tasks', meta: { auth: true, admin: true } },
  { path: '/admin/sources', component: () => import('@/pages/admin/SourcesPage.vue'), name: 'admin-sources', meta: { auth: true, admin: true } },
  { path: '/admin/banner', component: () => import('@/pages/admin/BannerConfigPage.vue'), name: 'admin-banner', meta: { auth: true, admin: true } },

  // ============ Mobile 嵌套路由 ============
  // MobileLayout 是父路由,所有 mobile 页面都是它的 children
  // 这样底 tab + 顶 header 持久化,只切换 router-view 内容
  {
    path: '/m',
    component: () => import('@/pages/m/MobileLayout.vue'),
    children: [
      { path: '', component: () => import('@/pages/m/MobileHome.vue'), name: 'm-home' },
      { path: 'hot', component: () => import('@/pages/m/MobileHot.vue'), name: 'm-hot' },
      { path: 'search', component: () => import('@/pages/m/MobileSearch.vue'), name: 'm-search' },
      { path: 'topics', component: () => import('@/pages/m/MobileTopicsPage.vue'), name: 'm-topics', meta: { auth: true } },
      { path: 'topic/:tid', component: () => import('@/pages/m/MobileTopicDetail.vue'), name: 'm-topic-detail', props: true },
      { path: 'me', component: () => import('@/pages/m/MobileMe.vue'), name: 'm-me', meta: { auth: true } },
      { path: 'me/inbox', component: () => import('@/pages/m/MobileInbox.vue'), name: 'm-inbox', meta: { auth: true } },
      { path: 'me/subs', component: () => import('@/pages/m/MobileSubs.vue'), name: 'm-subs', meta: { auth: true } },
      { path: 'me/settings', component: () => import('@/pages/m/MobileSettings.vue'), name: 'm-settings', meta: { auth: true } },
      { path: 'me/push-history', component: () => import('@/pages/m/MobilePushHistory.vue'), name: 'm-push-history', meta: { auth: true } },
      { path: 'subs/new', component: () => import('@/pages/m/MobileNewSub.vue'), name: 'm-sub-new', meta: { auth: true } },
      { path: 'subs/edit/:id', component: () => import('@/pages/m/MobileNewSub.vue'), name: 'm-sub-edit', meta: { auth: true }, props: true },
      { path: 'login', component: () => import('@/pages/m/MobileLogin.vue'), name: 'm-login' },
      { path: 'items/:id', component: () => import('@/pages/m/MobileItem.vue'), name: 'm-item', props: true },
    ],
  },

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
  console.log('[DEBUG GUARD1] to.path=', to.path, 'to.name=', to.name, 'to.meta=', to.meta)
  if (to.meta?.auth) {
    const token = localStorage.getItem('token')
    console.log('[DEBUG GUARD1] token=', token ? 'exists' : 'missing')
    if (!token) {
      console.log('[DEBUG GUARD1] redirect to /login?redirect=', to.fullPath)
      return next({ path: '/login', query: { redirect: to.fullPath } })
    }
    if (to.meta?.admin) {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      if (user?.role !== 'admin') {
        console.log('[DEBUG GUARD1] not admin, redirect to /me')
        return next({ path: '/me' })
      }
    }
  }
  console.log('[DEBUG GUARD1] next()')
  next()
})

// ============ Guard 2 · 移动端自适应路由 ============
// 同一访问地址,手机 UA 自动渲染 mobile 版本
// 例: 手机访问 "/" → 跳 "/m"; 桌面访问 "/m" → 跳 "/"
router.beforeEach((to, _from, next) => {
  console.log('[DEBUG GUARD2] to.path=', to.path, 'to.name=', to.name)
  // 跳过 admin / 404 / 静态资源
  if (to.path.startsWith('/admin') || to.name === '404') {
    console.log('[DEBUG GUARD2] skip admin/404')
    return next()
  }
  // 显式 ?desktop=1 强制桌面
  if (to.query.desktop === '1') {
    console.log('[DEBUG GUARD2] desktop=1, skip')
    return next()
  }

  const device = detectDevice()
  console.log('[DEBUG GUARD2] device=', device)

  // 修正:不能简单用 startsWith('/m'),否则 /me /monitor 等会被误判为 mobile 路径
  const isMobilePath = to.path === '/m' || to.path.startsWith('/m/')

  if (device === 'mobile' && !isMobilePath) {
    // 手机访问 desktop 路径 → 重定向到 /m 对应路径
    const mobilePath = to.path === '/' ? '/m' : `/m${to.path}`
    console.log('[DEBUG GUARD2] mobile redirect to=', mobilePath)
    // 保留 query / hash(过滤掉 desktop=1)
    const { desktop: _, ...restQuery } = to.query as any
    return next({ path: mobilePath, query: restQuery, hash: to.hash, replace: true })
  }

  if (device === 'desktop' && isMobilePath) {
    // 桌面访问 /m/* 路径 → 跳回 desktop 版本
    let desktopPath = to.path === '/m' ? '/' : to.path.replace(/^\/m\//, '/')
    console.log('[DEBUG GUARD2] desktop redirect to=', desktopPath)
    return next({ path: desktopPath, query: to.query, hash: to.hash, replace: true })
  }

  console.log('[DEBUG GUARD2] next()')
  next()
})

export default router