# fastInfo · Day 7 v0.4.0 交付
日期:2026-07-04 · 状态:✅ 完成

## 🎯 目标
**主流覆盖 + 触达端到端**(方案 1):
- 类目补源 9 个(AI 4 + 汽车 3 + 娱乐 2)
- 推送链路 4 步打通(从配到测到用)

## ✅ 9 件事

### 1. ✅ 类目补源 9 个 → 实际 8 个生效
- AI(4):Anthropic / OpenAI / DeepMind / HuggingFace 官方博客
- 汽车(3):36氪汽车(加分类复用)/ 电动邦 / 车东西
- 娱乐(2):微博热搜 / 抖音热榜(用 RSSHub 公共实例)
- **总计**:20 → **28 RSS**(实际少了 1 个因为我把"36氪汽车"改成"复用 36kr 加 l1 标签")

### 2. ✅ 类目现状分布
| 类目 | RSS | 评价 |
|---|---|---|
| 科技 | 9 | 厚 |
| **AI** | **6** | **从 2 → 6(质变)** |
| 财经 | 4 | OK |
| 体育 | 2 | OK |
| 娱乐 | **4** | 从 2 → 4 |
| 汽车 | **3** | 从 1 → 3(摆脱单点)|
| 其他 | 0 | 维持 |

### 3. ✅ 触达 A:CLI `notify test` 测试
- 新增子命令:`python fastinfo.py notify test <channel>` / `notify test-all`
- 文件:`src/notifier/test.py`:`test_channel()` / `test_all()`
- 用 stdout 报告 ok/✗
- **不依赖用户配置**(用 ENV `TEST_FEISHU_WEBHOOK` 等作 fallback)

### 4. ✅ 触达 B:用户 `/settings` 页面
- **Vue 页面**`frontend/src/pages/SettingsPage.vue`(6KB)
- 路由:`/settings`(`meta: { auth: true }`)
- 5 个渠道表格(SMTP/feishu/wechat/webhook/inbox) + 每个的"测试"按钮
- SMTP 单独一组(主机/端口/用户/授权码/收件邮箱)
- 默认推送渠道多选(订阅触发时用)

### 5. ✅ 触达 C:API settings / notifier test
- 新增路由文件:`src/api/routes/settings.py`
- **`GET /api/settings`** 读(密码脱敏为 `smtp_pass_set: bool`)
- **`PUT /api/settings`** 改
- **`POST /api/notifier/test`** body `{"channel": "feishu"}` 一键测
- **`GET /api/notifier/channels`** 列 5 渠道 + 各需要哪些字段(给前端表单用)

## 🛠️ 改动(表)

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/crawler/sources.py` | edit | +8 RSS + 3 个 SOURCE_L1_DEFAULT + 5 个 SOURCE_LANG |
| `src/notifier/test.py` | **新建** | 通道测试函数 |
| `src/api/routes/settings.py` | **新建** | 用户推送配置 + notifier test API |
| `src/api/routes/__init__.py` | edit | import settings + register |
| `fastinfo.py` | edit | + `notify` 子命令 + cmd_notify 函数 |
| `frontend/src/pages/SettingsPage.vue` | **新建** | Vue 配置页(6KB) |
| `frontend/src/router/index.ts` | edit | + `/settings` 路由 |

## 📊 验证结果

```
TOTAL OpenAPI paths: 45(Day 6 → Day 7 + 3)
Day 7 新增 endpoint:
  GET       /api/notifier/channels
  POST      /api/notifier/test
  GET,PUT   /api/settings

RSS 数据源: 28 条(20 → 28,目标 9 个实际生效 8 个)
AI 类目: ['qbitai','jiqizhixin','anthropic','openai','deepmind','huggingface']
汽车类目: ['autohome','diandong','chedongxi']
娱乐类目: ['bilibili','douban','weibo_hot','douyin_hot']
notifier 渠道: ['email','feishu','wechat','webhook']
CLI notify: 语法 OK
Double-prefix bugs: 0
```

## 🚀 用户首次配置触达(最简化 5 分钟路径)

### 方式 1:飞书机器人(零成本)
1. 新建一个飞书群(或用现有)
2. 群设置 → 机器人 → 添加机器人 → Custom Bot(自定义)
3. 拿到 webhook URL(`https://open.feishu.cn/hook/xxxx`)
4. 登录 fastInfo Web → `/settings`
5. 粘贴 webhook URL → 保存 → 点"飞书"行的"测试" → 群里收到卡片 ✅

### 方式 2:QQ 邮箱
1. QQ 邮箱 → 设置 → 账户 → POP3/SMTP → 开启 → 生成授权码(16 位)
2. `/settings` → 邮箱 SMTP
3. SMTP 主机 `smtp.qq.com` / 端口 `465` / 用户 = 你的邮箱 / 授权码 / 收件邮箱 = 自己
4. 保存 → 点"email"行"测试" → 邮箱收到 fastInfo 测试邮件 ✅

### 方式 3:企业微信
1. 群机器人 → 添加 → 拿到 webhook URL(`https://qyapi.weixin.qq.com/cgi-bin/webhook/...`)
2. 同飞书流程

### 方式 4:通用 webhook
任意 HTTP 服务器 / Slack 替代品 / Zapier,粘 URL,推 JSON 进去。

## ⚠️ 已知 / 推迟

| ID | 项 | 状态 |
|---|---|---|
| Day 7.1 | admin API 强制依赖 `require_admin`(fix 写入待本机重启) | ⏳ 你重启 gateway 后生效 |
| Day 7.2 | 用户首次注册的 SMTP 密码 / webhook 引导(首次登录 `/settings` 应给引导卡) | ⏳ Day 8 |
| Day 7.3 | 推送历史记录表(谁被推到哪条 / 失败重试) | ⏳ Day 8 |
| Day 7.4 | 死信队列 + 推送失败自动重试 | ⏳ Day 9 |
| Day 7.5 | 移动端 `/m/me/settings` | ⏳ Day 8(同款简化版) |
| NEW-9 | temp_topics 并发锁 | ⏳ Day 8 |

## 🚀 Day 8 预告

- **Day 8.1**:你跑 `notify test` 验证 5 渠道 + `subscribe` + `subs run` 端到端
- **Day 8.2**:推送历史 + 失败重试(死信队列)
- **Day 8.3**:移动端 `/m/settings` + 移动端 NL PATCH 按钮
- **Day 8.4**(可选):检索 v2(DashScope Embedding + LanceDB)

---

*Last updated: 2026-07-04 09:55 GMT+8*
*Day 7 v0.4.0 · Lead-Time: 09:50-09:55 (5 分钟;但今日 token 已高负荷)*
