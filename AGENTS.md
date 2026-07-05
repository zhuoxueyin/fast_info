# AGENTS.md · fastInfo 项目入口

> 面向 AI agent / 后续接手者 / 自己回看 —— **从 0 到产出,这份文档讲清一切。**
>
> 📌 **本文件必须随 day-end 迭代回填**(详见末尾 §13 「更新约定」)。
>
> 📚 深度方案在 `docs/`:主方案 v1.0 / 本地化方案 v1.1 / MVP 方案 v1.0 / 各 day-N 交付文档。

---

## 0. 项目一句话

**fastInfo = 资讯中心 + AI 情报中枢** — 把分散的 RSS、AI 媒体、热搜用 LLM 摘要 / 解读聚合,按用户**个人订阅**精准推送,BYOK + 本地优先 + 零数据外传。

---

## 1. 现状速览(2026-07-05,Day 9 ✅ + Day 10 双 hotfix)

| 维度 | 当前 |
|---|---|
| 阶段 | **MVP11 · Day 11 完成**(失败源修复 + 同类替换)(Day 11, 2026-07-05) |
| 最新里程碑 | **Day 11(失败源修复 + 同类替换)**:1) cls 改走主页 SSR JSON 抓取(`fetch_cls_home`,正则抠 `hotArticleData` + `json.loads(strict=False)`);2) huxiu 替换为 leiphone 雷锋网(科技/AI 同类,实测 RSS 200 + 600KB+ feed);3) autohome 直接 disable(官方 RSS 404 + SPA + API 封闭,标 Phase 4);4) **顺手修 `upsert_item_async` _id immutable bug**(pymongo insert 失败 mutate dict 后 update 触发 immutable field 错误,update 前 pop `_id`);详见 `docs/day11-deliverable.md`。**Day 10 hotfix #2 · 今日排行冲击榜单**:`/api/hot` 重构加 `mode=category` + `max_per_category`;新增 `/api/hot/categories` 一次拿 7 个 L1 完整榜单;`HotPage.vue` 重写为「总榜 TOP 10(🥇🥈🥉 加冕)+ 分榜汇总(左 L1 导航 + 右完整榜单)」;`MobileHot.vue` 同步升级(横滑 tab + 单列卡);emoji 全部换 lucide-vue-next icon 跨平台无字体依赖;详见 `docs/day10-hotfix-hot-leaderboard.md`。**Day 10 hotfix #1**(推送 GBK):1) notifier 4 处 print → logging + ASCII,2) subs_scheduler TextIOWrapper UTF-8 兜底,3) `send_all` 透传 notifier 返 dict 不再丢 http_status;详见 `docs/day10-hotfix-push-gbk.md`。Day 9 主线(临时话题入口 + 短期跟踪 + 转订阅 fix + 推送历史):`TopicsPage.vue`+`MobileTopicsPage.vue`;subscriptions 加 `track_mode/expires_at/duration_days/track_entity`;LLM 识别事件/人物实体;转订阅选 3/7/14/30 天/长期;`scripts/init_tester.py` 创建 tester 账号(Day 8 P-TEST) |
| 数据 | `items` 130+(+6 cls/leiphone stub) · `subscriptions` 5(4 老 + 1 王力宏短期)· `subscriptions_delivered` 26 · `users` **2** (admin + tester) · `task_runs` 2 · `source_config` 18(原 19 -huxiu/auto 启用 -1 leiphone) · `source_runs` ~50 · `temp_topics` 2 |
| 数据源 | **14 RSS**(科技/AI/财经/体育/娱乐;**huxiu / autohome 已 disabled,新增 leiphone**)+ **5 KOL**(微博/X/小红书;微博 3 用户 KOL disabled 等 OpenAPI) |
| LLM | M2.7-highspeed → M2.7 → M3 → K2.6(四级 fallback) |
| 存储 | MongoDB(主) |
| 推送渠道 | **5 种**:`inbox` / `email`(SMTP)/ `feishu` / `wechat` / `webhook` — 前端按 settings 实际配齐动态展示 |
| 分类 | **L1**(7):科技/AI/体育/娱乐/财经/汽车/其他 + **L2**(30+) |
| 后台 daemon | `ingest_daemon` 30 min + `subs_scheduler` 60s 自动跑订阅 |
| 接口 | CLI + FastAPI(**43** endpoint) + Web(11 页面) + **Mobile(6 页面)** + Docs(12 篇) |
| 源管理 | `source_config` 18 条(多文档,2 disabled) + `source_runs` + `system_alerts` + **批量启停 API** + **recent_runs[3]** |
| 源自动化 | huxiu 多镜像 fallback(已弃) / nitter 5 mirror 轮询 / cls 主页 SSR JSON 抓取(Day 11) / 微博 OpenAPI 脚手架 / 连续失败 ≥5 自动禁用 + 告警 + 批量运维 |
| 部署目标 | 阿里云 ECS 2C2G(~¥30/月) |
| 代码规模 | `src/` 9 包(含 `notifier/` + `taxonomy.py` + `crawler/collectors.py`)· `scripts/` 17 个(+1 `init_tester` +1 `migrate_subscriptions_channels`) |
| 端口标准化 | 本地 L-* (8000/8080) + Docker S-* (18000/18080) — 见 **`docs/ports-分配方案.md`** |

详细里程碑:**`docs/day1-deliverable.md`** / **`docs/day2-deliverable.md`** / **`docs/day3-deliverable.md`** / **`docs/day4-deliverable.md`** / **`docs/day5-deliverable.md`** / **`docs/day6-deliverable.md`** / **`docs/day7-deliverable.md`** / **`docs/day8-deliverable.md`** / **`docs/day9-deliverable.md`** / **`docs/day10-hotfix-push-gbk.md`** / **`docs/day10-hotfix-hot-leaderboard.md`** / **`docs/ports-分配方案.md`**。

---

## 2. 技术架构

### 2.1 顶层三段

```
┌────────────────────────────────────────────────────────────────┐
│           抓取侧(管理员 · 后台 · 不跟用户关联)                  │
│  ingest_daemon  ──→  RSS / 热搜 API  ──→  LLM short_summary     │
│                              ↓                                  │
│                  MongoDB.items(items 公共,跨用户共享)           │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│           用户侧(主进程 · 跟 user_id 强绑定)                   │
│  subs run / CLI / FastAPI  ──→  从 items 过滤 + 去重 + 推送    │
│      ↘                       (subscriptions_delivered 表)       │
│   optional LLM 个性化解读                                       │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│           检索侧(v1=MongoDB text,v2=DashScope+LanceDB)         │
│  search_text / Hot spot / Hot today / Interest inference        │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计原则

1. **抓取独立于订阅**:ingest 是"管理员任务",跟用户无关,后台跑;订阅是"用户视图",只读库。
2. **公共 `items`, per-user `subscriptions`**:同一篇文章被多个用户订阅时,只摘要一次,所有用户共享摘要(broadcast)。
3. **day-N 路由**:今日 Day 2 起每条交付有对应 `docs/day{N}-deliverable.md`。
4. **LLM fallback 双保险**:M3 主,K2.6 备,任何一个 provider 无 key 时自动跳过。
5. **零外部依赖可跑**:本机 MongoDB + 本机 Redis + 远程 LLM API,可全离线本地基础设施跑完整链路。
6. **支持 v2 检索层升级位**:`retrieval/__init__.py` 已留 BGE-M3/DashScope 升级接口,MongoDB text 是兜底。

### 2.3 编码铁律（0-1 项目核心原则）

> 当前项目 0→1，无真实用户。**只有 admin 一个有效用户**，其他账号都是测试/假数据。
> 以下 3 条是架构级红线，代码审查必查。

| # | 原则 | 说明 |
|---|---|---|
| **P1** | **拒绝历史兼容** | 不写兼容旧数据/旧格式的 fallback。数据不规范直接修数据，不要修代码去兜。 |
| **P2** | **唯一链路、唯一写法** | 每个功能只有一条数据流、一种查询方式。禁止同一件事有两条路径（如 ObjectId + username 双路查用户）。 |
| **P3** | **admin 就是唯一业务用户** | 所有业务设计以 admin 为准。不为 smoke_*/local/testuser 等假用户写特殊逻辑。生产/演示/截图都用 admin。 |

#### P-TEST · 测试账号规范(Day 7 加入)

> 🚨 **本项目所有测试 / 调试脚本只许用测试账号 `tester`,不许在 admin 库里造数据。**

| # | 规则 | 理由 |
|---|---|---|
| P-TEST-1 | **测试账号只用一个**:`username=tester`,`password=Tester@2026`(由 `scripts/init_tester.py` 创建,幂等可重跑) | 唯一来源,避免满地假账号污染 |
| P-TEST-2 | **测试脚本必须用 tester 登录**(Bearer token 走 `/api/auth/login`),不许直接 `db["subscriptions"].insert_one(...)` 之类绕过鉴权 | 真实链路验证,不漏 P2 之类的鉴权 bug |
| P-TEST-3 | **不许在 admin 库里造数据**:`db.users.find_one({"username":"admin"})` 后 insert 是禁术——一旦遗留在 admin 库里就破坏 P1(脏数据污染) | 数据规范,清不清得掉都会成为隐患 |
| P-TEST-4 | **诊断脚本命名带 `_` 前缀**(`_diag.py` `_repro.py` `_day7_regress.py`),用完 `mavis-trash` 掉,不进 git | 不污染交付物 |
| P-TEST-5 | **测试残留清理优先于回滚**:连续失败的回归脚本必须最后一步 `db.subscriptions.delete_many({"user_id": "<tester_id>"})` 兜底,失败则用 `--reset` 重新建账号 | 防止越测越脏 |
| P-TEST-6 | **admin 跑过的脚本立刻停,改 tester 重跑**:如果发现脚本动了 admin(回查脚本里是否出现 `username=='admin'` 字符串),改用 tester 重跑并把已污染数据手工清理 | 兜底纪律 |

**使用示例**(合规 vs 违规):

```python
# ✅ 合规:测试账号 + 清理尾巴
import sys; sys.path.insert(0, r"D:\WORK\trae\fast_info\src")
db = get_sync_client()["fastinfo"]
tester_id = db.users.find_one({"username":"tester"})["_id"]

