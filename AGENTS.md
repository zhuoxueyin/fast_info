# AGENTS.md · fastInfo 项目入口

> 面向 AI agent / 后续接手者 / 自己回看 -- **从 0 到产出,这份文档讲清一切。**
>
> 📌 **本文件必须随 day-end 迭代回填**(详见末尾 §13 「更新约定」)。
>
> 📚 深度方案在 `docs/`:主方案 v1.0 / 本地化方案 v1.1 / MVP 方案 v1.0 / 各 day-N 交付文档。

---

## 0. 项目一句话

**fastInfo = AI 驱动的资讯情报中枢** -- 用户用自然语言对话告诉系统"想看什么",AI 从统一资讯池里为他持续订阅 / 临时生成 / 主动推荐。

**三个参照面**:
1. **差异化 vs 传统资讯**(微博/头条/今日头条):那些人**主动推荐 / 用户主动浏览**;我们**AI 驱动 + 用户 NL 自定义 + AI 协同分发** -- 主动权反转。
2. **差异化 vs 传统 RSS 工具**(Feedly/Inoreader):那些人**手动选源 + 关键词过滤**;我们**NL 对话一句话建订阅**,无需懂 RSS 协议。
3. **差异化 vs 算法推荐**(抖音/小红书即刻 feed):那些人**被动接信息流**;我们**主动表达 + 持续精确供给**。

**关键场景**:用户说"今天想关注世界杯" → AI 从统一资讯池为他聚合 + 摘要 + 推送(世界杯例子可以是临时兴趣,不必建长期 sub)。

**边界**:BYOK(自带 LLM key)+ 本地优先 + 零数据外传。

---

## 1. 现状速览(2026-07-04,Day 7 ✅)

| 维度 | 当前 |
|---|---|
| 阶段 | **MVP7 · 主流覆盖 + 触达端到端** (Day 7 v0.4.0 完成,2026-07-04) |
| 最新里程碑 | Day 7:9 类目补源(AI 4/汽车 2/娱乐 2)+ 推送全链路打通(CLI test + API /api/settings + 前端 /settings) |
| 数据 | items 沿用 · `subscriptions` 17+ · `subscriptions_delivered` 143 · `temp_topics` 沿用(TTL) |
| 数据源 | **28 RSS**(+8: Anthropic/OpenAI/DeepMind/HuggingFace + 电动邦/车东西 + 微博热搜/抖音热榜)+ **5 KOL**(不动)|
| LLM | M2.7-highspeed → M2.7 → M3 → K2.6(四级 fallback)+ 翻译复用 short_summary |
| 存储 | MongoDB(主)+ users 集合补 SMTP_PASSWORD / webhook URL 字段(默认脱敏) |
| **推送渠道** | **6 种** 🆕 `feishu_dm` 个人单聊已上线 + 原有 5 种全打通(`inbox`/`email`/`feishu`群/`wechat`/`webhook`)。**CLI `notify test` + API `/api/notifier/test` + 前端 `/settings` 一键测试**。使用详情见 `docs/notifier-feishu-dm.md` |
| 分类 | L1(7)+ L2(30+)|
| 后台 daemon | `scripts/ingest_daemon.py` 30 min/轮 + `scripts/subs_scheduler.py` 60s + `subs_scheduler` 自动跑订阅 + 推送到渠道 |
| 接口 | CLI + **FastAPI(45 OpenAPI 路径)** + Web(**15 页面** = 11 普通(含 SettingsPage)+ 4 admin)+ **Mobile(7 页面**) + Docs(12 篇) |
| 源管理 | `source_config` 多文档 + `source_runs` + `system_alerts` + `Depends(require_admin)` 已加 |
| 源自动化 | huxiu/nitter 多镜像 fallback + 微博 OpenAPI + 翻译 + 🆕 **推送死信队列占位**(Day 8)|
| 部署目标 | 阿里云 ECS 2C2G(~¥30/月)+ DevOps Day 5-9(横切)|
| 代码规模 | `src/` **12 包**(+`notifier/test.py` + `api/routes/settings.py`)+ `fastinfo.py` CLI 14 子命令 + `scripts/` 22 |

