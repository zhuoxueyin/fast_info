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
  // IA: 今日 / 频道 / 雷达 / 我的（ZAKER 杂志感 + AI 情报中枢）
  {
    path: '/m',
    component: () => import('@/pages/m/MobileLayout.vue'),
    children: [
      { path: '', component: () => import('@/pages/m/MobileHome.vue'), name: 'm-home' },
      { path: 'hot', component: () => import('@/pages/m/MobileHot.vue'), name: 'm-hot' },
      { path: 'search', component: () => import('@/pages/m/MobileSearch.vue'), name: 'm-search' },
      // 频道 = 订阅杂志
      { path: 'channels', component: () => import('@/pages/m/MobileChannels.vue'), name: 'm-channels', meta: { auth: true } },
      // 雷达 = 临时话题 + 短期跟踪
      { path: 'radar', component: () => import('@/pages/m/MobileRadar.vue'), name: 'm-radar', meta: { auth: true } },
      // 兼容旧路径
      { path: 'topics', redirect: '/m/radar' },
      { path: 'topic/:tid', component: () => import('@/pages/m/MobileTopicDetail.vue'), name: 'm-topic-detail', props: true },
      { path: 'me', component: () => import('@/pages/m/MobileMe.vue'), name: 'm-me', meta: { auth: true } },
      { path: 'me/inbox', component: () => import('@/pages/m/MobileInbox.vue'), name: 'm-inbox', meta: { auth: true } },
      { path: 'me/subs', redirect: '/m/channels' },
      { path: 'me/settings', component: () => import('@/pages/m/MobileSettings.vue'), name: 'm-settings', meta: { auth: true } },
      { path: 'me/push-history', component: () => import('@/pages/m/MobilePushHistory.vue'), name: 'm-push-history', meta: { auth: true } },
      { path: 'subs/new', component: () => import('@/pages/m/MobileNewSub.vue'), name: 'm-sub-new', meta: { auth: true } },
      { path: 'subs/edit/:id', component: () => import('@/pages/m/MobileNewSub.vue'), name: 'm-sub-edit', meta: { auth: true }, props: true },
      { path: 'login', component: () => import('@/pages/m/MobileLogin.vue'), name: 'm-login' },
      // 沉浸阅读：隐藏底 tab + 顶 header
      {
        path: 'items/:id',
        component: () => import('@/pages/m/MobileItem.vue'),
        name: 'm-item',
        props: true,
        meta: { immersive: true },
      },
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
  if (to.meta?.auth) {
    const token = localStorage.getItem('token')
    if (!token) {
      return next({ path: '/login', query: { redirect: to.fullPath } })
    }
    if (to.meta?.admin) {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      if (user?.role !== 'admin') {
        return next({ path: '/me' })
      }
    }
  }
  next()
})

// ============ Guard 2 · 移动端自适应路由 ============
// 同一访问地址,手机 UA 自动渲染 mobile 版本
// 例: 手机访问 "/" → 跳 "/m"; 桌面访问 "/m" → 跳 "/"
router.beforeEach((to, _from, next) => {
  // 跳过 admin / 404 / 静态资源
  if (to.path.startsWith('/admin') || to.name === '404') {
    return next()
  }
  // 显式 ?desktop=1 强制桌面
  if (to.query.desktop === '1') {
    return next()
  }

  const device = detectDevice()

  // 修正:不能简单用 startsWith('/m'),否则 /me /monitor 等会被误判为 mobile 路径
  const isMobilePath = to.path === '/m' || to.path.startsWith('/m/')

  if (device === 'mobile' && !isMobilePath) {
    // 手机访问 desktop 路径 → 重定向到 /m 对应路径
    const mobilePath = to.path === '/' ? '/m' : `/m${to.path}`
    // 保留 query / hash(过滤掉 desktop=1)
    const { desktop: _, ...restQuery } = to.query as any
    return next({ path: mobilePath, query: restQuery, hash: to.hash, replace: true })
  }

  if (device === 'desktop' && isMobilePath) {
    // 桌面访问 /m/* 路径 → 跳回 desktop 版本
    // 部分 mobile 专属路由需要映射到桌面等价页
    const MOBILE_DESKTOP_MAP: Record<string, string> = {
      '/m': '/',
      '/m/channels': '/me/subs',
      '/m/radar': '/topics',
    }
    let desktopPath =
      MOBILE_DESKTOP_MAP[to.path] ||
      (to.path === '/m' ? '/' : to.path.replace(/^\/m\//, '/'))
    if (desktopPath.startsWith('//')) desktopPath = desktopPath.replace(/^\/+/, '/')
    return next({ path: desktopPath, query: to.query, hash: to.hash, replace: true })
  }

  next()
})

export default router