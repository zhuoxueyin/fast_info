# /api/admin · 管理员接口

> ⚠️ 全部接口需要 **admin 角色**(`scripts/init_admin.py` 创建)
> Headers: `Authorization: Bearer <admin-token>`

## GET /api/admin/stats

汇总统计。

**响应 200**

```json
{
  "total_items": 49,
  "total_users": 13,
  "total_subscriptions": 15,
  "total_delivered": 10,
  "by_source": [
    {"_id": "ithome", "count": 9},
    {"_id": "36kr", "count": 8}
  ],
  "by_category": [
    {"_id": "AI", "count": 12},
    {"_id": "科技", "count": 7}
  ],
  "by_user": [
    {"_id": "u_alice", "count": 5}
  ]
}
```

---

## GET /api/admin/users

全部用户(不含 password_hash)。

**响应 200**

```json
{
  "total": 13,
  "items": [
    {
      "id": "u_alice",
      "username": "alice",
      "email": "alice@example.com",
      "role": "user",
      "plan": "free",
      "created_at": "2026-07-02T10:00:00Z",
      "last_login_at": "2026-07-02T14:30:00Z"
    }
  ]
}
```

---

## GET /api/admin/subscriptions

全部用户的全部订阅。

**响应 200**

```json
{
  "total": 15,
  "items": [
    {
      "id": "...",
      "user_id": "u_alice",
      "title": "AI 资讯日报",
      "nl_query": "每天 9 点看 AI 资讯",
      "keywords": ["AI"],
      "categories": [],
      "cron_expr": "0 9 * * *",
      "is_active": true,
      "run_count": 3,
      "error_count": 0
    }
  ]
}
```

---

## GET /api/admin/tasks/source-status

7 个 RSS 源 24h 抓取状态。

**响应 200**

```json
[
  {
    "source": "ithome",
    "fetched_24h": 9,
    "failed_24h": 0,
    "last_run_at": "2026-07-02T14:30:00Z",
    "last_latency_ms": 1200,
    "healthy": true
  },
  ...
]
```

---

## GET /api/admin/tasks/runs?limit=20

抓取时间线。

**Query**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 20 | 1-100 |

**响应 200**

```json
[
  {
    "run_id": "uuid-...",
    "started_at": "2026-07-02T14:30:00Z",
    "finished_at": "2026-07-02T14:30:15Z",
    "trigger": "scheduled",
    "operator": null,
    "items_fetched": 30,
    "items_summarized": 28,
    "items_failed": 2,
    "per_source": {
      "ithome": {"fetched": 5, "summarized": 5, "errors": 0, "latency_ms": 1200}
    },
    "llm_breakdown": {}
  }
]
```

**trigger 取值**

- `scheduled` - daemon 定时
- `manual_api` - 用户手动 `/api/ingest/run`
- `manual_admin` - 管理员 `/api/admin/ingest/run`
- `subs_run` - 跑订阅触发

---

## GET /api/admin/tasks/runs/{run_id}

单次抓取明细。

**路径参数**

- `run_id` - uuid

**错误**

- `404`:run_id 不存在

---

## GET /api/admin/llm/health

LLM 模型组 × provider 配置。

**响应 200**

```json
{
  "groups": {
    "short_summary": {
      "m2_7_highspeed": {
        "priority": 1,
        "weight": 1,
        "model": "MiniMax-M2.7-highspeed",
        "max_tokens": 600,
        "protocol": "openai"
      },
      "m2_7": {"priority": 2, ...},
      "m3": {"priority": 3, ...},
      "k2_6": {"priority": 4, ..., "protocol": "anthropic"}
    },
    "long_summary": {...},
    "deep_interpretation": {...},
    "nl_parse": {...}
  }
}
```

---

## POST /api/admin/ingest/run?limit=8

手动触发全站抓取(同步等结果,会真调 LLM,可能 1-3 分钟)。

**Query**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 8 | 1-30,每源最多条数 |

**响应 200**

```json
{
  "run_id": "uuid-...",
  "started_at": "2026-07-02T15:00:00Z",
  "finished_at": "2026-07-02T15:00:45Z",
  "items_fetched": 30,
  "items_summarized": 28,
  "items_failed": 2
}
```

**示例**

```bash
curl -X POST "http://127.0.0.1:8000/api/admin/ingest/run?limit=10" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```