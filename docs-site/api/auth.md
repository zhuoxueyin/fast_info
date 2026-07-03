# /api/auth · 认证

## POST /api/auth/register

注册新用户。

**请求**

```json
{
  "username": "alice",        // 必填,3-20 位
  "password": "p@ssw0rd",     // 必填,≥ 6 位
  "email": "alice@example.com" // 可选
}
```

**响应 200**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": "u_alice",
    "username": "alice",
    "email": "alice@example.com",
    "role": "user",
    "plan": "free",
    "created_at": "2026-07-02T10:00:00Z"
  }
}
```

**错误**

- `400`:用户名已存在 / 密码太弱

**示例**

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"p@ssw0rd"}'
```

---

## POST /api/auth/login

登录获取 JWT。

**请求**

```json
{
  "username": "alice",
  "password": "p@ssw0rd"
}
```

**响应 200**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": "u_alice",
    "username": "alice",
    "role": "user",
    "plan": "free",
    ...
  }
}
```

**错误**

- `401`:用户名或密码错误

**示例**

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"p@ssw0rd"}'
```

---

## GET /api/auth/me

获取当前用户。

**Headers**

```
Authorization: Bearer <token>
```

**响应 200**

```json
{
  "id": "u_alice",
  "username": "alice",
  "role": "user",
  "plan": "free",
  "email": "alice@example.com",
  "created_at": "2026-07-02T10:00:00Z",
  "last_login_at": "2026-07-02T14:30:00Z"
}
```

**错误**

- `401`:token 无效 / 过期

**示例**

```bash
curl http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```