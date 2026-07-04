import { ofetch } from 'ofetch'

// 不带 auth header 的基础 fetch
const authFetch = ofetch.create({
  baseURL: '',
  // 拦截器,加 Bearer / 处理 401
  onRequest({ options }) {
    const token = localStorage.getItem('token')
    if (token) {
      options.headers = { ...(options.headers as any || {}), Authorization: `Bearer ${token}` }
    }
  },
  onResponseError({ response }) {
    if (response.status === 401 && !location.pathname.startsWith('/login')) {
      location.href = '/login'
    }
  },
})

export default authFetch

export function api<T = any>(path: string, options: any = {}) {
  const normalizedPath = path.startsWith('/api/')
    ? path
    : `/api${path.startsWith('/') ? path : `/${path}`}`
  return authFetch<T>(normalizedPath, options)
}

// ============================================================
// 日 / 用户 / 订阅
// ============================================================

export async function fetchToday(opts: { limit?: number; category?: string } = {}) {
  const qs = new URLSearchParams()
  if (opts.limit) qs.set('limit', String(opts.limit))
  if (opts.category) qs.set('category', opts.category)
  return authFetch(`/api/today?${qs}`)
}

export async function fetchHot(opts: { limit?: number; hours?: number; threshold?: number } = {}) {
  const qs = new URLSearchParams()
  if (opts.limit) qs.set('limit', String(opts.limit))
  if (opts.hours) qs.set('hours', String(opts.hours))
  if (opts.threshold) qs.set('threshold', String(opts.threshold))
  return authFetch(`/api/hot?${qs}`)
}

export async function searchItems(q: string, limit = 20) {
  return authFetch(`/api/search?q=${encodeURIComponent(q)}&limit=${limit}`)
}

export async function fetchItem(id: string) {
  return authFetch(`/api/items/${id}`)
}

export async function fetchItems(ids: string[]) {
  return authFetch(`/api/items?ids=${ids.join(',')}`)
}

export async function fetchAuthMe() {
  return authFetch('/api/auth/me')
}

export async function login(username: string, password: string) {
  return authFetch('/api/auth/login', { method: 'POST', body: { username, password } })
}

export async function register(username: string, password: string, email?: string) {
  return authFetch('/api/auth/register', { method: 'POST', body: { username, password, email: email || '' } })
}

export async function logout() {
  return authFetch('/api/auth/logout', { method: 'POST' })
}

export async function fetchStats() {
  return authFetch('/api/stats')
}

// ============================================================
// 订阅
// ============================================================

export async function listSubs() {
  return authFetch('/api/subs')
}

export async function createSub(nl_query: string, channels: string[] = ['inbox']) {
  return authFetch('/api/subs', { method: 'POST', body: { nl_query, channels } })
}

export async function runSub(id: string) {
  return authFetch(`/api/subs/${id}/run`, { method: 'POST' })
}

export async function deleteSub(id: string) {
  return authFetch(`/api/subs/${id}`, { method: 'DELETE' })
}

export async function nlPatchSub(id: string, nl_command: string) {
  return authFetch(`/api/subs/${id}/nl-patch`, { method: 'POST', body: { nl_command } })
}

export async function listTopics(opts: { active_only?: boolean } = {}) {
  const qs = opts.active_only === false ? '?active_only=false' : ''
  return authFetch(`/api/topics/list${qs}`)
}

export async function createTopicNow(nl_query: string, max_items = 12, hours = 48) {
  return authFetch('/api/topics/now', { method: 'POST', body: { nl_query, max_items, hours } })
}

// ============================================================
// 推送配置 (Settings + Notifier) - Day 7 v0.4.0/v0.4.1
// ============================================================

export async function getSettings() {
  return authFetch('/api/settings')
}

export async function saveSettings(body: any) {
  return authFetch('/api/settings', { method: 'PUT', body })
}

export async function listNotifierChannels() {
  return authFetch('/api/notifier/channels')
}

export async function testNotifier(channel: string) {
  return authFetch('/api/notifier/test', { method: 'POST', body: { channel } })
}

// 飞书 OAuth
export async function startFeishuBind() {
  return authFetch('/api/auth/feishu/bind') as Promise<{ oauth_url: string; state: string }>
}

export async function getFeishuBindStatus() {
  return authFetch('/api/auth/feishu/status') as Promise<{
    bound: boolean
    open_id?: string | null
    name?: string | null
    email?: string | null
    avatar?: string | null
    bind_at?: string | null
  }>
}

export async function unbindFeishu() {
  return authFetch('/api/auth/feishu/unbind', { method: 'POST' })
}

// ============================================================
// Admin: 数据源 (Day 5)
// ============================================================

export type SourceConfig = {
  source_id: string
  kind: 'rss' | 'weibo_user' | 'x_user' | 'xhs_note' | 'hot_ranking'
  display_name: string
  url?: string
  urls?: string[]
  l1?: string
  tags?: string[]
  cron_interval_seconds?: number
  is_active: boolean
  weight?: number
  limit_per_run?: number
  auto_disable_threshold?: number
  consecutive_fails?: number
  last_success_at?: string | null
  last_fail_at?: string | null
  disabled_reason?: string | null
  created_at?: string
  updated_at?: string
}

export async function listSources(opts: { l1?: string; active_only?: boolean } = {}) {
  const qs = new URLSearchParams()
  if (opts.l1) qs.set('l1', opts.l1)
  if (opts.active_only) qs.set('active_only', 'true')
  return authFetch(`/api/admin/sources${qs.toString() ? '?' + qs : ''}`) as Promise<{ items: SourceConfig[]; total: number }>
}

export async function getSource(source_id: string) {
  return authFetch(`/api/admin/sources/${source_id}`)
}

export async function createSource(body: Partial<SourceConfig>) {
  return authFetch('/api/admin/sources', { method: 'POST', body })
}

export async function updateSource(source_id: string, body: Partial<SourceConfig>) {
  return authFetch(`/api/admin/sources/${source_id}`, { method: 'PATCH', body })
}

export async function deleteSource(source_id: string, hard = false) {
  return authFetch(`/api/admin/sources/${source_id}?hard=${hard}`, { method: 'DELETE' })
}

export async function toggleSource(source_id: string) {
  return authFetch(`/api/admin/sources/${source_id}/toggle`, { method: 'POST' })
}

export async function testSource(source_id: string, limit = 5) {
  return authFetch(`/api/admin/sources/${source_id}/test?limit=${limit}`, { method: 'POST' })
}

export type SourceHealth = {
  source_id: string
  window_days: number
  total_runs: number
  ok_runs: number
  fail_runs: number
  success_rate: number | null
  total_fetched: number
  total_new: number
  total_summarized: number
  total_deduped: number
  avg_duration_ms: number | null
  last_run_at: string | null
  last_status: string | null
  last_error_code: string | null
}

export type SourceHealthSummary = SourceConfig & SourceHealth

export async function getSourceMetrics(source_id: string, window_days = 7) {
  return authFetch(`/api/admin/sources/${source_id}/metrics?window_days=${window_days}`) as Promise<SourceHealth>
}

export async function getHealthSummary(window_days = 1) {
  return authFetch(`/api/admin/sources/health/summary?window_days=${window_days}`) as Promise<{
    window_days: number
    items: SourceHealthSummary[]
    total_sources: number
    active_sources: number
    disabled_sources: number
  }>
}

export async function getSourceRuns(source_id: string, limit = 50) {
  return authFetch(`/api/admin/sources/${source_id}/runs?limit=${limit}`) as Promise<{ items: any[] }>
}
