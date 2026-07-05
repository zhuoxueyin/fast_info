import { ofetch } from 'ofetch'

// 不带 auth header 的基础 fetch
const authFetch = ofetch.create({
  baseURL: '',
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
// 订阅
// ============================================================

export async function parseSub(nl_query: string) {
  return authFetch('/api/subs/parse', { method: 'POST', body: { nl_query } })
}

export async function createSub(body: any) {
  return authFetch('/api/subs', { method: 'POST', body })
}

export async function getSub(id: string) {
  return authFetch(`/api/subs/${id}`)
}

export async function patchSub(id: string, body: any) {
  return authFetch(`/api/subs/${id}`, { method: 'PATCH', body })
}

// ============================================================
// 话题
// ============================================================

export async function createTopicNow(nl_query: string, max_items = 12, hours = 48) {
  return authFetch('/api/topics/now', { method: 'POST', body: { nl_query, max_items, hours } })
}

export async function getTopic(tid: string) {
  return authFetch(`/api/topics/now/${tid}`)
}

export async function convertTopic(tid: string) {
  return authFetch(`/api/topics/now/${tid}/convert`, { method: 'POST' })
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

export async function listSources(opts: { l1?: string; active_only?: boolean } = {}) {
  const qs = new URLSearchParams()
  if (opts.l1) qs.set('l1', opts.l1)
  if (opts.active_only) qs.set('active_only', 'true')
  return authFetch(`/api/admin/sources${qs.toString() ? '?' + qs : ''}`) as Promise<{ items: SourceConfig[]; total: number }>
}

export async function createSource(body: Partial<SourceConfig>) {
  return authFetch('/api/admin/sources', { method: 'POST', body })
}

export async function updateSource(source_id: string, body: Partial<SourceConfig>) {
  return authFetch(`/api/admin/sources/${source_id}`, { method: 'PATCH', body })
}

export async function toggleSource(source_id: string) {
  return authFetch(`/api/admin/sources/${source_id}/toggle`, { method: 'POST' })
}

export async function testSource(source_id: string, limit = 5) {
  return authFetch(`/api/admin/sources/${source_id}/test?limit=${limit}`, { method: 'POST' })
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