详细里程碑:**`docs/day1-deliverable.md`** / **`docs/day2-deliverable.md`** / **`docs/day3-deliverable.md`** / **`docs/day4-deliverable.md`**。

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

### 2.3 数据流(Subscription 一次执行)

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
| **队列** | Redis 7.x(Docker)| 已起容器 `fastinfo-redis`,6379,healthy |
| **后端** | venv Python 3.12(本地);ECS Linux Python 3.12 | 不用 3.14,ML 库兼容性差 |
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
├── docker-compose.yml                                  ← Redis 单服务
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
- **Docker Desktop**(本机已装,Redis 容器`fastinfo-redis` healthy)
- **Python 3.12+**(本机用 3.14 也兼容大部分代码,部署用 3.12)
- **API Key**:MiniMax(主)+ Kimi K2.6(备,二选一必有一个)

### 5.2 一键启动

```powershell
# 1) 克隆 / 进入项目
cd D:\WORK\trae\fast_info

# 2) venv 激活(已建好,直接激活即可)
. scripts\activate.ps1
# Linux: source scripts/activate.sh

# 3) 起 Redis 容器(如果没起)
docker compose up -d redis

# 4) 设环境变量
$env:MONGO_URL = "mongodb://127.0.0.1:27017"
$env:REDIS_URL = "redis://127.0.0.1:6379"
$env:MMX_API_KEY = "sk-..."    # 必填
$env:KIMI_API_KEY = "sk-..."   # 选填,无则降级到单 key

# 5) 初始化 Mongo 索引(首次)
python -c "import sys; sys.path.insert(0,'src'); from storage.mongo_writer import ensure_indexes; ensure_indexes()"

# 6) 烟雾测试(应 4/4 通过)
python examples/smoke_test.py

# 7) 跑一次 ingest 测试
python scripts/ingest_daemon.py --once

# 8) 启 CLI
python fastinfo.py --help
```

### 5.3 ECS 部署(Linux,2C2G)

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
| GET  | `/api/hot?limit=&hours=&threshold=` | 公开 | 今日热点 |
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
| Kimi 调用 401 | 走的协议不对 - **必须** `x-api-key` header + `anthropic-version: 2023-06-01`,endpoint `/v1/messages`(不是 `/v1/chat/completions`)|
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
| **Day 5** | 源可管理 + 可监控 | 19 源 × source_runs + 8 admin API + SourcesPage 升级 + 自动禁用 + 告警 + huxiu/nitter 多镜像 | ✅ **今日** |
| **Day 6+** | **Day 6** | 临时话题 + NL 改订阅 + admin 鉴权 + 翻译 + 扩源 6 个 | v0.3.0,5 维度完成,2 维度留 Day 7 | ✅ |
| **Day 7** | **主流覆盖 9 源 + 触达 4 步(CLI/API/前端/真测)** | **v0.4.0:** AI 从 2 → 6 RSS,汽车从 1 → 3,娱乐 + 2,推送全链路完成 | ✅ **今日** |
| **Day 8** | 推送历史/死信重试 + 移动端 `/m/settings` + 移动端 NL PATCH 按钮 + 检索 v2 起步 | 推送可靠性 + 移动端完整 + 检索升级 | ⏳ |

**更新节奏**:每日完工 → 写 `docs/day{N}-deliverable.md` → 回填本文件 §1 / §5 / §6 相应章节。

### 9.1 DevOps 升级横切路线(2026-07-03 v1.0,详见 `docs/devops-研发部署流程升级-v1.0.md`)