# 创建测试订阅
db["subscriptions"].insert_one({"user_id": str(tester_id), "title": "TEST·foo", ...})

# 测试结束,一次性清理
db["subscriptions"].delete_many({"user_id": str(tester_id)})
```

```python
# 🚫 违规:在 admin 里直接造数据
admin = db.users.find_one({"username": "admin"})
db["subscriptions"].insert_one({"user_id": str(admin["_id"]), "title": "TEST", ...})
```

**代码审查检查点**:
- `_find_user_doc` 是否只用 `ObjectId` 一种方式查？ ✅ 不允许 username fallback
- settings/notifier 是否有多余的渠道(如 `feishu_dm` 孤儿渠道)？ ✅ 只有活跃渠道
- 订阅执行 channels 是否有多层 fallback？ ✅ 订阅自己的 channels 字段,空则 fallback 到 user.default_channels,再 fallback 到 `["inbox"]`(Day 7 三层兜底)
- `_id` 是否统一为 ObjectId？ ✅ `init_admin.py` 不再用 `"u_admin"` 字符串 _id
- **新增**:任何脚本字符串里出现 `'admin'` 作为 user_id 来源,就是 P-TEST-3 违规

### 2.4 数据流(Subscription 一次执行)

```
ingest_daemon (30 min/次)
   ↓
RSS / 热搜 API
   ↓
LLM short_summary  ──── [M3 失败] ──→ [K2.6 顶]
   ↓
MongoDB.items  (id=url_hash, dedup)
   ↓
user subs run  ──→  keywords 硬过滤  ──→  categories boost(软)
   ↓
subscriptions_delivered  (sub × item 唯一去重)
   ↓
