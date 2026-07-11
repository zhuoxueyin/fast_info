export interface Item {
  id: string
  source: string
  source_url?: string
  url: string
  title: string
  summary?: string
  key_points?: string[]
  category?: string
  category_l1?: string
  relevance?: number
  published_at?: string
  fetched_at?: string
  author?: string
  tags?: string[]
  summary_model?: string
}

export interface Subscription {
  id: string
  user_id: string
  title: string
  nl_query?: string
  keywords: string[]
  sources: string[]
  categories: string[]
  categories_l1: string[]
  categories_l2: string[]
  channels: string[]
  /** 本订阅选定的飞书群 name 列表(对应 settings.feishu_webhooks[].name) */
  feishu_targets?: string[]
  cron_expr: string
  interval_min: number
  next_run_at?: string
  last_run_at?: string
  is_active: boolean
  max_items: number
  // Day 9:短期跟踪字段
  track_mode?: 'long' | 'short' | null
  expires_at?: string | null
  duration_days?: number | null
  track_entity?: string | null
}

export interface Topic {
  tid: string
  user_id?: string
  nl_query: string
  title?: string
  parsed: {
    title?: string
    keywords?: string[]
    categories_l1?: string[]
    categories_l2?: string[]
    sources?: string[]
  }
  item_count: number
  created_at: string
  expires_at: string
  converted_to_sub_id?: string | null
}

export interface TopicListItem {
  tid: string
  nl_query: string
  title: string
  item_count: number
  created_at: string
  expires_at: string
  converted_to_sub_id?: string | null
}

export interface InboxItem {
  delivered_at?: string
  subscription_id: string
  subscription_title?: string
  item: Item
}

export interface InboxResponse {
  items: InboxItem[]
  total: number
  page: number
  page_size: number
}

export interface TaskRun {
  run_id: string
  started_at?: string
  finished_at?: string
  trigger: string
  operator?: string | null
  items_fetched: number
  items_summarized: number
  items_failed: number
  per_source: Record<string, { fetched: number; summarized: number; errors: number; latency_ms: number }>
  llm_breakdown: Record<string, Record<string, { calls: number; avg_ms: number }>>
}

export interface SourceStatus {
  source: string
  fetched_24h: number
  failed_24h: number
  last_run_at?: string | null
  last_latency_ms: number
  healthy: boolean
}



export interface BannerConfig {
  categories: string[]
  max_per_category: number
  updated_at?: string | null
  updated_by?: string | null
}

export interface User {
  id: string
  username: string
  role?: 'user' | 'admin'
  plan?: string
  email?: string
  nickname?: string | null         // Day 7:用户昵称,空 → 显示 username
  avatar_url?: string | null       // Day 7:头像 URL,空 → 显示首字母
  feishu_webhook?: string
  feishu_webhooks?: Array<{ name: string; webhook: string }>  // Day 12:多飞书群机器人
  wechat_webhook?: string
  webhook_url?: string
  created_at?: string
  last_login_at?: string
}

export interface Stats {
  total_items: number
  total_users: number
  total_subscriptions: number
  total_delivered: number
  by_source: Array<{ _id: string; count: number }>
  by_category: Array<{ _id: string; count: number }>
  by_user?: Array<{ _id: string; count: number }>
}

export interface SearchResponse {
  total: number
  items: Item[]
}

export interface TodayResponse {
  total: number
  items: Item[]
}

export interface HotResponse {
  total: number
  items: Item[]
}

// Day 9:推送历史
export interface PushChannelResult {
  ok: boolean
  http_status?: number | null
  error?: string | null
}

export interface PushHistoryItem {
  item_id: string
  title: string
  url?: string
  source?: string
}

export interface PushHistoryRecord {
  id: string
  user_id: string
  subscription_id?: string | null
  subscription_title: string
  trigger: 'manual' | 'schedule' | 'test' | 'cli' | 'unknown' | string
  operator: string
  channels_ok: string[]
  channels_fail: string[]
  channel_results: Record<string, PushChannelResult>
  items: PushHistoryItem[]
  item_count: number
  sent_at?: string | null
  duration_ms: number
  error?: string | null
}

export interface PushHistoryListResponse {
  total: number
  items: PushHistoryRecord[]
}

export interface PushHistoryStats {
  total: number
  by_trigger: Record<string, number>
  last_24h: number
}