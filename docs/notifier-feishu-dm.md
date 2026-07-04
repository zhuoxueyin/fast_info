# 飞书个人单聊推送 · feishu_dm 渠道使用指南

> v0.4.0 (Day 7) · 2026-07-04

## 这是什么

订阅触发后,直接推一条**富文本卡片**到你的飞书手机客户端(单聊消息),**不需要加群、不需要建机器人、不需要 webhook URL**。复用 OpenClaw 已经配的同一个飞书 App。

vs `feishu` 渠道(只在群里发)对比:

| 渠道 | 推送目的地 | 配置复杂度 | 适合 |
|---|---|---|---|
| `feishu` | 飞书群(自定义机器人 webhook)| 简单,在群里加 bot 拿 URL | 团队 / 公开群 |
| **`feishu_dm`** | **你的个人飞书(直接单聊)**| **简单,复用已有 App** | **个人订阅、临时话题这种"通知我自己"** |

## 前置条件(一次性,5 min)

### 1. 环境变量

fastInfo 启动时,跟 OpenClaw 用**同一个 App ID + Secret**:

```powershell
# Windows PowerShell
$env:LARK_APP_ID = "cli_xxxxxx"
$env:LARK_APP_SECRET = "xxxxxxxxxxxx"
```

```bash
# Linux / macOS
export LARK_APP_ID=cli_xxxxxx
export LARK_APP_SECRET=xxxxxxxxxxxx
```

> ⚠️ 不需要新建飞书 App。直接用 OpenClaw 已经在用的那个。

### 2. 飞书后台 — App 权限

**飞书开发者后台** → 你的 App → 权限管理 → 找到 **`im:message`**(发送消息)→ 开通。

### 3. 触发激活(一次性)

**第一次必须你主动给 bot 发过任何一条消息** —— 飞书限制应用不能"无端"找用户(否则会报 `230020`)。

打开飞书 → 找到你 OpenClaw 那个 bot(也就是正跟你聊的这个)→ 发一句"激活" → OK,通道就通了。

## 用户侧配置(每用户一次性)

1. 登录 web → `http://127.0.0.1:5173/settings`
2. 在"飞书个人单聊(feishu_dm)"区:
   - **open_id 通常留空就行** = 自动用当前登录用户(也是你跟 OpenClaw 聊天的那个)
   - 如果你想给**别的飞书用户**推(比如家人、朋友的 open_id),手动填 `ou_xxx`
3. 保存。
4. 在表格里点 `feishu_dm` 行的"测试"按钮。
5. 你飞书客户端应**立刻收到一张绿色卡片**(标题"推送通道测试")。

## CLI 验证(无需 Web)

```bash
# 单测 feishu_dm(无 Mongo 也能跑)
LARK_APP_ID=cli_xxx LARK_APP_SECRET=*** python fastinfo.py notify test feishu_dm

# 测全部 5 渠道
python fastinfo.py notify test-all
```

## 订阅里用

创建订阅时 channels 多选 `feishu_dm`:

```bash
curl -X POST http://127.0.0.1:8000/api/subs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nl_query": "每天 9 点看 AI 资讯",
    "channels": ["inbox", "feishu_dm"]
  }'
```

或 Web 端 `/subs/new` 时勾选"飞书个人单聊"。

## 失败排错

| 现象 | 原因 |
|---|---|
| `code 230020` | 你从未给 bot 发过消息 → 给 bot 发任意一条激活 |
| `code 99991663` 或 token 失败 | `LARK_APP_ID` / `LARK_APP_SECRET` 没设 / 错 |
| `code 99991663` + app_id 正确 | App 没有 `im:message` 权限 → 飞书后台开通 |
| `unreachable / connect timeout` | 你 fastInfo server 不能访问 `open.feishu.cn`(可能被公司网拦了)|
| 卡片乱码或被截 | content 超 1800 字 → 已经内置保护,实际推送不会超 |
| 测试一直 False 但 CLI 不报错 | App ID/Secret 是 secret 范畴,写日志时被脱敏看不到,直接看 `LARK_APP_ID` 是否被 export 到 sub-process env |

## 跟 OpenClaw 的关系

- OpenClaw 用**同一个** LARK_APP_ID/SECRET
- OpenClaw 飞书插件已经在 `~/.openclaw/openclaw.json` 里配了这个 App
- 你只需要把 **同一个 App ID + Secret export 到 fastInfo 启动环境** —— 仅一处多设,fastInfo 就能直接发

不需要为 fastInfo 单独建一个新的飞书 App(除非你想做权限隔离)。

---

*Last updated: 2026-07-04 10:07 GMT+8 · Day 7 v0.4.0*
