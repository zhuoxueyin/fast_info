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
  cron_expr: string
  interval_min: number
  next_run_at?: string
  last_run_at?: string
  is_active: boolean
  max_items: number
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

export interface SourceConfigItem {
  id: string
  name: string
  kind: 'rss' | 'kol' | string
  url: string
  default_interval_sec: number
  category_l1: string
  enabled: boolean
}

export interface SourceConfigResponse {
  rss: SourceConfigItem[]
  kol: SourceConfigItem[]
  all_enabled: boolean
}

export interface LLMProviderInfo {
  priority: number
  weight: number
  model?: string
  max_tokens?: number
  protocol?: string
}

export interface LLMHealth {
  groups: Record<string, Record<string, LLMProviderInfo>>
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
  feishu_webhook?: string
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