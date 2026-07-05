# fastInfo · Day 7 交付
日期:2026-07-05 · 状态:✅ 完成(订阅链路一致性)

## 🎯 目标
用户的三个痛点,本次聚焦其中两个(订阅保存 + 渠道一致性),F(头像/昵称/订阅编辑)暂缓:

> "我创建订阅已经勾选了飞书,但运行没推过去。Settings 没配邮箱但订阅能勾邮件,两边不一致。"

→ 把"渠道配置"做成单一真实来源:settings 没配的渠道,在订阅页压根不出现。

## ✅ 5 件事

### 1. 找到保存链路的"假 bug"
**实测真相**:API 链路本身没坏。用脚本 `_day7_regress.py` 模拟"前端勾了 ['inbox','feishu'] 传过来" → 入库就是 `['inbox','feishu']`。
**真根因**:
- 后端 settings 的 `default_channels`(`['inbox','feishu']`)和**订阅自己的 channels** 是两套独立字段
- `run_subscription` 读的是订阅自身的 channels,完全不管用户全局默认
- 老订阅没有 channels 字段,跑的时候就只走 inbox 默认
- Mongo 里 4 条订阅 channels 是 `[]` / `['inbox']`,跟用户配的飞书无关 → 点了运行当然收不到飞书消息

### 2. 后端做"渠道一致性"single source of truth
**`src/api/routes/settings.py`**:
- 抽出 helper `_available_channels(user)`,根据 settings 单字段配齐状态算出可用渠道
- `GET /api/notifier/channels` 改成鉴权(原公开)+ 每渠道 `available: bool` + `default_channels: [...]` 字段
- CHANNEL_LABEL 抽成字典(原 inline `.get()` 三连写)

效果(用户视角):
```
inbox     站内 Inbox      fields=[]                available=true   ← 永远可用
email     邮件 SMTP        fields=[email, smtp_*]  available=false  ← 没 SMTP 自动关
feishu    飞书群机器人      fields=[feishu_webhook] available=true   ← webhook 配了
wechat    企业微信          fields=[wechat_webhook] available=false  ← 没配
webhook   Webhook         fields=[webhook_url]     available=false  ← 没配
```

### 3. 订阅保存/运行三层兜底
**`src/api/routes/subs.py`**:
- `SubscribeRequest.channels` schema 改 `Optional[List[str]] = None`(默认 `["inbox"]` 会让 `if req.channels` 永远 truthy,做不出"未传→fallback"语义)
- 创建时:无论 req.channels 是 None/[]/['inbox','email','feishu'],都过 `_available_channels` 过滤一次 → 静默拒绝未配置的渠道

**`src/subscription/__init__.py`**:
- `run_subscription` 在订阅 channels 为空时,拉 `db["users"]` 拿 default_channels,再用 `_available_channels` 过滤
- `_render_and_send` 顺手修掉 `send_all` 位置参数错位(`body_md` 不再误填 `content_html` 第 4 位,改传空串走 keyword)

### 4. 前端 3 个页面统一从 `/notifier/channels` 读渠道
**`NewSubPage.vue` 创建弹窗**:
- 渠道复选框从写死的 `inbox/feishu/email` 改成 `v-for over availableChannels`
- 默认勾选 = 后端告诉的 `default_channels`(已经按 available 过滤)
- 副标题:"来自 Settings 单字段一致性同步,未配置的渠道不会显示"

**`MePage.vue` 默认推送渠道**:
- 同样动态读 + 显示"与 Settings 单字段一致"提示

**`SettingsPage.vue`**:
- 渠道总览表 + 默认推送复选框都从 `/notifier/channels` 拉
- 类型定义 `PushChannel` 加 `available: boolean`
- `availableChannels` ref 装仅 available=true 的

### 5. 历史订阅 channels 一次性回填
**新增** `scripts/migrate_subscriptions_channels.py`:
- 扫描 admin 所有订阅,三类脏数据统一处理:
  - `channels=[]` → 用 `user.default_channels` 替换
  - `channels=['inbox']`(老默认)→ 用 `user.default_channels` 替换
  - `channels=['inbox','email','feishu']` 含不可用 → 过滤掉不可用
