# /api · 资讯(公开读取)

## GET /api/search

全文搜索(MongoDB text index,中文效果一般)。

**Query**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `q` | string | 必填 | 搜索词 |
| `limit` | int | 20 | 返回条数 |

**响应 200**

```json
{
  "total": 3,
  "items": [
    {
      "id": "...",
      "title": "...",
      "summary": "...",
      "category": "AI",
      "source": "qbitai",
      "url": "https://...",
      "relevance": 0.85,
      "published_at": "2026-07-02T08:30:00Z"
    }
  ]
}
```

**示例**

```bash
curl "http://127.0.0.1:8000/api/search?q=AI&limit=5"
```

---

## GET /api/today

最近 N 条资讯。

**Query**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 20 | |
| `source` | string | - | 按源过滤 |
| `category` | string | - | 按类目过滤 |

**响应 200**

```json
{
  "total": 30,
  "items": [...]
}
```

**示例**

```bash
curl "http://127.0.0.1:8000/api/today?limit=10&source=ithome"
```

---

## GET /api/hot

今日热点(按 relevance + published_at 排序)。

**Query**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 20 | |
| `hours` | int | 24 | 时间窗口 |
| `threshold` | float | 0.7 | relevance 下限 |
| `category` | string | - | 按类目过滤 |

**响应 200**

```json
{
  "total": 5,
  "items": [...]
}
```

**示例**

```bash
curl "http://127.0.0.1:8000/api/hot?limit=10&category=AI"
```

---

## GET /api/items?ids=...

批量查(逗号分隔 id)。

**Query**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ids` | string | 是 | 逗号分隔的 item id |

**响应 200**

```json
[ { ...item1 }, { ...item2 } ]
```

**示例**

```bash
curl "http://127.0.0.1:8000/api/items?ids=abc,def,ghi"
```

---

## GET /api/items/{id}

单条详情。

**路径参数**

- `id` - item id

**响应 200**: 单个 item 对象。

**错误**

- `404`:item 不存在

---

## GET /api/categories

items.category 的 distinct 列表。

**响应 200**

```json
{"categories": ["AI", "科技", "财经", ...]}
```

---

## GET /api/stats

库统计。

**响应 200**

```json
{
  "total_items": 49,
  "collections": {...},
  "indexes": {...}
}
```