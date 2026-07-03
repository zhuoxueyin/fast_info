# /api/inbox · 个人推送历史

## GET /api/inbox

**Headers**

```
Authorization: Bearer <token>
```

**Query**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `sort` | string | `relevance` | `relevance` / `time` |
| `subscription` | string | - | 按订阅 ID 过滤 |
| `category` | string | - | 按类目过滤 |
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 1-100 |

**响应 200**

```json
{
  "items": [
    {
      "delivered_at": "2026-07-02T10:00:00Z",
      "subscription_id": "...",
      "subscription_title": "AI 资讯日报",
      "item": {
        "id": "...",
        "title": "...",
        "summary": "...",
        "category": "AI",
        "source": "qbitai",
        "url": "https://...",
        "relevance": 0.92,
        "published_at": "2026-07-02T08:30:00Z",
        "tags": ["LLM", "GPT"]
      }
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

**示例**

```bash
# 按热度
curl "http://127.0.0.1:8000/api/inbox?sort=relevance" \
  -H "Authorization: Bearer $TOKEN"

# 按类目 + 时间
curl "http://127.0.0.1:8000/api/inbox?sort=time&category=AI&page=1" \
  -H "Authorization: Bearer $TOKEN"

# 按订阅 ID
curl "http://127.0.0.1:8000/api/inbox?subscription=6789abcdef" \
  -H "Authorization: Bearer $TOKEN"
```