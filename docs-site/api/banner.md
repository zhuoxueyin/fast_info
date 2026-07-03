# /api/banner · Banner 配置

## GET /api/banner(公开)

获取当前生效的 Banner 类目配置。

**响应 200**

```json
{
  "categories": ["AI", "科技", "财经"],
  "max_per_category": 3,
  "updated_at": "2026-07-02T14:00:28.368000",
  "updated_by": null
}
```

**示例**

```bash
curl http://127.0.0.1:8000/api/banner
```

---

## PUT /api/banner(admin)

更新 Banner 配置。

**Headers**

```
Authorization: Bearer <admin-token>
```

**请求**

```json
{
  "categories": ["AI", "科技", "财经", "汽车"],
  "max_per_category": 3
}
```

**校验**

- `categories`: ≥ 1 个,≤ 5 个
- `max_per_category`: 1-10

**响应 200**

```json
{
  "categories": ["AI", "科技", "财经", "汽车"],
  "max_per_category": 3,
  "updated_at": "2026-07-02T15:00:00Z",
  "updated_by": "admin"
}
```

**错误**

- `403`:非管理员

**示例**

```bash
curl -X PUT http://127.0.0.1:8000/api/banner \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"categories":["AI","科技","财经"],"max_per_category":3}'
```