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

export async function listTopics(activeOnly = true) {
  const qs = activeOnly ? '?active_only=true' : '?active_only=false'
  return authFetch(`/api/topics/list${qs}`) as Promise<{ items: any[]; total: number }>
}

/**
 * 转订阅(Day 9:支持短期 / 长期)
 * @param tid 临时话题 ID
 * @param opts.duration_days 短期跟踪天数(默认 7)
 * @param opts.track_mode 'short' / 'long'(默认 short)
 */
export async function convertTopic(
  tid: string,
  opts: { duration_days?: number; track_mode?: 'short' | 'long' } = {},
) {
  const qs = new URLSearchParams()
  if (opts.duration_days != null) qs.set('duration_days', String(opts.duration_days))
  if (opts.track_mode) qs.set('track_mode', opts.track_mode)
  const url = `/api/topics/now/${tid}/convert${qs.toString() ? '?' + qs : ''}`
  return authFetch(url, { method: 'POST' }) as Promise<{
    converted: boolean
    subscription_id: string
    tid: string
    track_mode?: 'short' | 'long'
    track_entity?: string | null
    idempotent?: boolean
  }>
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

export type RecentRun = {
  run_id: string
  started_at: string
  ended_at: string
  duration_ms: number
  status: 'ok' | 'partial' | 'fail' | 'disabled' | string
  fetched_count: number
  new_count: number
  error_code: string | null
  error_msg: string | null
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
  recent_runs?: RecentRun[]
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

/**
 * 批量启停数据源(Day 6 新增)
 * @returns {ok, updated, skipped[], is_active}
 */
export async function batchToggleSources(source_ids: string[], is_active: boolean) {
  return authFetch('/api/admin/sources/batch-toggle', {
    method: 'POST',
    body: { source_ids, is_active },
  }) as Promise<{ ok: boolean; updated: number; skipped: string[]; is_active: boolean }>
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

// ===== Day 10.5 · 调度策略 API =====

export type ScheduleRow = {
  source_id: string
  display_name: string
  kind: string
  l1: string
  is_active: boolean
  interval_seconds: number
  interval_label: string
  last_run_at: string | null
  next_run_at: string | null
  due_in_seconds: number
  status: string
}

export async function getScheduleOverview() {
  return authFetch('/api/admin/sources/schedule/overview') as Promise<{
    items: ScheduleRow[]
    total_sources: number
    active_scheduled: number
    manual_only: number
    due_now: number
  }>
}

export async function updateSchedule(source_id: string, cron_interval_seconds: number) {
  return authFetch(`/api/admin/sources/${source_id}/schedule`, {
    method: 'POST',
    body: { cron_interval_seconds },
  }) as Promise<{ ok: boolean; source_id: string; cron_interval_seconds: number; label: string }>
}

export async function batchUpdateSchedule(
  source_ids: string[],
  cron_interval_seconds: number
) {
  return authFetch('/api/admin/sources/schedule/batch', {
    method: 'POST',
    body: { source_ids, cron_interval_seconds },
  }) as Promise<{ ok: boolean; updated: number; skipped: string[]; cron_interval_seconds: number }>
}

export async function runSourceNow(source_id: string, limit = 8) {
  return authFetch(`/api/admin/sources/${source_id}/run-now?limit=${limit}`, { method: 'POST' }) as Promise<{
    run_id: string
    status: string
    fetched: number
    summarized: number
    failed: number
    sources_ran: number
  }>
}

// ============================================================
// Day 9: 推送历史
// ============================================================

import type { PushHistoryListResponse, PushHistoryStats, PushHistoryRecord } from '@/types/api'

export async function listPushHistory(opts: {
  limit?: number
  trigger?: string
} = {}) {
  const qs = new URLSearchParams()
  if (opts.limit) qs.set('limit', String(opts.limit))
  if (opts.trigger) qs.set('trigger', opts.trigger)
  return authFetch(`/api/me/push-history${qs.toString() ? '?' + qs : ''}`) as Promise<PushHistoryListResponse>
}

export async function getPushHistory(id: string) {
  return authFetch(`/api/me/push-history/${id}`) as Promise<PushHistoryRecord>
}

export async function getPushHistoryStats() {
  return authFetch('/api/me/push-history-stats') as Promise<PushHistoryStats>
}
