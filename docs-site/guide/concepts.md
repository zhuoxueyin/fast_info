# 核心概念

## 数据流(三段式)

```
┌──────────────── 抓取侧(管理员视角,跟用户无关) ────────────────┐
│                                                                │
│  scripts/ingest_daemon.py  ──→  src/crawler/rss_collector.py   │
│       (30 min 一轮 / --once)         fetch_all(7 个 RSS 源)    │
│       ↓                                                        │
│  src/llm/model_registry.py  4 级 fallback 摘要                  │
│       ↓                                                        │
│  MongoDB.items (公共库,跨用户共享)                              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────── 用户侧(主进程,跟 user_id 强绑定) ─────────────┐
│                                                                │
│  CLI:  fastinfo.py                                              │
│  API:  src/api/*                                               │
│  Web:  frontend/* (Vue3)                                       │
│                                                                │
│  用户 NL 描述                                                  │
│       ↓  parse_nl_to_subscription()  LLM nl_parse               │
│  MongoDB.subscriptions                                         │
│       ↓  run_subscription(sub)                                 │
│  读 items → keywords 硬过滤 → categories 软 boost              │
│       ↓  跳已推 (subscriptions_delivered)                      │
│  写 subscriptions_delivered (per-user 去重)                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────── 检索侧(支撑所有读路径) ──────────────────────┐
│                                                                │
│  src/retrieval/__init__.py                                     │
│      search / hybrid_search()                                  │
│  v1 = MongoDB text index (title×10 + summary×5 + kp×3)        │
│  v2 留位 = BGE-M3 + LanceDB                                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## 关键术语

| 术语 | 含义 |
|------|------|
| **Item** | 一条被抓取的资讯,包含 url/title/summary/key_points/category/relevance 等 |
| **Subscription** | 用户的订阅,用 NL 描述,后端解析为 cron + 关键词 |
| **Delivered** | 订阅"推送"过的 item 记录,per-user 去重 |
| **NL Query** | 自然语言订阅描述,例:"每天 9 点看 AI 资讯" |
| **Cron 表达式** | 定时规则,5 字段 unix cron |
| **Banner** | 公域首页顶部的类目分组卡片,管理员可配置 |
| **Inbox** | 用户个人推送历史 |
| **Run** | 一次抓取事件,有 run_id + 触发者 + 抓取数 / 失败数 |

## 数据模型(完整)

| 集合 | 作用 | 关键字段 |
|------|------|----------|
| `users` | 用户账号 | username, password_hash, role, plan |
| `items` | 资讯库(公共) | url_hash, title, summary, key_points, category, relevance |
| `subscriptions` | 订阅 | user_id, nl_query, keywords, cron_expr, is_active |
| `subscriptions_delivered` | 推送去重 | subscription_id, item_id(唯一索引) |
| `banner_config` | Banner 配置(单例) | categories, max_per_category |
| `task_runs` | 抓取事件留痕 | run_id, trigger, per_source, llm_breakdown |

## 角色与权限

| 角色 | 注册 | 权限 |
|------|------|------|
| 游客 | 无需 | 公域浏览 / 搜索 / 文档 |
| 普通用户 | 用户名+密码 | + 个人订阅 / 个人推送 / 触发个人抓取 |
| 管理员 | 数据库预置 | + 爬取任务监控 / 全部用户 / Banner 配置 / 全局 ingest |