# fastInfo 📡

> 一个面向知识工作者的 AI 情报中枢:RSS + 主流社媒聚合 + 主题订阅 + LLM 摘要 / 简报 / 研报。

> 📌 **AI agent / 接手者入口**:**[`AGENTS.md`](./AGENTS.md)** — 项目架构 / 方案 / 教程 / 迭代节奏都在那儿。本 README 是对外 facing 简版。

## 当前状态

```
Day 1 · 2026-06-30 · MVP2 入门口(架构解耦 + 后台调度)
├── ✅ Day 1 完成       docs/day1-deliverable.md
├── ⏳ Day 2 待办       FastAPI 化(/search/today/hot/subscribe/items/stats)
├── ⏳ Day 3 待办       扩源(RSS+热搜 API)
└── ⏳ Day 4 待办       v2 检索(DashScope Embedding + LanceDB + RRF)
```

## 本机架构(零订阅)

```
┌──────────────────────────────────────────────┐
│  本机                                        │
│                                              │
│  MongoDB(你已有)         主存储              │
│       ↓                                     │
│  Rust API(Axum)         API 网关            │
│       ↓                                     │
│  Redis(Docker)          队列 / 缓存 / 限流  │
│       ↓                                     │
│  Python Crawler+AI       采集 / 摘要 / 嵌入  │
│       ↓                                     │
│  BGE-M3 本地            Embedding           │
│  LanceDB 嵌入式         向量检索             │
│                                              │
│  远程: MiniMax-M3 + Kimi K2.6(双机容灾)   │
└──────────────────────────────────────────────┘
```

## 5 分钟启动

### 1. Docker 一键启动(推荐)

```powershell
cd D:\WORK\trae\fast_info

# 首次构建 + 启动 Mongo / Redis / API / Web / Docs
docker compose up -d --build

# 打开
# Web:  http://127.0.0.1:8080
# API:  http://127.0.0.1:8000
# Docs: http://127.0.0.1:8080/docs/

# 健康检查
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8000/healthz
```

默认 Docker 环境使用内置 MongoDB(`fastinfo-mongo`)和 Redis(`fastinfo-redis`)。
Mongo 映射到宿主机 `27018`,避免和本机已有 `27017` 冲突。

如需启用后台抓取与订阅调度:

```powershell
docker compose --profile workers up -d --build
```

真实 LLM 抓取需要先在 `docker/env.docker.example` 或自定义 env 文件中配置 `MMX_API_KEY` / `KIMI_API_KEY`。

常用命令:

```powershell
docker compose ps
docker compose logs -f api
docker compose down
```

如果 Docker Hub 拉镜像超时,可临时切国内镜像前缀再启动:

```powershell
$env:DOCKER_REGISTRY_PREFIX = "docker.m.daocloud.io/library/"
docker compose up -d --build
```

### 2. 基础设施(Docker,旧式本机开发)

```powershell
# Redis(已就绪,验证下)
docker ps                                      # 应看到 fastinfo-redis
docker exec fastinfo-redis redis-cli ping       # 应返回 PONG

# 如需停 / 启
cd D:\WORK\trae\fast_info
docker compose down                            # 停
docker compose up -d redis                     # 起
```

### 3. Python 虚拟环境(**强烈推荐**)

**venv 隔离,ECS 部署必须用** —— 避免污染系统 Python。

**Windows 本机**:
```powershell
cd D:\WORK\trae\fast_info
python -m venv .venv --prompt fastinfo
.venv\Scripts\Activate.ps1                       # 激活(看到 (fastinfo) 前缀)
pip install -r requirements.txt
```

**Linux / ECS**:
```bash
cd /opt/fast_info                # 或你部署的目录
python3.12 -m venv .venv --prompt fastinfo
source scripts/activate.sh        # 便捷脚本(自动激活 + 提示)
pip install -r requirements.txt
```

### 4. 一键激活(我已写好脚本)

```powershell
# Windows
. scripts\activate.ps1

# Linux / ECS
source scripts/activate.sh
```

激活后任何 shell 都在 venv 里跑,Python 可执行文件自动指向 `.venv/Scripts/python.exe`。

### 5. 环境变量

> ⚠️ 安全提醒:请先在 minimaxi.com 和 platform.moonshot.cn **rotate 一次 API key**(因为它们曾经出现在我的对话历史里)。

```powershell
# 把 .env.example 复制为 .env,然后填入真实 key(或者直接用环境变量)
copy config\.env.example .env

# 或 PowerShell 直接设置(本会话有效)
$env:MMX_API_KEY = "sk-..."
$env:KIMI_API_KEY = "sk-..."
$env:REDIS_URL = "redis://127.0.0.1:6379"
```

### 6. 跑烟雾测试

```powershell
$env:PYTHONPATH = "."
python examples/smoke_test.py
```

期望看到:
- [1/4] Redis PONG ✓
- [2/4] API Key 已加载 ✓
- [3/4] short_summary 调用成功,内容显示 ✓
- [4/4] Fallback 测试成功(模拟 M3 失败,K2.6 顶上)✓

## 项目结构

```
fast_info/
├── docs/                                      # 方案文档
│   ├── fastInfo-可行性技术方案-v1.0.md        # 主方案
│   ├── fastInfo-技术栈本地化与模型组-v1.1.md # 模型组 + 本地化设计
│   ├── adr/0001-tech-stack.md                 # 技术决策记录
│   └── schema/schema-v1.sql                   # (Mongo 版后续替换)
├── config/
│   └── .env.example                           # 环境变量样例
├── src/
│   ├── llm/
│   │   └── model_registry.py                  # ⭐ M3 + K2.6 路由(可直接搬)
│   ├── api/                                   # Rust API(待建)
│   └── crawler/                               # Python 爬虫(待建)
├── examples/
│   └── smoke_test.py                          # 烟雾测试
├── scripts/                                   # 运维脚本
├── data/                                      # 本地数据(gitignore)
├── docker-compose.yml                         # Redis(已起)
├── requirements.txt
├── .gitignore
└── README.md(本文件)
```

## 模型组速查

| 组名 | 用途 | 主(M3)权重 | 备(K2.6)权重 |
|---|---|---|---|
| `short_summary` | < 500 字短摘要 | 80 | 20 |
| `long_summary` | 长摘要 / 简报 | 60 | 40 |
| `deep_interpretation` | 研报级深度解读 | 70 | 30 |
| `nl_parse` | NL → 结构化(订阅解析) | 80 | 20 |

每个组都配:熔断(30% 错误率) + 冷却(指数退避上限 30 分钟) + Provider 内 retry 2 次。
详见 `src/llm/model_registry.py`。

## 路线图

| 阶段 | 周 | 目标 |
|---|---|---|
| **MVP 0** | W0(本周) | Redis + 模型路由跑通 |
| **MVP 1** | W1-W2 | RSS 采集 + 摘要 + 检索 CLI |
| **MVP 2** | W3-W4 | 订阅引擎 + Web Console |
| **MVP 3** | W5-W8 | 搜索 API 接入(微博/抖音/X) + 研报生成 |

详细里程碑见 `fastInfo-可行性技术方案-v1.0.md`。

## 安全提示

- 真实 API Key **不要**写进 `.env` 文件后 commit 到 git(`.gitignore` 已经忽略了 `.env`)
- 定期 rotate key
- 模型路由日志不会打印 key,但会打印 provider id,如有问题可以查日志定位