- 支持 `--apply` / 默认干跑,带 reason tag,写库后打 `_migrated_day7: true` 标记
- 实测回填 **9 条**(4 老空/3 老默认/2 拼错),全部 → `['inbox','feishu']`

## 🛠️ 改动(表)

| 文件 | 改动 |
|---|---|
| `src/api/routes/settings.py` | 加 `_available_channels()` / `CHANNEL_LABEL`,`/notifier/channels` 加鉴权 + available + default_channels |
| `src/api/routes/subs.py` | `create_subscription` 强制走一致性过滤;`_to_view` 给空 channels 兜底 |
| `src/api/schemas.py` | `SubscribeRequest.channels` → `Optional[List[str]] = None` |
| `src/subscription/__init__.py` | `run_subscription` 第 1 步加 user.default_channels fallback;`_render_and_send` 修 send_all 位置参数;复用 user_doc_for_channels 避免重复查 |
| `src/notifier/__init__.py` | WebhookNotifier 优先 `body_html or content_html`,加 `content_md` 字段 |
| `frontend/src/pages/NewSubPage.vue` | `availableChannels` 动态渲染 + 默认勾 default_channels |
| `frontend/src/pages/MePage.vue` | 同上 |
| `frontend/src/pages/SettingsPage.vue` | `availableChannels` + 类型加 `available` |
| `scripts/migrate_subscriptions_channels.py` | **新增**一次性回填脚本 |
| `docs/day7-deliverable.md` | **新增**本文档 |

## 📊 当前数据

- users 表 admin:default_channels=`['inbox','feishu']`,feishu_webhook 已配,email/wechat/webhook 均无
- subscriptions:**14 条** channels 全部 `['inbox','feishu']`(回填后)
- subscriptions_delivered 历史推送 143 条(没动)
- API endpoints 不变(43),schema 兼容性:`SubscribeRequest.channels` 从必填隐默认变成可空,前端已适配

## 🧪 验证命令

```powershell
# 1. 后端一致性
curl.exe http://127.0.0.1:8000/api/notifier/channels -H "Authorization: Bearer <token>"
# → 看到 available / default_channels 字段

# 2. 创建订阅(勾了 email 但没配 SMTP)→ email 应该被静默拒
curl.exe -X POST http://127.0.0.1:8000/api/subs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"nl_query":"test","title":"一致性测试","channels":["inbox","email","feishu"]}'
# → sub.channels = ['inbox','feishu']

# 3. 不传 channels
curl.exe -X POST http://127.0.0.1:8000/api/subs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"nl_query":"test","title":"fallback 测试"}'
# → sub.channels = ['inbox','feishu'](user.default)

# 4. 历史回填
python scripts\migrate_subscriptions_channels.py --dry  # 干跑预览
python scripts\migrate_subscriptions_channels.py --apply  # 真写库
```

**实战**:重新跑 `AI每日资讯` 订阅(刚刚回填过),命中 5 条 → `[feishu] https://open.feishu.cn/... ✓` —— 飞书实际收到推送。

## ⚠️ 已知 / 推迟

- **头像 / 昵称(F-1)**:用户说"其他没问题",Day 7 不动 `users` 字段,等下次会议
- **订阅编辑入口(F-3)**:后端 `PATCH /api/subs/{id}` 已就绪,Day 8+ 再接前端按钮/Drawer
- **MePage 顶部三件套剩余 1 件(套餐显示错的 "套餐: admin")**:Feishu 等后续做头像时一并修

## 🚀 Day 8 预告

订阅链路稳定后,Day 8 把 F 主题闭环:
1. `users` 加 `nickname / avatar_url` 字段,settings PUT 支持
2. MePage 顶部三件套重渲染(头像图 → 首字母 / 昵称 → username)
3. 订阅卡片新增「编辑」按钮,抽屉式复用 NewSubPage 表单 → `PATCH /api/subs/{id}`
4. MePage "套餐: admin" 显示错误的 bug 顺手改

并写 `docs/day8-deliverable.md`,更新 AGENTS.md §1/§9/§11 各项。
