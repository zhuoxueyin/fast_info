# Changelog · fastInfo

> 全部 fastInfo 项目的版本化变更历史。
>
> **格式**:基于 [Keep a Changelog](https://keepachangelog.com/) 风格,版本遵循 [SemVer](https://semver.org/)。
>
> **与其它文档关系**:
> - `AGENTS.md §1 现状速览` → 当前状态一图流
> - `docs/day{N}-deliverable.md` → 当天交付完整复盘
> - **`docs/CHANGELOG.md`(本文件)** → **跨版本变更轨迹**(你正在看)
> - `git log` → 精确元数据(commit / author / 时间)
>
> **维护约定**:见 `docs/CHANGELOG-MAINTENANCE.md`

---

## [v0.5.0] - 2026-07-04 · Day 8 v0.5.0 推送升级

**定位**:推送结构实成升级 · 同一份订阅内容不同渠道通用模板。

### Added
- **`src/subscription/format_push.py`** (新建8KB):统一推送模板
  - `format_html(sub, items, inbox_url)` → 邮件 / 站内 HTML 卡片
  - `format_markdown(sub, items, inbox_url)` → 通用 webhook / 企微
  - `format_feishu_card(sub, items, inbox_url)` → 飞书 interactive card
  - 每条 item 推送必含:原文 URL · source · category · fetched_at · relevance · summary · title
  - XSS 转义 (`_esc()`)、长度裁断(防 256 字符限制)
- **`notifier.send / send_all` 接管 keyword-only kwargs**:
  - `body_md / body_html / card` 可选参数
  - EmailNotifier 优先 `body_html`
  - WechatNotifier 优先 `body_md`,限 4000 字符
  - FeishuNotifier (群) 优先 `card` fallback markdown
  - WebhookNotifier 优先 `body_md` + 加格式提示
  - FeishuDMNotifier 走 card
- **`_render_and_send()`** 升级:同时生成 3 种体,传给 `send_all`

### Changed
- 推送卡现成内容:原文 URL 详细为 button + 摘要 + 译 + 源 + 时间
- 底部统一加 "📥 在 fastInfo 网站查看全部" 入口(可选 inbox_url)

### Notes
- ✅ 后端推送升级完整可用
- ⏸ InboxPage / MobileInbox 卡片视图 留 P2(明天接手)
- ⏸ inbox API 分块参数 留 P2(明天接手)

**Commits**: `3f6488e`

---

## [Unreleased] / v0.4.2

> 还在开发,下次 commit 时整段迁移到具体版本号。

### Planned
- 群聊 App Bot:飞书后台启用机器人 → fastInfo 自接收事件 → /settings 显示已入群(免 webhook URL)
- 推送可靠性:死信队列 + 失败重试
- 移动端:`/m/settings` + 移动端订阅管理 NL PATCH 按钮
- 检索 v2:DashScope Embedding + LanceDB(替代 MongoDB text)

---

## [v0.4.1] - 2026-07-04 · Day 7 v0.4.1

**定位**:飞书 OAuth 单聊绑定(已废弃,改用 webhook 群机器人)。

### Added
- **飞书 OAuth 单聊绑定** 4 个端点:
  - `GET /api/auth/feishu/bind` → 返回 OAuth URL(state 含 user_id 防 CSRF)
  - `GET /api/auth/feishu/callback?code=&state=` → 用 code 换 access_token → 拉 user_info → 写 users.feishu_open_id
  - `GET /api/auth/feishu/status` → 前端轮询当前绑定状态
  - `POST /api/auth/feishu/unbind` → 清空字段
- **`scripts/bind_admin_feishu_and_push.py`**:给 admin 用户一键配飞书 + 触发所有订阅推送
- **`/tmp/feishu_mock_server.py`**(开发辅助):沙盒级 mock,模拟飞书 auth + im/v1/messages 端点
- **`FEISHU_BASE_URL` env**:`FeishuDMNotifier` 支持切换 mock base URL
  - 生产 = `https://open.feishu.cn`(默认)
  - 测试 = `http://127.0.0.1:9876`(本地 mock)

### Changed
- `FeishuDMNotifier` `_get_token` 与 `send` 全部支持 `FEISHU_BASE_URL` env

### Fixed
- 把"用 OpenClaw runtime 凭证"的设计盲点写进 `docs/feishu-bind-setup.md` 的独立性原则

### Docs
- `docs/feishu-bind-setup.md`(1.9KB):飞书后台 + env + 用户流程 + 独立性 deployment checklist
- `docs/notifier-feishu-dm.md` 已被 v0.4.0 后写的版本覆盖

### Stats
- **API endpoints**:+4(45 → 49)
- **OpenAPI paths**:49

**Commits**: `ce328be`、`11ca9a9`

---

## [v0.4.0] - 2026-07-04 · Day 7 v0.4.0

**定位**:主流覆盖 + 触达端到端打通(从采集到推送全部在线)。

### Added
- **9 RSS 数据源(新增 8 个)**:
  - **AI(4)**:Anthropic Blog / OpenAI Blog / DeepMind Blog / HuggingFace Blog
  - **汽车(2)**:电动邦 / 车东西
  - **娱乐(2)**:微博热搜 / 抖音热榜
  - **走 RSSHub 公共实例**(weibo_hot / douyin_hot)+ 官方原始 feed(其他)
- **`notifier/test.py`**:5 渠道一键测试(test_channel + test_all)
- **`FeishuDMNotifier` 类**:飞书 → 个人单聊(im/v1/messages + tenant_access_token + 缓存 20min)(后续在 v0.4.1 重构)
- **API settings 端点 4 个**:
  - `GET /api/settings`(脱敏读取,smtp_pass_set boolean)
  - `PUT /api/settings`(`SettingsUpdate` Pydantic)
  - `POST /api/notifier/test`(一键测指定渠道)
  - `GET /api/notifier/channels`(列出 5 渠道 + 字段需求)
- **CLI**:`fastinfo.py notify test <channel>` / `notify test-all`
- **前端**:`SettingsPage.vue`(6KB):
  - 5 渠道列表(SMTP / feishu / wechat / webhook / inbox)
  - per-channel "测试" button
  - SMTP 字段配置 + 默认推送渠道多选
- **router**:+ `/settings` 路由

### Changed
- `crawler/sources.py`:**20 → 28 RSS**(AI 2→6,Auto 1→3,Entertain 2→4)
- `notifier/__init__.py`:注册 FeishuDMNotifier,加 SettingsPage 友好的字段映射
- AGENTS.md §1 推送渠道 5→6

### Stats
- **RSS 数据源**:20 → 28(+40%)
- **API endpoints**:+3 settings/notifier
- **OpenAPI paths**:42 → 45

**Commits**: `5d2b990`、`11ca9a9`

---

## [v0.3.0] - 2026-07-04 · Day 6 v0.3.0

**定位**:产品差异化 — 让"世界杯例子"成为 24h 可点击 demo。

### Added
- **临时话题 API 4 个端点**(`/api/topics/*`):
  - `POST /api/topics/now` body `{nl_query, max_items=12, hours=48}` → 立即返回匹配的 items + 24h 短期 dashboard
  - `GET /api/topics/now/{tid}` → 查(TTL 过期返 404)
  - `POST /api/topics/now/{tid}/convert` → 一键转长期订阅
  - `GET /api/topics/list` → 列我的有效话题(active_only 默认)
- **临时话题数据层**(`src/storage/temp_topics.py`):
  - `temp_topics` collection(MongoDB)
  - 24h TTL 索引自动清理(`expires_at` + `expireAfterSeconds=0`)
  - 短 ID 唯一索引(`tid` 8 字符,`secrets.token_urlsafe`)
  - CLI sync 包装 `run_create_topic_now`
- **NL PATCH 改订阅**(`/api/subs/{sub_id}/nl-patch`):
  - body `{"nl_command": "改成下午 5 点只发飞书"}` → 自动改 cron / channels / max_items / categories
  - 复用 `nl_parse` 模型组 + 专门 prompt
  - 字段白名单
  - 自动重算 `next_run_at`
- **英文 → 中文自动翻译**(`src/llm/translate.py`):
  - `detect_lang()`:启发式(ascii vs 中文字符比例)
  - `translate_to_zh()`:复用 `short_summary` 模型组
  - `maybe_translate_item()`:ingest 时加 `title_zh / summary_zh / key_points_zh / lang_detected`
- **CLI 子命令新增**:
  - `topic <nl>`:创建临时话题
  - `topic-mgr list / convert`:管理
- **CHANGELOG 维护机制**(本日):`docs/CHANGELOG.md` + `docs/CHANGELOG-MAINTENANCE.md`

### Changed
- `api/routes/source_admin.py` 全部 12 router 加 `Depends(require_admin)`(关 **NEW-8**)
- `api/app.py` lifespan:`asyncio.run(setup_indexes())` 启动时建 TTL 索引
- `api/routes/__init__.py`:`register_routes` 加 topics + source_admin(后者此前漏 register)
- `_run_ingest_async`:检测英文 → 翻译 → 写带翻译字段的 doc
- `src/notifier/__init__.py`:加 `FeishuDMNotifier` 类(v0.4.0 重构)
- AGENTS.md §1 / §11 / §13 回填

### Fixed
- **严重 bug:source_admin router 之前根本没被 register 到 app**(导致 8 个 admin API 完全不可达)— 这次补 register
- **严重 bug:source_admin 自身 prefix 写错** `/api/admin/sources` + register 又加 `/api` → 双层 prefix `/api/api/admin/sources`,改成 `/admin/sources` 后正确

### Docs
- `docs/day6-deliverable.md`(5.8KB):完整交付复盘

### Stats
- **API endpoints**:45 → 52(+7 topics / nl-patch 等净增)
- **OpenAPI paths**:45(注:实际是 41 + 1 topic 重复过滤)= **41 → 42**
- **Subs CLI**:`subs` 字段加 nl_patch

**Commits**: `eec6c3b`、`11ca9a9`

---

## [v0.2.0] - 2026-07-04 · Day 5(v0.2.0 phase 2)

**定位**:源管理 + 监控上线。

### Done(提交于本 session 前,summary here)
- 14 RSS + 5 KOL 上线
- L1 分类(7)+ L2 分类(30+)
- 5 渠道推送架构(email / feishu / wechat / webhook / inbox)
- Web 11 页 + Mobile 6 页 + Docs 12 篇
- `source_config` 多文档 + `source_runs` + `system_alerts`
- 多镜像 fallback(huxiu / nitter)
- 微博 OpenAPI 双模式

**Source commits**:`d29bcf7`、`7ef8bdd`、`99682d3`、`79268d2`、`37dace9`、`f05315b`(本 session 前已 commit)

---

## [Pre-version]

W0-W3 + Day 1-4 全部已 commit 并完整:
- LLM 四级 fallback(M2.7-highspeed → K2.6)
- NL→cron 解析 + run_subscription
- ingest_daemon + subs_scheduler
- JWT 鉴权 + CLI auth 子命令
- Vue 3 + Naive UI + Tailwind 前端
- VitePress 文档站

详见 `git log --oneline` 历史。

---

## Unreleased / 下一棒(跳出 fastInfo 框架的全局方向)

- **多 agent 协同**(用户 12:50 提议):OpenClaw 多 agent 配置,3 个代码库并行推进
- **fastInfo 检索 v2**:DashScope Embedding + LanceDB
- **Phase 4 真 KOL API**:微博 OpenAPI 正式接入 / X v2 真实数据
- **DevOps Day 6-9**:5 服务镜像化 + staging + 回滚演练
- **推送可靠性**:死信队列 + 重试