return {scanned, matched, delivered}
```

---

## 3. 技术栈

| 层 | 选型 | 备注 |
|---|---|---|
| **DB** | MongoDB 8.x(本机已有)| `text` index search v1 / 后续 LanceDB 向量 v2 |
| **队列** | Redis 7.x(Docker)| Docker Compose 内置 Redis,默认宿主机端口 6379 |
| **后端** | venv Python 3.12(本地)；ECS Linux Python 3.12 | 不用 3.14,ML 库兼容性差 |
| **Web 后端** | FastAPI 0.115+ (Day 2 实装)| + uvicorn 0.32+ |
| **Web 前端** | 单页 HTML(Day 5+)| 走 FastAPI JSON |
| **LLM 主** | M2.7-highspeed / M2.7 / M3(`api.minimaxi.com/v1`)| OpenAI 协议,`Authorization: Bearer` |
| **LLM 备** | Kimi K2.6(`api.kimi.com/coding/v1`)| **Anthropic Messages** 协议,`x-api-key` 鉴权 |
| **Embedding v1** | MongoDB text index(`english`)| 兜底 |
| **Embedding v2** | DashScope Embedding API(远程)| Day 4,ECS 也跑得起 |
| **向量库** | LanceDB(本机)| Day 4 |
| **认证** | PBKDF2 + JWT(HS256)| session 落 `data/.session.json` |
| **部署** | 阿里云 ECS 2C2G | systemd / cron 调度 |
| **调度** | 自家 cron 解析 + ingest_daemon 循环 | 不用 APScheduler,够 MVP |

不用 / 推迟:SQL / Cassandra / Kafka / Rust Axum / 本地 BGE-M3 / Web 框架(GUI 留 Day 5+)/ 邮件推送 / Rerank 队列。

---

## 4. 目录结构(实)

```
fast_info/                                              ← 项目根
├── AGENTS.md                                           ← ⭐ 本文件,AI/新接手的入口
├── README.md                                           ← 对外 facing(简版)
├── docker-compose.yml                                  ← Docker 预发布环境(Mongo/Redis/API/Web/workers)
├── requirements.txt                                    ← Python 依赖
│
├── config/
│   └── .env.example                                    ← 环境变量样例(MMX_API_KEY 等)
│
├── src/                                                ← 所有 import 起点 (Day 5 升级)
│   ├── llm/
│   │   └── model_registry.py                           ← ⭐ M2.7-highspeed→M2.7→M3→K2.6 四级路由
│   ├── crawler/                                        ← ⭐ Day 5 改造
│   │   ├── rss_collector.py                            ← Item dataclass + 单 URL RSS 兼容入口
│   │   ├── collectors.py                               ← ⭐ 多镜像 fallback + 每源 source_runs
│   │   ├── sources.py                                  ← RSS_SOURCES / KOL_SOURCES 注册表(Day 5 删 xhs demo)
│   │   ├── mirrors.py                                  ← ⭐ Day 5: HUXIU_RSS / NITTER_MIRRORS
│   │   ├── weibo_openapi.py                            ← ⭐ Day 5: 双模式 (openapi / scraper)
│   │   └── alarms.py                                   ← ⭐ Day 5: system_alerts 派发
│   ├── storage/                                        ← ⭐ Day 5 多文档
│   │   ├── mongo_writer.py                             ← Mongo CRUD + text index + ensure_indexes (新加 source_runs/source_config/system_alerts)
│   │   ├── source_runs.py                              ← ⭐ Day 5: 每源记录 + 健康度 + 自动禁用
│   │   └── source_config.py                            ← ⭐ Day 5: 多文档 CRUD + seed
│   ├── retrieval/
│   │   └── __init__.py                                 ← search_text / hybrid_search(v1 + v2 升级位)
│   ├── subscription/
│   │   └── __init__.py                                 ← NL→cron + run_subscription(read-DB)
│   ├── auth/
│   │   └── __init__.py                                 ← PBKDF2 + JWT + session
│   └── api/                                            ← ⭐ Day 2 新增 / Day 5 加 source_admin
│       ├── app.py                                      ← FastAPI 实例 + lifespan
│       ├── deps.py                                     ← require_user 鉴权依赖
│       ├── schemas.py                                  ← Pydantic 请求/响应
│       └── routes/                                     ← 8 个子 router(auth/hot/ingest/items/search/stats/subs/today)
│
├── scripts/                                            ← 运维 / 测试 / 后台
│   ├── ingest_daemon.py                                ← ⭐ 后台 30 分钟轮询(独立进程)
│   ├── api_server.py                                   ← ⭐ Day 2 新增:uvicorn 启动入口
│   ├── activate.ps1 / activate.sh                      ← venv 激活快捷
│   ├── reset_delivered.py                              ← 清推送去重(测试用)
│   ├── test_search.py / test_subscription.py /         ← 各模块 smoke 测试
│   ├── test_sub_run.py / trace_sub.py / debug_subs.py  ← Day 1 debug 留下的
│
├── examples/                                           ← 用户可参照的最小样例
│   ├── smoke_test.py                                   ← Redis+API Key+M3+K2.6 fallback 全链路
│   ├── fetch_and_summarize.py                          ← RSS fetch + M3 摘要端到端
│   └── api_e2e_smoke.py                                ← ⭐ Day 2 新增:API 端到端 13 步 smoke
│
├── docs/                                               ← 方案 / 里程碑
│   ├── fastInfo-可行性技术方案-v1.0.md                 ← 主方案
│   ├── fastInfo-技术栈本地化与模型组-v1.1.md           ← 模型组路由
│   ├── fastInfo-MVP-整体方案-v1.0.md                   ← MVP 整体规划
│   ├── adr/0001-tech-stack.md                          ← ADR
│   ├── schema/schema-v1.sql                            ← (参考,已被 MongoDB 替代)
│   ├── day1-deliverable.md                             ← Day 1 交付总结
│   └── day2-deliverable.md                             ← ⭐ Day 2 交付总结(本次)
│
├── data/                                               ← 本地数据(gitignore)
│   ├── ingest-daemon.log
│   ├── api-server.log                                  ← Day 2
│   └── .session.json                                   ← JWT 持久化
│
├── frontend/                                           ← ⭐ Day 3 新增:Vue 3 + Vite + Naive UI + Tailwind
│   ├── src/
│   │   ├── pages/              ← 11 页面(HomePage/HotPage/SearchPage/ItemDetail/Login/Register/Me/Inbox/NewSub/admin/*)
│   │   ├── components/         ← ItemCard
│   │   ├── layouts/            ← DefaultLayout
│   │   ├── store/              ← Pinia auth
│   │   ├── router/             ← Vue Router + 鉴权 guard
│   │   ├── lib/                ← api.ts (ofetch 封装)
│   │   └── types/              ← TS 接口
│   └── dist/                   ← Vite 构建产物
│
├── docs-site/                                           ← ⭐ Day 3 新增:VitePress 文档站
│   ├── .vitepress/config.mts   ← 主题 + 侧边栏
│   ├── index.md                ← 首页
│   ├── guide/                  ← getting-started / concepts / auth / subscriptions
│   └── api/                    ← 7 篇 API 详情(总览 + auth/items/subs/banner/inbox/admin)
│
├── .trae/documents/                                     ← ⭐ Day 3 新增:PRD + 技术架构
│   ├── prd.md
│   └── technical-architecture.md
│
└── .venv/                                              ← Python 虚拟环境(gitignore)
```

---

## 5. 快速开始(从 0 跑起来)

### 5.1 前置依赖

- **MongoDB 8.x**(本机已装,默认端口 27017)
- **Docker Desktop**(本机已修复,用于本机预发布 / Docker 验证)
- **Python 3.12+**(本机用 3.14 也兼容大部分代码,部署用 3.12)
- **API Key**:MiniMax(主)+ Kimi K2.6(备,二选一必有一个)

### 5.2 本地 / Docker 端口约定

> 核心原则:从 **Windows 本机**访问用 `127.0.0.1:宿主机端口`;从 **容器内部**互访用 Compose 服务名 + 容器端口。

#### 本地开发(非 Docker)

| 服务 | 地址 | 说明 |
|---|---|---|
| Vue Web | `http://127.0.0.1:5173/` | `frontend` 下 `npm run dev` |
| FastAPI | `http://127.0.0.1:8000` | `python scripts/api_server.py` |
| Swagger | `http://127.0.0.1:8000/docs` | 原生 FastAPI 文档 |
| VitePress Docs | `http://127.0.0.1:5174/` | `docs-site` 下 `npm run dev` |
| MongoDB | `mongodb://127.0.0.1:27017` | Windows 本机 Mongo |
| Redis | `redis://127.0.0.1:6379` | 本机 Redis 或单独容器 |

#### Docker 预发布(推荐验收入口)

| 服务 | Windows 访问 | 容器内部访问 | 说明 |
|---|---|---|---|
| Web + Nginx | `http://127.0.0.1:18080/` | `web:80` | 用户主入口(**S-Web**,5 位数) |
| API | `http://127.0.0.1:18000` | `api:8000` | 直连,调试用(**S-API**) |
| Docs | `http://127.0.0.1:18080/docs/` | `web:80/docs/` | Docker 内置静态文档 |
| Swagger | `http://127.0.0.1:18080/swagger` 或 `http://127.0.0.1:18000/docs` | `api:8000/docs` | Nginx 反代到 API |
| MongoDB | `mongodb://127.0.0.1:27018` | `mongodb://mongo:27017` | 宿主机 +1,避开本机 27017 |
| Redis | `redis://127.0.0.1:6380` | `redis://redis:6379` | 宿主机 +1,避开本机 6379 |

> 📌 **2026-07-04 起端口标准化**:本地 + Docker 用不同段位,**可以同时跑**不冲突。
> 完整对照表见 **`docs/ports-分配方案.md`**(本地 L-* 用 8000/5173,Docker S-* 用 18000/18080)。

如需自定义端口:

```powershell
$env:FASTINFO_WEB_PORT = "28080"
$env:FASTINFO_API_PORT = "28000"
$env:FASTINFO_MONGO_PORT = "37018"
$env:FASTINFO_REDIS_PORT = "26380"
$env:DOCKER_REGISTRY_PREFIX = "docker.m.daocloud.io/library/"
docker compose up -d --build
```

### 5.3 本地开发一键启动

> 📌 **2026-07-04 起改用 dotenv + 根 .env 单文件方案**,不再每个 key 单独 `$env:...=...`。

```powershell
# 1) 克隆 / 进入项目
cd D:\WORK\trae\fast_info

# 2) venv 激活(已建好,直接激活即可)
. scripts\activate.ps1
# Linux: source scripts/activate.sh

# 3) 复制 .env.example → .env 并填入真实 key(只需做一次)
copy .env.example .env
#    编辑 .env,填 MMX_API_KEY / KIMI_API_KEY / FASTINFO_SECRET
#    .env 已在 .gitignore 里,不会被 commit

# 4) 起 Redis 容器(如果没起)
docker compose up -d redis

# 5) 初始化 Mongo 索引(首次)
python -c "import sys; sys.path.insert(0,'src'); from storage.mongo_writer import ensure_indexes; ensure_indexes()"

# 6) 烟雾测试(应 4/4 通过)
python examples/smoke_test.py

# 7) 跑一次 ingest 测试
python scripts/ingest_daemon.py --once

# 8) 启 CLI
python fastinfo.py --help

# 9) 启 API
python scripts/api_server.py
#    访问 http://127.0.0.1:8000/docs
```

**dotenv 加载规则**:
- `src/_env.py` 在所有 entrypoint 脚本顶部自动加载 `项目根/.env`
- `override=False`: shell 已 export 的 env 优先(便于临时调试)
- 本地开发用 `项目根/.env` 一份;Docker 用 `docker/env.docker.local` 覆盖差异

### 5.4 Docker 编译 + 部署(本机预发布)

适用场景:更新 day5 分支代码后,在本机 Docker 里按接近云环境的方式重新编译、部署、验收。

> 📌 **2026-07-04 起 5 个 service 一把梭**:`docker compose up -d` 默认会拉起 mongo / redis / api / web / **ingest_daemon** / **subs_scheduler**(6 个)。
> 后台 worker 不再藏在 `--profile workers` 里,避免新人踩坑"起了 docker 但没数据"。

```powershell
cd D:\WORK\trae\fast_info

# 1) 如需拉最新代码(手工确认后再执行)
git switch day5
git pull

# 2) 准备两份 env 文件(每个环境只需做一次)
#    a. 根 .env: 共享配置(API Key / SECRET / SMTP 等)
copy .env.example .env
#       编辑 .env 填入真实 key
#    b. docker/env.docker.local: Docker 差异值(容器内服务地址)
copy docker\env.docker.local.example docker\env.docker.local
#       (默认模板就能用,无需改)

# 3) 国内网络建议加镜像前缀
$env:DOCKER_REGISTRY_PREFIX = "docker.m.daocloud.io/library/"

# 4) 编译 + 部署全部 6 个 service
docker compose up -d --build

# 5) 验证服务
docker compose ps
curl.exe http://127.0.0.1:18080/healthz        # 走 Nginx
curl.exe http://127.0.0.1:18000/healthz        # 直连 API
```

**容器内 env 加载优先级**(高→低):
1. `docker-compose.yml` 的 `env_file: docker/env.docker.local`(本机覆盖)
2. `./.env` 通过 volume 挂到 `/app/.env`(共享配置)
3. shell 环境变量
4. 代码默认值

**关键变化**:
- ✅ `docker/env.docker.local` 已 gitignore,误填 key 也不会 commit
- ✅ 共享 key(API Key / SECRET)只填一次,本地 + Docker 通吃
- ✅ ingest_daemon / subs_scheduler 默认随主流程一起起,30min 抓取 / 60s 调度自动运行
- ✅ **端口标准化**:Docker 用 18000/18080,本地用 8000/8080,**可同时跑**不冲突(详见 `docs/ports-分配方案.md`)

浏览器验收:

```text
Web:     http://127.0.0.1:18080/        (S-Web,推荐走 Nginx)
Docs:    http://127.0.0.1:18080/docs/
Swagger: http://127.0.0.1:18000/docs   (S-API 直连)
Admin:   admin / admin@2026
```

Docker 首次启动会自动执行:

```text
python scripts/init_admin_collections.py
python scripts/init_admin.py --username admin --password admin@2026
```

如果改了 `requirements.docker.txt`、Dockerfile、Node 依赖或构建缓存异常,用无缓存重建:

```powershell
$env:DOCKER_REGISTRY_PREFIX = "docker.m.daocloud.io/library/"
docker compose build --no-cache api web
docker compose up -d
```

如需连后台抓取 / 订阅调度一起跑:

```powershell
$env:DOCKER_REGISTRY_PREFIX = "docker.m.daocloud.io/library/"
docker compose --profile workers up -d --build
```

常用排错:

```powershell
docker compose logs -f api
docker compose logs -f web
docker compose logs -f ingest_daemon
docker compose down              # 停容器,保留 Mongo/Redis volume 数据
docker compose down -v           # 危险:连数据库 volume 一起删,只在重置环境时用
```

### 5.5 ECS 部署(Linux,2C2G)

```bash
# 1) 装 Python 3.12 + Redis(可选跳过,用远程 Redis)
sudo apt install python3.12-venv redis-server -y

# 2) 拉项目
cd /opt && git clone https://github.com/<user>/fast_info.git && cd fast_info

# 3) venv + 依赖
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4) 环境变量(放 systemd unit / .env,不要 commit)
export MONGO_URL=mongodb://<remote>:27017
export REDIS_URL=redis://localhost:6379
export MMX_API_KEY=sk-...

# 5) systemd 拉起 ingest_daemon
sudo tee /etc/systemd/system/fastinfo-ingest.service <<EOF
[Unit]
Description=fastInfo Ingest Daemon
After=network.target

[Service]
WorkingDirectory=/opt/fast_info
ExecStart=/opt/fast_info/.venv/bin/python scripts/ingest_daemon.py
Restart=always
EnvironmentFile=/opt/fast_info/.env

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now fastinfo-ingest

# 6) FastAPI 放 Day 2
```

---

## 6. 使用教程

### 6.1 CLI 一览

```powershell
python fastinfo.py --help
```

```
fastinfo.py
├── auth
│   ├── register   --username <name> [--email <e>]
│   ├── login      --username <name>
│   ├── logout
│   └── whoami
├── search     --query <q> --limit 20           # v1: MongoDB text
├── today      --limit 20 --category X          # 最近 N 条
├── hot        --limit 10 --hours 24 \          # 今日热点
│              --threshold 0.7
├── ingest     --limit 8                        # 单次抓+摘要
├── subs
│   ├── list                                      # 列出所有订阅
│   ├── run <id> [-v]                              # 立即跑(从库过滤)
│   └── delete <id>                                # 删除
└── stats                                       # MongoDB 状态 / 索引
```

### 6.2 推荐用法(用户视角)

```powershell
# 1. 注册 + 登录
python fastinfo.py register --username alice --email a@x.com
python fastinfo.py login --username alice

# 2. 手动跑一次抓取(可选,后台 daemon 已自动跑)
python fastinfo.py ingest --limit 8

# 3. 看今日热点
python fastinfo.py hot --limit 5

# 4. NL 写订阅 → 解析为 cron
python fastinfo.py subs run <id>          # 立即执行
# (scheduler:subs list 显示 next_run)
```

### 6.3 订阅 NL 模板

```
"帮我每天 9 点看 AI 资讯"               → keywords=AI/人工智能, cron=0 9 * * *
"每周一周三 18 点给我科技周末报"          → keywords=科技/数码, cron=0 18 * * 1,3
"实时抓 V2EX 上的 Claude 帖子"           → keywords=V2EX/Claude, cron=*/30 * * * *
"只看财经并按相关度排序"                 → keywords=财经/股票, sort=relevance
```

### 6.4 后台 ingest_daemon(运维视角)

```powershell
# 单次(测试 / 排查)
python scripts/ingest_daemon.py --once

# 守护(默认 30 min/轮)
python scripts/ingest_daemon.py                # Ctrl+C 退出
python scripts/ingest_daemon.py --interval 600  # 10 min/轮

# 看日志
Get-Content data\ingest-daemon.log -Tail 20 -Wait

# 杀后台(精准,只杀 fast_info 进程,不误伤其他项目)
Get-Process python | Where-Object {$_.CommandLine -like '*fast_info*'} | Stop-Process -Force
```

### 6.5 FastAPI 启动 + 使用(Day 2 起)

```powershell
# 启动(默认 127.0.0.1:8000)
python scripts/api_server.py
# 部署时: --host 0.0.0.0 --port 8000

# 打开浏览器
http://127.0.0.1:8000/docs          # Swagger UI(可在线测)
http://127.0.0.1:8000/redoc         # ReDoc
http://127.0.0.1:8000/healthz       # Mongo 健康检查

# 端到端 smoke(13/13 应全过)
python examples/api_e2e_smoke.py --no-ingest     # 跳过真抓取
python examples/api_e2e_smoke.py                 # 全跑(含 LLM 抓取)

# 一键启停(只动 fast_info 自己的进程,不误伤)
powershell -ExecutionPolicy Bypass -File scripts\restart_api.ps1 start
powershell -ExecutionPolicy Bypass -File scripts\restart_api.ps1 stop
powershell -ExecutionPolicy Bypass -File scripts\restart_api.ps1 status
bash scripts/restart_api.sh                       # Linux/macOS

# ⚠️ 本机有 Clash / v2rayN 之类的系统代理时,客户端请求 127.0.0.1 会被劫
# 返 502。api_server.py 启动时已自动清 HTTP_PROXY/HTTPS_PROXY,但客户端
# 进程(curl / PowerShell / Python)需要自己清:
#   $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''
```

#### API endpoint 一览(Day 2 实装)

| Method | Path | 鉴权 | 用途 |
|---|---|---|---|
| GET  | `/healthz` | 公开 | Mongo 健康检查 |
| GET  | `/api/stats` | 公开 | 库统计 + 索引 |
| GET  | `/api/search?q=&limit=` | 公开 | MongoDB 全文检索 |
| GET  | `/api/today?limit=&source=&category=` | 公开 | 最近 N 条 |
| GET  | `/api/hot?limit=&hours=&threshold=&mode=&max_per_category=&category=` | 公开 | 今日热点(Day 10 加 `mode=category` 单类完整榜 + `max_per_category` 截断) |
| GET  | `/api/hot/categories?limit=&hours=&threshold=` | 公开 | 🆕 今日分榜汇总(一次拿 7 个 L1 的 TOP N) |
| GET  | `/api/items?ids=a,b,c` | 公开 | 批量查(逗号分隔 id) |
| GET  | `/api/items/{id}` | 公开 | 单条详情 |
| POST | `/api/auth/register` | 公开 | 注册 |
| POST | `/api/auth/login` | 公开 | 登录(JWT) |
| GET  | `/api/auth/me` | Bearer | 当前用户 |
| POST | `/api/subs` | Bearer | NL 建订阅 |
| GET  | `/api/subs` | Bearer | 列出我的 |
| POST | `/api/subs/{id}/run` | Bearer | 立即跑 |
| DELETE | `/api/subs/{id}` | Bearer | 删除 |
| POST | `/api/ingest/run?limit=` | Bearer | 手动触发抓取 |

#### 鉴权流

```bash
# 1. 注册
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"p@ss"}'

