# NL 订阅

## 概述

fastInfo 用 **自然语言 → 结构化** 的方式让用户创建订阅。输入"每天 9 点看 AI 资讯",后端用 LLM 解析为:

```json
{
  "title": "AI 资讯日报",
  "keywords": ["AI", "人工智能", "LLM", "GPT"],
  "cron_expr": "0 9 * * *",
  "max_items": 5
}
```

## 支持的 NL 模式

| NL 描述 | 解析结果 |
|---|---|
| "每天 9 点看 AI 资讯" | cron: `0 9 * * *`, keywords: `[AI, ...]` |
| "工作日早上 8 点" | cron: `0 8 * * 1-5` |
| "每周三下午 3 点" | cron: `0 15 * * 3` |
| "每天傍晚 6 点" | cron: `0 18 * * *`(默认 hour=18) |
| "每 30 分钟" | cron: `*/30 * * * *` |
| "周末晚上 8 点" | cron: `0 20 * * 0,6` |

解析失败时,**兜底**:用 NL 文本前 15 字做 title,提取前 5 个中文 / 英文词做 keywords,cron 默认 `0 9 * * *`。

## API

### NL 解析预览(不存库)

```http
POST /api/subs/parse
Authorization: Bearer <token>
Content-Type: application/json

{
  "nl_query": "每天 9 点看 AI 资讯"
}
```

返回:

```json
{
  "title": "AI 资讯日报",
  "keywords": ["AI", "人工智能", "LLM"],
  "sources": [],
  "categories": [],
  "cron_expr": "0 9 * * *",
  "max_items": 5,
  "nl_query": "每天 9 点看 AI 资讯",
  "fallback": false
}
```

### 创建订阅(解析 + 存库)

```http
POST /api/subs
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "AI 资讯日报",            // 可选,会从 NL 自动生成
  "nl_query": "每天 9 点看 AI 资讯",
  "max_items": 5
}
```

返回:

```json
{
  "sub": {
    "id": "...",
    "title": "AI 资讯日报",
    "keywords": ["AI", ...],
    "cron_expr": "0 9 * * *",
    "is_active": true,
    ...
  },
  "parsed": {
    "keywords": [...],
    "sources": [],
    "categories": [],
    "cron_expr": "0 9 * * *"
  }
}
```

### 列出我的订阅

```http
GET /api/subs
Authorization: Bearer <token>
```

### 立即跑

```http
POST /api/subs/{id}/run
Authorization: Bearer <token>
```

返回:

```json
{
  "scanned": 30,      // 看 lookback 窗口内多少 items
  "matched": 8,       // 关键词命中多少
  "delivered": 3,     // 实际推送多少(去重后)
  "items": [...]      // 推送的 items 简略
}
```

### 暂停 / 启用

```http
PATCH /api/subs/{id}
Authorization: Bearer <token>
Content-Type: application/json

{"is_active": false}
```

### 删除

```http
DELETE /api/subs/{id}
Authorization: Bearer <token>
```

## 定时执行

⚠️ 当前需要手动跑(CLI `fastinfo.py subs run <id>` 或 API `/api/subs/{id}/run`)。
Day 3.0 计划加 `subs_scheduler.py` daemon,根据 `next_run_at` 自动触发。

## Cron 表达式

简化版 cron(5 字段),支持:

- `*` 任意
- `*/N` 每 N
- `N-M` 范围
- `N,M,K` 列表
- `@hourly` `@daily` `@weekly` 别名

不支持秒级;不支持 `L` / `W` / `#` 高级字段。

例:`0 9 * * 1-5` = 工作日早上 9 点。