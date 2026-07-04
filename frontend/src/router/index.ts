import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
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
  // 兼容旧路由重定向
  { path: '/settings', redirect: '/me/settings' },
  { path: '/topic/:tid', component: () => import('@/pages/TopicDetail.vue'), name: 'topic-detail', props: true },
  { path: '/m/topic/:tid', component: () => import('@/pages/m/MobileTopicDetail.vue'), name: 'mobile-topic-detail', props: true },
  { path: '/admin', component: () => import('@/pages/admin/AdminHome.vue'), name: 'admin', meta: { auth: true, admin: true } },
  { path: '/admin/tasks', component: () => import('@/pages/admin/TasksPage.vue'), name: 'admin-tasks', meta: { auth: true, admin: true } },
  { path: '/admin/sources', component: () => import('@/pages/admin/SourcesPage.vue'), name: 'admin-sources', meta: { auth: true, admin: true } },
  { path: '/admin/banner', component: () => import('@/pages/admin/BannerConfigPage.vue'), name: 'admin-banner', meta: { auth: true, admin: true } },
  // ====== 移动端 /m ======
  { path: '/m', component: () => import('@/pages/m/MobileLayout.vue') },
  { path: '/m/hot', component: () => import('@/pages/m/MobileHot.vue') },
  { path: '/m/items/:id', component: () => import('@/pages/m/MobileItem.vue'), props: true },
  { path: '/m/me', component: () => import('@/pages/m/MobileMe.vue') },
  { path: '/m/me/inbox', component: () => import('@/pages/m/MobileInbox.vue') },
  { path: '/m/me/subs', component: () => import('@/pages/m/MobileSubs.vue') },
  { path: '/m/login', component: () => import('@/pages/m/MobileLogin.vue') },
  { path: '/:pathMatch(.*)*', component: () => import('@/pages/NotFoundPage.vue'), name: '404' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

// 鉴权 guard
router.beforeEach(async (to, _from, next) => {
  if (!to.meta?.auth) return next()
  const token = localStorage.getItem('token')
  if (!token) return next({ path: '/login', query: { redirect: to.fullPath } })
  if (to.meta?.admin) {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (user?.role !== 'admin') return next({ path: '/me' })
  }
  next()
})

export default router