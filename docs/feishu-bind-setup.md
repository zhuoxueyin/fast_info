# 飞书 OAuth 单聊绑定 · 一次性配置指南

> v0.4.1 (Day 7) · 2026-07-04
>
> **解决"用户手填 open_id 太底层"问题** —— 改为 OAuth 一键授权。

## 是什么

用户在 fastInfo Web → `/settings` 点 **"🔵 绑定飞书账号"** 按钮 → 跳到飞书 → 用户点"同意" → 飞书自动调 fastInfo 回调 → 写到 `user.feishu_open_id` → 完成。

**用户视角完全无 ID 操作**:1 点 + 1 同意 = 绑定完成。

## 一次性配置(飞书开发者后台)

约 5 分钟。

### 1. 给 App 加 OAuth scope

**开发者后台** → 你的 App → 权限管理 → 找到并开通:

| scope | 拿什么 |
|---|---|
| `contact:user.id:basic` | open_id / union_id / name / email |
| `contact:user.employee_id:basic` | employee_id(可选) |

### 2. 配置 OAuth redirect_uri

**开发者后台** → 你的 App → 安全设置 → **重定向 URL**(或类似名字)

添加:
```
http://127.0.0.1:8000/api/auth/feishu/callback
https://your-prod-domain/api/auth/feishu/callback    # 生产环境
```

### 3. 启用 App Bot 能力(可选,群聊要用)

**开发者后台** → 你的 App → 应用能力 → **机器人** → 启用

启用后 App 变成"Bot",可以被群添加为成员。

### 4. (可选)App Bot 事件订阅(用于自动接收群邀请)

**开发者后台** → 你的 App → 事件订阅 → 选择 **"使用 长连接 / Webhook 订阅"** → **Webhook 方式** → URL 填:
```
http://127.0.0.1:8000/api/feishu/event
```

订阅事件勾选:
- `im.chat.member.bot.added_v1`  ← bot 被加入群
- `im.chat.member.bot.deleted_v1` ← bot 被踢出群

> ⚠️ 这一步给"群聊自动感知"用(Phase 2),本次 v0.4.1 单聊可用,**群聊下次推**。

## 环境变量

fastInfo 启动时:

```powershell
$env:LARK_APP_ID = "cli_xxxxxx"
$env:LARK_APP_SECRET = "***"
$env:FEISHU_REDIRECT_URI = "http://127.0.0.1:8000/api/auth/feishu/callback"   # 可选,默认就是这个
```

## 用户使用流程

1. 登录 web → `/settings`
2. 在最上面"🧜‍ 飞书绑定 (OAuth)"区点 **"🔵 绑定飞书账号"**
3. 浏览器跳到 `open.feishu.cn` 飞书授权页面
4. 选你的飞书身份 → 同意"基础身份"授权
5. 飞书跳回 fastInfo `/settings`
6. 看到 **"✓ 已绑定"** + 用户名 + 头像 + open_id(后端存) → 绑定完成
7. `feishu_dm` 自动加进默认推送渠道
8. 在"飞书个人单聊"区点"测试"按钮 → 你飞书收到卡片 ✅

## 后续影响

- `feishu_dm` 渠道不再要求手填 `feishu_open_id` —— 自动从绑定状态读
- 单次点击绑定,**永久**(除非手动解绑)
- 解绑:`/settings` → "解绑" 按钮 → 清字段
- 多用户:每个用户**各自独立绑定**,互不干扰

## 独立性原则(fastInfo ≠ OpenClaw 子系统)

fastInfo 是独立产品,可独立部署到 ECS / 独立域名。**任何能力不能假设背后有 OpenClaw runtime**。

### 设计原则(不踩坑)

1. 任何 OAuth 流程 fastInfo **自写后端**，不假设背后有 OAuth provider
2. 任何 HTTP 调飞书 fastInfo **自持 LARK_APP_ID/SECRET**，不走 OpenClaw 中转
3. 任何事件接收 fastInfo **自端 webhook 端点**(不靠 OpenClaw forward)
4. 用户身份走 fastInfo **自的 users 集合 + JWT**，不靠 OpenClaw 的 sender_id
5. 后台 daemon (ingest_daemon, subs_scheduler) **fastInfo 自跑进程**，systemd 可托管

### 独立部署 checklist

前上 ECS 生产前过一遍:

- [ ] fastInfo 公网 HTTPS 域名 + 证书(如 Cloudflare 反代)
- [ ] 飞书后台 OAuth 重定向 URL 加 **公网版本**(只能填 https://)
- [ ] 飞书后台 App 权限开通:
  - `contact:user.id:basic` (OAuth 用)
  - `im:message` (推送用)
  - `im:message.group_at_message` (群聊 Bot 用)
- [ ] **独立 LARK_APP_ID/SECRET** 推荐(可与 OpenClaw 同 App,但生产隔离则新 App)
- [ ] `FEISHU_REDIRECT_URI` env 填公网: `https://fastinfo.your.com/api/auth/feishu/callback`
- [ ] (群聊阶段)Webhook 事件 URL: `https://fastinfo.your.com/api/feishu/event`(需公网，**不能 localhost**)
- [ ] systemd unit 拉起 `/opt/fast_info/.venv/bin/python scripts/ingest_daemon.py` + `api_server.py`
- [ ] nginx/cloudflare 反代配路径:`/api/*` -> `127.0.0.1:8000`
- [ ] SSL 证书 + https-only
- [ ] 独立 MongoDB 连接(腾讯云 MongoDB 4C4G,见 ADR-014)

### 独立性自测 (每生产部署完,跑一遍)

```
>>> 关掉 OpenClaw:
>>> systemctl --user stop openclaw

>>> 只起 fastInfo:
>>> systemctl --user start fastinfo-api fastinfo-ingest fastinfo-scheduler

>>> 验证推送:
$ curl -X POST http://127.0.0.1:8000/api/auth/login ...
$ curl -X POST http://127.0.0.1:8000/api/notifier/test \
    -H "Authorization: Bearer $TOKEN" -d '{"channel":"feishu_dm"}'
>>> 飞书收到卡片? = fastInfo 独立推送 OK

>>> 验证 OAuth:
$ open browser http://localhost:8000/settings
>>> 点绑定飞书 → 跳转飞书 → 同意 → 回 /settings ✓ = OK

>>> 验证事件接收(群 Bot 阶段):
>>> 在生产 ECS 上 fastInfo 启动时,飞书后台应看到 webhook 调用记录
```

⚠️ 如果某一项独立能失败,fastInfo 就有 OpenClaw 耦合 — 需要重构!

## 当前 vs 下一步

| | 本 v0.4.1 | 下一步(v0.4.2) |
|---|---|---|
| 单聊 | OAuth 1-键绑定 ✅ | — |
| 群聊 | 仍 webhook URL(未变) | App Bot 事件 + 自动感知群 |

---

*Last updated: 2026-07-04 10:25 GMT+8*
