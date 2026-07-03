# API 总览

> 完整 OpenAPI schema 见 [Swagger UI](http://127.0.0.1:8000/docs) (实时同步)

## 端点速查

### 认证(公开 + Bearer)

| Method | Path | 鉴权 | 说明 |
|---|---|---|---|
| POST | [/api/auth/register](/api/auth) | 公开 | 注册 |
| POST | [/api/auth/login](/api/auth) | 公开 | 登录(返回 JWT) |
| GET  | [/api/auth/me](/api/auth) | Bearer | 当前用户 |

### 资讯(公开)

| Method | Path | 鉴权 | 说明 |
|---|---|---|---|
| GET | [/api/search](/api/items) | 公开 | 全文搜索 |
| GET | [/api/today](/api/items) | 公开 | 最近 N 条 |
| GET | [/api/hot](/api/items) | 公开 | 今日热点 |
| GET | [/api/items?ids=a,b,c](/api/items) | 公开 | 批量查 |
| GET | `/api/items/{id}` | 公开 | 单条详情 |
| GET | `/api/categories` | 公开 | 全部类目 |
| GET | `/api/stats` | 公开 | 库统计 |

### 订阅(Bearer)

| Method | Path | 鉴权 | 说明 |
|---|---|---|---|
| POST | `/api/subs/parse` | Bearer | NL 解析预览(不存) |
| POST | [/api/subs](/api/subs) | Bearer | 创建订阅 |
| GET  | [/api/subs](/api/subs) | Bearer | 列出我的 |
| POST | `/api/subs/{id}/run` | Bearer | 立即跑 |
| PATCH | `/api/subs/{id}` | Bearer | 暂停 / 启用 |
| DELETE | `/api/subs/{id}` | Bearer | 删除 |

### Banner

| Method | Path | 鉴权 | 说明 |
|---|---|---|---|
| GET | [/api/banner](/api/banner) | 公开 | 当前 Banner 配置 |
| PUT | [/api/banner](/api/banner) | admin | 更新 Banner |

### Inbox

| Method | Path | 鉴权 | 说明 |
|---|---|---|---|
| GET | [/api/inbox](/api/inbox) | Bearer | 个人推送历史 |

### 管理员(admin 角色)

| Method | Path | 说明 |
|---|---|---|
| GET | [/api/admin/stats](/api/admin) | 汇总统计 |
| GET | `/api/admin/users` | 全部用户 |
| GET | `/api/admin/subscriptions` | 全部订阅 |
| GET | [/api/admin/tasks/source-status](/api/admin) | 7 源 24h 状态 |
| GET | `/api/admin/tasks/runs?limit=20` | 抓取时间线 |
| GET | `/api/admin/tasks/runs/{run_id}` | 单次明细 |
| GET | `/api/admin/llm/health` | LLM 模型组配置 |
| POST | `/api/admin/ingest/run` | 手动全站抓取 |

## 通用约定

### 请求

- Content-Type: `application/json`
- Bearer token: `Authorization: Bearer <jwt>`

### 响应

- 成功: 200/201 + JSON
- 客户端错误: 400/401/403/404/422 + `{detail: "..."}`
- 服务器错误: 500 + `{detail: "..."}`

### 时间

所有时间字段用 ISO 8601:
```json
"created_at": "2026-07-02T10:00:00.000Z"
"published_at": "2026-07-02T08:30:00+08:00"
```

### 错误处理

```json
// 401
{"detail": "Not authenticated"}

// 403
{"detail": "需要管理员权限"}

// 422(Pydantic validation)
{
  "detail": [
    {"loc": ["body", "password"], "msg": "string too short", "type": "value_error"}
  ]
}
```