# 2. 登录拿 token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"p@ss"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 3. 带 token 调鉴权接口
curl -X POST http://127.0.0.1:8000/api/subs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"AI早报","nl_query":"每天 9 点看 AI 资讯","max_items":3}'
```

### 6.7 Web 平台 + 文档站(Day 3 起)

三个服务**各自独立端口**同时跑,互不依赖。

```powershell
# 1) 后端 API(已有,Day 2)
python scripts/api_server.py                    # :8000
#   Swagger UI: http://127.0.0.1:8000/docs

# 2) Web 前端(Vue 3 + Naive UI + Tailwind)
cd frontend
npm install
npm run dev                                    # :5173
#   proxy: /api → :8000 /docs → :5174

# 3) 文档站(VitePress)
cd docs-site
npm install
npm run dev                                    # :5174
#   顶部 nav 直接跳 /api/docs Swagger UI
```

#### 三端关系图

```
浏览器
  ├─ http://127.0.0.1:5173/          ← Vue 前端(主入口)
  │     ├ /api/*     → proxy → :8000(FastAPI)
  │     └ /docs/*    → proxy → :5174(VitePress)
  ├─ http://127.0.0.1:5174/          ← VitePress 文档
  │     └ 顶部 nav 跳 → :8000/docs(Swagger)
  └─ http://127.0.0.1:8000/docs   ← Swagger UI(原生 FastAPI)
```

#### 首次初始化

```powershell
# 1) 装依赖
cd frontend && npm install && cd ..
cd docs-site && npm install && cd ..

# 2) 初始化数据库
python scripts/init_admin_collections.py

# 3) 创建管理员账号
python scripts/init_admin.py --username admin --password "admin@2026"
# 用 admin / admin@2026 登录后可访问 /admin/* 页面
```

#### 生产构建

```powershell
cd frontend && npm run build         # 产物 → frontend/dist/
cd docs-site && npm run build         # 产物 → docs-site/.vitepress/dist/
# nginx 反代 /api 到 :8000,/docs 到 .vitepress/dist/,根到 frontend/dist/
```

### 6.8 故障排错清单

| 现象 | 排查 |
|---|---|
| `subs run` 返回 `delivered=0` | 先清 `subscriptions_delivered`(`scripts\reset_delivered.py`)重测,确认 keywords 命中 |
| `hot` 命令 `NoneType subscriptable` | items 缺 `published_at`,代码已 fallback 到 `fetched_at` |
| `ingest` 没新增 | 检查 `MMX_API_KEY` / `MONGO_URL` / `KIMI_API_KEY`,看 daemon 日志 |
| `connect ECONNREFUSED 27017` | `mongosh` 检查 Mongo 进程;Linux 用 `systemctl status mongod` |
| Kimi 调用 401 | 走的协议不对 — **必须** `x-api-key` header + `anthropic-version: 2023-06-01`,endpoint `/v1/messages`(不是 `/v1/chat/completions`)|
| `RuntimeError: There is no current event loop` | 用了 nested `asyncio.run`,改用本文件的 sync wrapper |
| **API 返 502 空响应,但 `app.openapi()` 正常** | 本机 Clash / v2rayN 把 127.0.0.1 流量劫到 7892 返 502。`api_server.py` 默认会自动清代理;客户端进程需手动 `$env:HTTP_PROXY=''; $env:HTTPS_PROXY=''` 或 smoke 脚本已内置清代理 |
| `winerror 10013` / `无法访问套接字` | 端口被系统策略拦,换 `--port 18080` 或加防火墙规则 |

---

## 7. 模型路由(`src/llm/model_registry.py`)

### 7.1 模型组(实测四级 fallback)

| 组名 | 用途 | 路由顺序(priority 1→4) | max_tokens |
|---|---|---|---|
| `short_summary` | < 500 字短摘要(ingest 默认)| M2.7-highspeed → M2.7 → M3 → K2.6 | 600 |
| `long_summary` | 长摘要 / 简报 | 同上 | 2000 |
| `deep_interpretation` | 研报级深度解读 | 同上 | 8192 |
| `nl_parse` | NL→结构化(订阅解析)| 同上(temperature=0.2) | 500 |

**权重不再按 "M3 vs K2.6" 二元写死**,改为按 priority 顺序回退,具体见 `src/llm/model_registry.py` 的 `BUILTIN_GROUPS`。

### 7.2 双机容灾(实测 4 provider)

- **熔断**:错误率 ≥ 30% 触发,持续 60s 半开,3 个探针恢复
- **冷却**:失败后指数退避 300 → 1800s 上限
- **Provider 内 retry**:网络抖动重试 2 次
- **单 key 降级**:`_select_provider` 自动跳过无 api_key 的 provider(只配 MMX_API_KEY 也能跑)
- **协议分歧**:
  - MMX 三档(M2.7-highspeed / M2.7 / M3):OpenAI 协议,`Authorization: Bearer`,endpoint `https://api.minimaxi.com/v1`
  - Kimi K2.6:**Anthropic Messages 协议**,`x-api-key` + `anthropic-version: 2023-06-01`,endpoint `https://api.kimi.com/coding/v1`

### 7.3 调用样例

```python
from llm.model_registry import build_default_registry
registry = build_default_registry()
result = await registry.get("short_summary").chat(messages, max_tokens=600)
content = result["choices"][0]["message"]["content"]
await registry.aclose()
```

---

## 8. 数据库 Schema(MongoDB,库名 `fastinfo`)

| collection | 关键字段 | 索引 |
|---|---|---|
| `users` | `_id`, `username`, `password_hash`(PBKDF2), `email`, `created_at` | `ux_username` unique |
| `items` | `_id`, `url_hash`(dedup), `source`, `url`, `title`, `summary`, `category`, `relevance`, `fetched_at`, `summary_at` | `ux_url_hash`, `ix_source`, `ix_cat`, `ix_fetched`, **`ix_search_text`**(title+summary text index,english) |
| `subscriptions` | `_id`, `user_id`, `title`, `nl_query`, `keywords[]`, `sources[]`, `categories[]`, `cron_expr`, `next_run_at`, `is_active` | `ix_user_active` |
| `subscriptions_delivered` | `subscription_id`, `user_id`, `item_id`, `delivered_at` | `ux_sub_item` unique, `ix_user_delivered` |

所有 ISO 时间字符串字段用 `datetime.now(timezone.utc).isoformat()` 写入,字典序 == 时序,可直接比较。

⚠️ **`language` 字段是 MongoDB text index 保留字段**:入库要么改名,要么在 text index 时显式 `language_override="doc_lang"`(已避开)。

---

## 9. Day 迭代路线图

| Day | 主题 | 关键交付 | 状态 |
|---|---|---|---|
| **W0** | 方案 + 基础设施 | 方案文档 / Redis / venv / Mongo 接入 | ✅ |
| **W1** | LLM 路由 + 用户系统 | M2.7-highspeed→M2.7→M3→K2.6 fallback / PBKDF2+JWT | ✅ |
| **W2** | RSS 抓取 + MongoDB text search | 7 RSS 源 + RSS LLM 摘要入 items 库 | ✅ |
| **W3** | 订阅引擎 + CLI | NL→cron / run / scheduler / CLI 8 命令 | ✅ |
| **Day 1** | 架构解耦 + 调度 + 今日热点 | subs 读库 + ingest_daemon + hot | ✅ |
| **Day 2** | FastAPI 化 | 15 endpoint + JWT 鉴权 + e2e smoke 13/13 + 文档同步 | ✅ |
| **Day 3** | Web 平台 + 文档站 | Vue3 前端 11 页面 + VitePress 文档站 12 篇 + 后端 9 个新 API + admin 视图 | ✅ |
| **Day 4** | 多源 + KOL + 二级分类 + 多渠道推送 + 移动端 | 14 RSS + 5 KOL + L1/L2 + 5 渠道 Notifier + /m 移动端 + subs_scheduler | ✅ **今日** |
| **Day 5** | 源可管理 + 可监控 + SourcesPage 增强 | 19 源 × source_runs + 8 admin API + SourcesPage 升级 + 批量启停 + 自动禁用 + 告警 + huxiu/nitter 多镜像 | ✅ |
| **Day 6** | 实时依赖监控(GBK bug 修) | daemon GBK 兜底 + `reap_stale_task_runs` 一键清理 + `/api/admin/monitoring` 聚合 8 组件 + MonitoringPage 红黄绿 + 一键重启 daemon + 一键重启用 disabled 源 | ✅ |
| **Day 6v2** | 监控重构 + SourcesPage 跨页同步 | check_web/docs/daemon 三组聚合 + MonitoringPage 三段式(服务/任务/资源) + 去手动 reap 按钮 + SourcesPage 跨页自动刷新(focus + visibilitychange + sources-changed 事件) | ✅ |
| **Day 7** | 订阅链路一致性(single source) | `GET /notifier/channels` 加 `available` + `default_channels`(单一来源);`subs.create` + `run_subscription` 三层 fallback 到 user.default_channels;前端 NewSubPage / MePage / SettingsPage 渠道动态展示;`scripts/migrate_subscriptions_channels.py` 回填 9 条老订阅;`send_all` 位置参数顺手修正;**飞书实测收到推送** | ✅ |
| **Day 8** | 用户三件套 + 订阅二次编辑 + 测试纪律 | `users` 加 `nickname / avatar_url`;MePage 顶部三件套重渲染(头像 URL→首字母 / 昵称→username / 套餐真值)+「编辑资料」Modal;订阅卡片「✏️」编辑 → `/subs/edit/:id` → `PATCH /api/subs/{id}`;**`scripts/init_tester.py` 创建 `tester` 账号 + AGENTS.md §2.3 P-TEST 6 条纪律** | ✅ |
| **Day 9** | 临时话题入口 + 短期跟踪 + 转订阅 RuntimeError 修复 | 新增 `TopicsPage.vue` + `MobileTopicsPage.vue` + 顶 nav + 底 tab 加入口;修转订阅 `RuntimeError`(拆 `convert_topic_to_sub` 的 LLM/写库,FastAPI handler 改 await);`subscriptions` 加 `track_mode`/`expires_at`/`duration_days`/`track_entity` 四字段,LLM 自动识别事件/人物实体(王力宏、世界杯等),转订阅弹 Modal 选 3/7/14/30 天 / 长期,cron 缩短到 6h,`subs_scheduler` 过期自动停;`SubscribeRequest/Patch/SubscriptionView/_to_view` + `POST /api/topics/now/{tid}/convert?duration_days=N&track_mode=short` 全链路接入 | ✅ |
| **Day 9(增)** | 推送历史 + 触发来源识别 | 新增 `push_history` 集合(`user_id / subscription_id / trigger / operator / channels_ok/fail / channel_results / items / sent_at / duration_ms`);`notifier.send_all` + 4 channel 全部返结构化 `{ok, http_status, error}`;`run_subscription(trigger, operator)` 透传并落历史;`scripts/subs_scheduler` 透 `trigger="schedule"`;`GET /api/me/push-history[?trigger=]` + `/push-history/{id}` + `/push-history-stats` 3 路由;前端 `PushHistoryPage.vue` 全屏 + `MePage` 缩略;**顺手修 inbox 渠道 unknown bug**(inbox 不在 notifier 注册表,在 `_render_and_send` 单独标 ok);详见 `docs/day9-deliverable.md` | ✅ |
| **Day 10 hotfix** | notifier GBK 死循环 + send_all http_status 透传 | `src/notifier/__init__.py` 4 处 print → `logging.info/warning` + ASCII `[OK]/[FAIL]`;`scripts/subs_scheduler.py` 加 win32 TextIOWrapper(同 api_server.py 模式);`send_all` 透传 dict 不再当 bool;新记录 `feishu.status=200 err=`,老 3 条 GBK 失败留作对照;详见 `docs/day10-hotfix-push-gbk.md` | ✅ **今日(hotfix)** |
| **Day 10 hotfix #2** | 今日排行升级为冲击榜单 | `/api/hot` 重构加 `mode=category` / `max_per_category`;**新增** `/api/hot/categories` 一次返 7 类目 TOP N;`HotPage.vue` 重写「总榜 TOP 10 + 分榜汇总」双区(🥇🥈🥉 加冕);`MobileHot.vue` 同步升级(横滑 tab + 单列卡);emoji 全换 lucide icon;详见 `docs/day10-hotfix-hot-leaderboard.md` | ✅ **今日(hotfix)** |
| **Day 10+** | SourcesPage TS 修复 + track_entity prompt 优化 + P-TEST 演练 + BSON Date 迁移 | SourcesPage.vue `columns` 加类型 cast;LLM prompt 剥"动态""最新"等修饰;「已转为订阅 #xxx」加跳订阅编辑;用 tester 跑一遍 convert_topic 全链路;统一 `now_utc()` 改 BSON Date(Day 7 留下的债);**+ HF-1 清理 53 处 print 含 ✗/✓**(其它 CLI/smoke/admin_sources 可选批量换 logging) | ⏳ |
| **Day 11** | 失败源修复 + 同类替换 + upsert_item_async _id bug | **cls** 改走主页 SSR JSON 抓取(`fetch_cls_home`,正则抠 `hotArticleData` + `json.loads(strict=False)`);**huxiu** 替换为 **leiphone 雷锋网**(科技/AI 同类,实测 RSS 200 + 600KB+ feed);**autohome** 直接 disable(官方 RSS 404 + SPA + API 封闭,标 Phase 4);**顺手修 `upsert_item_async` _id immutable bug**(pymongo insert 失败 mutate dict 后 update 触发 immutable field 错误,update 前 pop `_id`);详见 `docs/day11-deliverable.md` | ✅ **今日** |
| **Day 12** | HF-1 收尾(53 处 print 改 logging + ASCII) | CLI / smoke / admin_sources 批量替换 `print(\"✓...\")` 为 `logging.info(\"[OK] ...\")`;admin API smoke 同步;保留原始 GBK-safe 输出给 win32 控制台 | ⏳ 下一棒 |

**更新节奏**:每日完工 → 写 `docs/day{N}-deliverable.md` → 回填本文件 §1 / §5 / §6 相应章节。

### 9.1 DevOps 升级横切路线(2026-07-04 v1.1,详见 `docs/deploy-runbook.md`)

| Day | 主题 | 关键交付 | 状态 |
|---|---|---|---|
| **Day 5** | Git + GitHub 仓库 + Actions 骨架 | git init / push GitHub / ci.yml / 第一个 PR 合 main | ⏳ |
| **Day 6** | 三环境模型 + 完整部署手册 v2.0 | `docs/deploy-runbook.md`(L/S/P 三环境 + 一键部署) | ✅ **已完成** |
| **Day 7** | 服务器首次部署 + 日常迭代上线 | 腾讯轻量 Lighthouse 2C2G 跑通 + `scripts/deploy-prod.sh` | ⏳ 下一棒 |
| **Day 8** | 生产环境 + 域名 | 腾讯云 MongoDB + 域名 + Cloudflare + HTTPS(对应 ADR-014/015) | ⏳ |
| **Day 9** | 回滚演练 + 多副本 | 镜像 tag + 切 tag 回滚 + 1 分钟恢复(对应 ADR-017) | ⏳ |

**2026-07-04 调整**(原 Day 5 GitHub Actions 路线**暂缓**):
- 单人项目不再需要 GitHub Actions 自动构建 — 服务器本地 build 够用(2C2G 5-15min,Daily deploy N 次可接受)
- TCR 镜像仓库暂缓 — Docker Hub 公开仓库 + 服务器本地 build 已能完整支持迭代
- Day 6 的核心交付改为:**完整部署手册 v2.0**(`docs/deploy-runbook.md`),统一三环境发布模型
- 详细部署指令 / 端口 / env / 故障定位 / [Agent]/[User] 责任划分,全部在该文档

**与业务 day 路线并行**:DevOps 升级是横切工程化,不影响业务 day 5-6+ 的功能迭代。两者可同日推进(上午 dev,下午 devops)。

---

## 10. 关键决策 / ADR 摘要

完整决策见 `docs/adr/0001-tech-stack.md`,这里只列概要:

| 编号 | 决策 | 理由 |
|---|---|---|
| ADR-001 | MongoDB + Redis(无 Postgres)| 单机够用,文档友好,避开 Docker 启 DB |
| ADR-002 | Python venv(no Docker for Python)| ECS 2C2G 跑不起容器化 Python 堆栈 |
| ADR-003 | M3 主 + K2.6 备(不依赖单一)| 1 main + 1 backup 单 key 降级也 work |
| ADR-004 | Kimi 用 Anthropic 协议 | 实测 OpenAI 协议 401(`api.moonshot.cn/v1`),Anthropic 协议 200(`api.kimi.com/coding/v1`)|
| ADR-005 | ingest / subs 解耦 | 性能:subs 毫秒级;语义:管理员视图 vs 用户视图 |
| ADR-006 | 公共 items + per-user subs | 一篇文章一次摘要,多用户共享(broadcast 模型)|
| ADR-007 | v1 MongoDB text,v2 LanceDB + DashScope | 降级路径明确 — 本机随时能用 v1,DashScope 用于 v2 精度提升 |
| ADR-008 | 自家 cron 解析(不上 APScheduler) | 5 行代码解决,少一个依赖 |
| ADR-009 | 滚动交付:by-day 版本 | 用户明确要求 |
| ADR-010 | GitHub 仓库 + GitHub Actions(2026-07-03) | 生态全、免费额度够、单人项目不需要复杂审批流 |
| ADR-011 | GitHub Flow 简化(无 develop/release/hotfix)(2026-07-03) | 项目小、tag 替代 release 分支 |
| ADR-012 | 腾讯云 TCR 做镜像仓库(2026-07-03) | 同地域免流量、推送快、私有仓库安全 |
| ADR-013 | 5 个服务拆 5 个镜像(不合并)(2026-07-03) | 镜像更新粒度细、问题定位快 |
| ADR-014 | 腾讯云 MongoDB 4C4G(不自装)(2026-07-03) | 数据不能丢、2C2G 装不下 mongo+app、备份免运维 |
| ADR-015 | Cloudflare 反代 + 免费证书(2026-07-03) | 免备案、隐藏真实 IP、配置简单 |
| ADR-016 | staging / prod 共用一台(用 compose -p 隔离)(2026-07-03) | 单台 2C2G 跑两套浪费、命名空间隔离够用 |
| ADR-017 | 回滚 = 切 tag 重 pull(不保留旧容器)(2026-07-03) | 镜像不可变 + tag 锁版本 = 确定性回滚 |

**反面决策**(不做):
- ❌ 本地 Embedding 模型(BGE-M3):ECS 2C2G 装不下,Win+Py3.14 安装各种炸
- ❌ Rust API 网关:Python FastAPI 直接够,memory 切割、admin latency 优势不再重要
- ❌ Postgres / Cassandra / Kafka / Spark:MVP 阶段不上
- ❌ Web Console 上 Day 5(不在前 4 天 MVP)
- ❌ 邮件 / Slack / Discord 推送:in-app + CLI 优先

---

## 11. 已知问题 / 限流 / TODO

| ID | 问题 | 影响 | 状态 |
|---|---|---|---|
| ISSUE-001 | huxiu RSS `ReadTimeout` 持续 | 抓不到该源,subs 走 `categories=[科技]` 仍可补 | Day 3 改走热搜 API 兜底 |
| ISSUE-002 | categories 软匹配是临时方案 | LLM 输出"AI芯片/融资"等细分类,跟用户 `categories=['AI']` 对不上 | Day 4 改 LLM prompt 输出固定二级标签 `["AI","科技","财经","汽车","娱乐","体育","其他"]` |
| ISSUE-003 | 没有真正的 scheduler daemon | `subs run` 必须手动(CLI)或靠 ingest_daemon 触发外推 | Day 3 加 `subs_scheduler.py`(cron 触发)|
| ISSUE-004 | ingest_daemon 进程级轮询非 systemd | ECS 上需要 systemd unit 兜底 | 文档已带 §5.3 部署说明,Day 3 加 unit 文件 |
| ISSUE-005 | ~~FastAPI 未上~~ → **已 Day 2 实装,smoke 13/13 通过** | — | ✅ 已关闭 |
| ISSUE-006 | 没有 retrieval 层 v2 | 仅 MongoDB text search,精度受限 | Day 4 |
| **NEW-1** | MongoDB text 索引对中文检索差 | "量子位" 0 命中,英文词正常 | Day 4 切 BGE-M3 / DashScope ⚠️ **未切,Day 5 不在范围** |
| **NEW-2** | Redis 当前没被代码使用 | docker daemon 没起 + 代码无 Redis 调用,"队列/去重"是文档理想 | 推迟(Day 5+ 真用上时再接) |
| **NEW-3** | LLM 摘要 prompt 在 3 处各写一份 | CLI / daemon / `fetch_and_summarize.py` 格式飘忽 | Day 3 抽到 `src/llm/prompts.py` |
| **NEW-4** | CLI 与 API 鉴权体感割裂 | CLI `.session.json` vs API `Authorization: Bearer` | 短期接受,Day 5+ 写统一前端收口 |
| **NEW-5** | NL 解析失败兜底"用前 15 字 + 5 汉字" | 用户体感差 | 改成显式提示"解析失败,用了默认值" |
| **NEW-6** | `nl_parse` max_tokens=500 偏小 | JSON 偶被截 | 提到 800 |
| TODO-001 | ✂️ 自动化测试未覆盖(auth / subscription / api) | | Day 3 加 `tests/` 套件 |
| TODO-002 | 🪵 ingest-daemon 日志缺轮转 | | Day 3 |
| TODO-003 | 📦 requirements.txt 未 pin 版本 | | Day 3 |
| TODO-004 | 🔒 CORS `allow_origins=["*"]` 生产有风险 | | Day 5+ |
| TODO-005 | 🛡 鉴权只 401,无 403 / role 细分 | | Day 5+ |
| TODO-006 | ⚠️ 无限频 / IP 黑洞名单,抓取可能被 ban | | Day 3+ |

---

| ISSUE-001 | ~~huxiu RSS `ReadTimeout`~~ | huxiu 多镜像 fallback 已解 | ✅ **Day 5 已关闭** |
| **NEW-7** | 小红书/抖音/微博 scrape 易被风控 | 数据源稳定性问题 | Day 5 仅删 XHS demo,待 Phase 4 接 X v2 / 微博 OpenAPI |
| **NEW-8** | admin API 当前公开,前端未鉴权 | source_admin/* 全公开 | 待 role-based guard |
| **NEW-9** | 告警 webhook 走 env,未抽到 Notifier 框架 | 当前用 `httpx.post(webhook, json=payload)` | 下一轮抽到 `notifier.send_all(user, ['webhook'], ...)` |
| **Day 5** | source_runs 自动禁用的 source_config 联动 + alarm | ✅ 已上线 | ✅ 关闭 |
| **P-CLEAN** | 代码清理：移除 feishu_dm 孤儿渠道、_id 统一 ObjectId、去掉过度 fallback | ✅ 已完成 | ✅ 关闭 |
| **P-MIGRATE** | admin 的 _id 从 `"u_admin"` 迁移到 ObjectId（init_admin.py 已改，存量 admin 需重建） | 重建：`python scripts/init_admin.py --username admin --password xxx --reset` | ⚠️ 需手动执行 |
| **NEW-10** | 批量启停无确认弹窗 + 无 undo | 直接 toggle 可逆,误操作可立即恢复;后续加 history 再 undo | Day 7+ |
| **NEW-11** | "仅显示异常源"是前端筛,不分页联动 | 一次性筛到底,源 >100 再改后端 | Day 7+ |
| **NEW-12** | ~~`source_config.l1` 全是 `""`,SourcesPage L1 筛选永远 0 命中~~ | 根因:`_default_for_rss/_kol` 写死 `l1=""`,seed 没读 `SOURCE_L1_DEFAULT`。修复:`seed_from_registry` 显式读 `SOURCE_L1_DEFAULT.get(sid, "其他")`;存量跑 `scripts/backfill_source_l1.py` 回填(幂等)。 | ✅ Day 6.5 已关闭 |
| **NEW-13** | ~~失败源未修复:cls/wallstreetcn 公开端点 418/404,bilibili RSS empty feed,weibo KOL 公开 scrape 被风控 302,huxiu 全网 timeout,autohome /rss 已下~~ | 根因分类:①官方 RSS 已下线(autohome/wallstreetcn) ②公开 scrape 风控(weibo×2/huxiu) ③RSS 端点失效(bilibili) ④公共 API 风控(cls)。修复:①cls/wallstreetcn → RSSHub 多镜像(rssforever/injahow/rsshub.app) ②bilibili → 官方 JSON API(web_location=333.934 白名单)+ fetch_bilibili_hot fetcher ③huxiu/autohome/weibo×2 → disable 标记原因 ④新增 zhihu_hot(RSSHub) + weibo:hot(头条 JSON,补热搜缺口)。详见 `docs/day6v2-fixes.md`。 | ✅ Day 7 hotfix 已关闭 |
| **NEW-14** | 公共 RSSHub 镜像偶尔 503 | cls/wallstreetcn/zhihu_hot 单次可能 fail,但 mirror fallback 三镜像轮询后总有一个能用;30min daemon 自动重试 | 接受,持续观察 |
| **NEW-15** | `weibo:hot` 实际走头条 JSON,source_id 名实不符 | 已更新 display_name="热搜词热榜";source_id 保留避免 Mongo 数据迁移 | 接受 |
| **NEW-16** | 微博用户 KOL(weibo:1887344341/weibo:1643971635)缺失 | 财经/社会类 KOL 暂缺 | Phase 4 接 Weibo OpenAPI 后恢复 |
| **Day 9** | 转订阅 `RuntimeError: asyncio.run() cannot be called from a running event loop` | `convert_topic_to_sub` 拆 LLM/写库,FastAPI handler 改 await,修好 | ✅ **Day 9 已关闭** |
| **NEW-17** | `frontend/src/pages/admin/SourcesPage.vue` TS 严格性报错(`columns` 类型不严格匹配 Naive UI `TableColumns<any>`) | 历史(Day 6 留);`vite build` 跳过 vue-tsc 不影响产物 | Day 10+ |
| **NEW-18** | 转订阅后 topic 详情页"已转为订阅 #xxx" 没有跳订阅编辑的链接 | 用户改不了新增的短期订阅 | Day 10+ |
| **NEW-19** | `track_entity` 直接用 `parsed.title`,LLM 没单独识别实体(「王力宏动态」存的就是"王力宏动态",没剥掉"动态") | 短期能用,但精准度有限 | Day 10+ prompt 优化 |
| **HF-1** | 其他 53 处 print 含 ✗/✓(CLI / smoke / admin_sources / fastinfo.py 等) | 同根症状,但**不阻塞推送链路**;仅在用户手动跑这些脚本时控制台喷 UnicodeEncodeError | Day 10+ 批量清理 |
| **HF-2** | push_history 时间字段是 ISO 字符串,非 BSON Date(Day 7 留下的债) | 字典序碰巧 == 时序,短期不致命 | Day 10+ 主线 |
| **HF-3** | `send_all` 在 Day 9 改造时把 `notifier.send()` 返的 dict 当 bool 判 `if ok:`,真实 `http_status` 被丢成 None | push_history status 字段永久 None | ✅ **Day 10 hotfix 已关闭** |
| **HF-4** | notifier `_post_webhook` 在 try 块内 print 含 `\u2717` → GBK stdout 抛 UnicodeEncodeError → 冒泡到 FeishuNotifier.send → send_all except 写成「推送失败」 | push_history 误标 `trigger='schedule'` 飞书全失败 | ✅ **Day 10 hotfix 已关闭** |
| **HF-5** | 总榜模式每 L1 最多 3 条,某些类目热门内容(>8 条同时高热度)被压到第 4 位及之后 | 用户想看完整榜单点左侧分类即可,但有"第 4 名就不上榜"的反直觉 | 已通过 `mode=category` + `/hot/categories` 解决 | ✅ **Day 10 hotfix #2 已关闭** |
| **HF-6** | mobile `/m/*` 路由没嵌套在 `/m` 父路由下,顶 nav 走 PC 版 `DefaultLayout` | mobile 主题可读但顶部混搭 PC nav | Day 10+ 路由重构 |
| **HF-7** | 暗色模式未适配(渐变色 + 浅文字对比可能不够) | 截图深色模式需另测 | Day 10+ |
| **HF-8** | `upsert_item_async` duplicate 时 update 触发 `WriteError: Performing an update on the path '_id' would modify the immutable field '_id'` | pymongo `insert_one` 失败 mutate item dict 自动加 `_id`,catch 块 update 时把 mutated dict `$set` 进去触发;任何源第二次抓相同 url 都会假死 | 修复:update 前 `{k: v for k, v in item.items() if k != "_id"}` 过滤掉 `_id` | ✅ **Day 11 已关闭** |
| **NEW-20** | 汽车类源暂缺(autohome 已 disabled) | 汽车资讯低频需求,Phase 4 评估易车 / 盖世 / 汽车之家新能源板块 / RSSHub autohome route | Phase 4 |
| **NEW-21** | cls 主页 Next.js SSR 结构变化风险 | 升级 schema 后正则失效,抓取 fail;5 次连续失败自动 disable 兜底 | 接受 — `source_runs.consecutive_fails` 自动 disable 兜底 |
| **NEW-22** | `feishu` / `wechat` / `webhook` / CLI / smoke / admin_sources 53 处 print 含 ✗/✓ 未统一改 logging | 用户手动跑这些脚本时控制台喷 GBK UnicodeEncodeError;但生产 daemon 不受影响(Day 10 hotfix 已修 notifier 推送链路) | Day 12 HF-1 收尾批量清理 |
| **NEW-23** | 公共 RSSHub 镜像 2026-07-05 大面积死(rsshub.app / injahow / rssforever 大量 path 404) | cls / zhihu_hot / wallstreetcn 受影响;cls 已切换主页 JSON 抓取;zhihu_hot / wallstreetcn 还在 RSSHub 多镜像 fallback,单次失败就 fail,下次轮询可能成功 | 长期观察,Phase 4 评估自建 RSSHub / 私有镜像 / 付费源 |

---

## 12. 测试 & 验证清单(每个 day 完工都要走一遍)

```powershell
# 基础设施
docker ps | Select-String "fastinfo-redis"           # Redis 跑(可选,代码目前不依赖)
mongosh --eval "db.adminCommand('ping')"             # Mongo 跑

# Python
. scripts\activate.ps1                               # venv 激活
pip list | Select-String -Pattern "motor|httpx|redis|feedparser"
python examples\smoke_test.py                        # 4/4 通过(LLM + Redis + fallback)
python examples\api_e2e_smoke.py --no-ingest         # 13/13 通过(API 全链路)
python examples\api_e2e_smoke.py                     # 含真实 ingest(会调 LLM)

# 启动服务
python scripts\ingest_daemon.py --once               # 后台抓 + 摘要
python scripts\api_server.py                         # FastAPI 启动

# 数据链路
python fastinfo.py hot --limit 5                     # 热点可见
python fastinfo.py subs run <id> -v                  # 推送 visible
curl http://127.0.0.1:8000/healthz                  # API 健康
curl http://127.0.0.1:8000/api/stats | python -m json.tool

# 单元 / 集成
python scripts\test_search.py                        # Mongo text search
python scripts\test_subscription.py                  # 订阅存储
python fastinfo.py stats                             # MongoDB 状态 / 索引
```

回归通过标准:
- ✅ smoke test 4/4
- ✅ **api_e2e_smoke 13/13**(Day 2 新增)
- ✅ ingest 一次新增 ≥ 10 条
- ✅ hot 命令展示 ≥ 3 条 relevance ≥ 0.7
- ✅ subs run 第一次 `delivered > 0`,再次 `delivered = 0`(去重 OK)
- ✅ CLI `stats` 列出 4 个表的索引
- ✅ `curl /healthz` 返回 `mongo_version` 字段
- ✅ **notifier GBK hotfix 验证(Day 10)**: `python fastinfo.py subs run <id>` 后 `db.push_history.find({'trigger':'cli'}).sort('sent_at',-1).limit(1)` 的 `channel_results.feishu.http_status == 200` 且 `error == null`

---

## 13. 更新约定(必须遵守)

> 📌 **每次 day-end 迭代完工后,必须回填本文件。**

具体动作:
1. **§1 「现状速览」** 更新日期、Day 编号、"数据"行(行数 + 新订阅数)
2. **§4 「目录结构」** 同步新文件、新脚本、新模块
3. **§6 「使用教程」** 加新 CLI 命令、新用法
4. **§9 「路线图」** 标 ✅ 已完成 → 填 ⏳ → 下一日加一行
5. **§11 「已知问题」** 关掉旧 issue、开新 issue
6. **§12 「测试清单」** 增删对应 test 命令
7. 新建 `docs/day{N}-deliverable.md`(模板见 §13.1),作为本次迭代的人/agent 友好的完整复盘

### 13.1 `day{N}-deliverable.md` 模板

```markdown
# fastInfo · Day {N} 交付
日期:YYYY-MM-DD · 状态:✅ 完成 / 🟡 部分

## 🎯 目标
## ✅ N 件事
### 1. 子项
## 🛠️ 改动(表)
## 📊 当前数据
## 🧪 验证命令
## ⚠️ 已知 / 推迟
## 🚀 Day {N+1} 预告
```

---

*Last updated: 2026-07-05(Day 11 — 失败源修复 + 同类替换:cls 改主页 JSON / huxiu 替换 leiphone / autohome disable / 顺手修 upsert_item_async _id bug,详见 docs/day11-deliverable.md)* · *Next update: Day 12(HF-1 53 处 print 改 logging)完工时*