| Day | 主题 | 关键交付 | 状态 |
|---|---|---|---|
| **Day 5** | Git + GitHub 仓库 + Actions 骨架 | git init / push GitHub / ci.yml / 第一个 PR 合 main | ⏳ 下一棒 |
| **Day 6** | 5 服务镜像化 | 5 个 Dockerfile + docker-compose.yml(本机跑通,5/5 健康) | ⏳ |
| **Day 7** | 预发布环境 | 腾讯轻量 + TCR + deploy-staging.sh(staging 自动部署) | ⏳ |
| **Day 8** | 生产环境 + 域名 | 腾讯云 MongoDB + 域名 + Cloudflare + deploy-prod.sh(审批) | ⏳ |
| **Day 9** | 回滚演练 | 故意发坏版本 → 切 tag 回滚 → 1 分钟恢复 | ⏳ |

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
| ADR-007 | v1 MongoDB text,v2 LanceDB + DashScope | 降级路径明确 - 本机随时能用 v1,DashScope 用于 v2 精度提升 |
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
| ISSUE-005 | ~~FastAPI 未上~~ → **已 Day 2 实装,smoke 13/13 通过** | - | ✅ 已关闭 |
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
| **NEW-8** | admin API 当前公开 | `source_admin/*` 全部 router 直接 dispatch,无 `Depends(require_admin)` | 工具函数 `api.deps_admin.require_admin` 已实现(`deps_admin.py` 顶部明确"在 require_user 基础上多查一次 users.role");**Day 6 待办**:在 `source_admin.py` 每个 router 加 `Depends(require_admin)`,并在 `require_user` 中加简单 API-key/X-Admin-Token fallback(给 CLI 调试)|
| **NEW-9** | 告警 webhook 走 env,未抽到 Notifier 框架 | 当前用 `httpx.post(webhook, json=payload)` | 下一轮抽到 `notifier.send_all(user, ['webhook'], ...)` |
| **Day 5** | source_runs 自动禁用的 source_config 联动 + alarm | ✅ 已上线 | ✅ 关闭 |
| **Day 5.1** | `require_admin` 函数已建但未接入 source_admin router | admin API 仍公开 | ⏳ Day 6 |
| **Day 5.2** | mobile 页数 7(含 MobileLayout)vs README 6 | 计数口径差异,文档已校准 | ✅ 已关闭 |
| **Day 5.3** | Web admin 页 4 个(AdminHome/Sources/Banner/Tasks)未单独列出 | 补入 §1 / §4 | ✅ 已关闭 |

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

*Last updated: 2026-07-04 09:55 GMT+8(Day 7 完成 · v0.4.0 API · /api 45 endpoints · 28 RSS · 14+7 页面)* · *Next update: Day 8 完工时*

---

## 14. 记忆三件套 / 跨会话持续

> 2026-07-04 07:53 修 OpenClaw 上下文丢失问题后,固化的三层结构。每次新开会话 AI 会按这顺序读,就能 100% 接上。

| 层 | 路径 | 谁加载 |
|---|---|---|
| 1️⃣ 主会话长期记忆 | `~/.openclaw/workspace/MEMORY.md` | OpenClaw 自动注入 system prompt(bootstrap)|
| 2️⃣ 当日日报 | `~/.openclaw/workspace/memory/YYYY-MM-DD.md` | `memory_search` 取(`/date/topic`)|
| 3️⃣ 项目圣经 | `~/.openclaw/workspace/fast_info/AGENTS.md` | `memory_search` 通过 `agents.defaults.memorySearch.extraPaths` 自动命中 |

### 每日完工 checklist(强制)
- [ ] 更新本文件 §1 / §11 / §13(Day 进度 / 新 issue / Last updated)
- [ ] 追加当日 `memory/YYYY-MM-DD.md` §“今日交付” + §“明日计划”
- [ ] 把这次会话我亲口说出的新决策 / 定位原话 回填到 §0 / §10 ADR
- [ ] 重要雷区 → 回填 `MEMORY.md` §“已知雷区”
- [ ] **CHANGELOG 同步**(见 `docs/CHANGELOG-MAINTENANCE.md`)

### 文档索引

跨会话与版本看的东西:

| 文档 | 看什么 |
|---|---|
| **`AGENTS.md`** (本文件) | 全局全貌 · 架构 · 状态 · ADR · 完整路径 |
| **`docs/CHANGELOG.md`** | 跨版本变更轨迹(每个版本 add/change/fix) |
| **`docs/CHANGELOG-MAINTENANCE.md`** | 怎么维护上面的 changelog |
| **`docs/day{N}-deliverable.md`** | 单日交付完整复盘 |
| **`docs/fastInfo-MVP-整体方案-v1.0.md`** | MVP 路径总账 |
| **`docs/devops-研发部署流程升级-v1.0.md`** | DevOps 路线 |
| **`~/.openclaw/workspace/MEMORY.md`** | OpenClaw 主会话长期记忆(不入 git) |
| **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`** | OpenClaw 每日工作日志(不入 git) |
