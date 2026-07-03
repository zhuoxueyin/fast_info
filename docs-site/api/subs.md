# /api/subs · 订阅

> 全部接口需 `Authorization: Bearer <token>`。

## POST /api/subs/parse

NL → 结构化(不存库,预览用)。

**请求**

```json
{
  "nl_query": "每天 9 点看 AI 资讯"
}
```

**响应 200**

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

---

## POST /api/subs

NL → 解析 → 存库。

**请求**

```json
{
  "title": "AI 资讯日报",
  "nl_query": "每天 9 点看 AI 资讯",
  "max_items": 5
}
```

**响应 200**

```json
{
  "sub": {
    "id": "...",
    "title": "AI 资讯日报",
    "keywords": ["AI", ...],
    "sources": [],
    "categories": [],
    "cron_expr": "0 9 * * *",
    "is_active": true,
    "max_items": 5,
    "created_at": "2026-07-02T10:00:00Z"
  },
  "parsed": {
    "keywords": [...],
    "sources": [],
    "categories": [],
    "cron_expr": "0 9 * * *"
  }
}
```

---

## GET /api/subs

列出当前用户的所有订阅。

**响应 200**

```json
{
  "total": 2,
  "items": [
    {
      "id": "...",
      "title": "AI 资讯日报",
      "keywords": ["AI", ...],
      "cron_expr": "0 9 * * *",
      "is_active": true,
      "max_items": 5,
      "created_at": "2026-07-02T10:00:00Z"
    }
  ]
}
```

---

## POST /api/subs/:id/run

立即执行一次(手动触发)。

**响应 200**

```json
{
  "scanned": 30,
  "matched": 8,
  "delivered": 3,
  "items": [
    { "id": "...", "title": "...", "category": "AI", "relevance": 0.9 }
  ]
}
```

---

## PATCH /api/subs/:id

修改订阅(暂停 / 启用 / 改标题等)。

**请求**

```json
{
  "is_active": false,
  "title": "新标题"
}
```

**响应 200**: 更新后的 sub 对象。

---

## DELETE /api/subs/:id

删除订阅。

**响应 200**

```json
{"ok": true}
```
