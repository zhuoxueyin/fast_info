# fastInfo · MVP 整体方案(v1.0)

> 日期:2026-06-30  ·  状态:**MVP 已跑通,待你确认 / 调整**
>
> 本文档把整个 fastInfo 当前的最佳形态**一次性**梳理清楚,包括:
> - 它是什么、能做什么
> - 技术选型(本机 + ECS 2C2G 通用)
> - 完整代码骨架
> - 已经实测通过的部分
> - 后续可演进方向(明确不做哪些)

---

## 1. fastInfo 是什么

**面向知识工作者的 AI 情报中枢** —— 你用自然语言描述"想追踪什么主题",fastInfo 自动:

1. **抓全网资讯**(7 个 RSS 站点 + 后续可接搜索 API)
2. **走 LLM 摘要 + 分类**(M3 主力,K2.6 备用)
3. **存到 MongoDB**(文档 + 全文索引)
4. **支持自然语言订阅**(NL → 结构化 + cron 调度)
5. **CLI 检索 / 推送 / 管理**(本地命令,日后可加 Web)

**当前你能在本机直接用的能力**:抓 RSS → LLM 摘要 → 入库 → 搜索 → 创建订阅 → 立即执行。

---

## 2. 部署形态(本机 + ECS 同一套代码)

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│ 本机(Windows + Python 3.14)│     │ ECS 2C2G(Linux + Python 3.12)│
│                             │     │                             │
│ .venv (Python 3.14 venv)    │     │ .venv (Python 3.12 venv)    │
│ MongoDB 8.2(本机已装)        │     │ MongoDB(阿里云托管)         │
│ Redis via Docker            │     │ Redis(阿里云托管)           │
│ M3 + K2.6(走 API)           │     │ M3 + K2.6(走 API)           │
│                             │     │                             │
│ 用途:开发 + 试跑             │     │ 用途:7×24 生产              │
└─────────────────────────────┘     └─────────────────────────────┘
         ↑                                       ↑
         └────── 同一份代码,只换 .env ──────────┘
```

**为什么同一套**:
- LanceDB / MongoDB / Redis 都是嵌入式或简单部署,跨平台一致
- 业务逻辑全在 Python,Linux 上 pip 一装就跑
- 无 server 进程依赖(没 Qdrant / Milvus 这种需常驻的服务)

---

## 3. 技术选型(已定型)

| 层 | 选型 | 理由 |
|---|---|---|
| **API 网关** | ❌ 不做(MVP 不需要) | Rust Axum 推迟到 v2 |
| **CLI 入口** | Python argparse | 标准库,零依赖 |
| **采集** | Python `feedparser` | 简单、稳定 |
| **存储** | **MongoDB 8.2**(主) + JSONL(临时) | 用户已有,文档型适配 |
| **缓存/限流/队列** | **Redis 7 via Docker** | 轻量,本地 30MB |
| **检索** | **MongoDB text index**(BM25-like)| MVP 够用,无 ML 依赖 |
| **AI 路由** | 自研 `LLMProvider` 双协议 | OpenAI + Anthropic 兼容 |
| **大模型(主力)** | MiniMax-M3(OpenAI 协议,api.minimaxi.com/v1) | 同公司主力 |
| **大模型(备用)** | Kimi K2.6(Anthropic 协议,api.kimi.com/coding/v1) | 容灾 + 长文 |
| **Embedding** | ❌ 不做 | 2C2G 装不下,留 v2 |
| **Web 控制台** | ❌ 不做 | CLI 足够 |
| **调度** | 自写简化 cron + 用户侧 systemd/cron | 够 MVP |

---

## 4. 功能矩阵

### ✅ 已跑通

| 功能 | 实现位置 | 实测 |
|---|---|---|
| RSS 抓取(7 源) | `src/crawler/rss_collector.py` | qbitai / jiqizhixin / infoq / ifanr 4 源 work,24 条/次 |
| MongoDB 写入 | `src/storage/mongo_writer.py` | 24 + 10 条入库,索引 4 个 |
| LLM 双模型容灾 | `src/llm/model_registry.py` | M3 + K2.6 + 熔断 + 冷却 + fallback 链路 ✓ |
| 长上下文兼容 | 同上 | Anthropic Messages 协议 + x-api-key header |
| NL 订阅解析 | `src/subscription/__init__.py` | "每周三看大厂博客" → cron `0 9 * * 3` ✓ |
| 订阅执行 | 同上 | matched 10 / summarized 10 / stored 10 ✓ |
| 全文检索 | MongoDB text index | `search "AI"` 命中 [6.2] 物理 AI 演进 ✓ |
| CLI 工具 | `fastinfo.py` | search / today / subscribe / subs / stats / ingest 8 子命令 ✓ |
| Redis 健康 | Docker 容器 | `fastinfo-redis` healthy ✓ |
| venv 隔离 | `.venv/` + activate 脚本 | 本机 + ECS 通用 |

### ⏸️ 已识别但不修(可后置)

| 项 | 现状 | 影响 |
|---|---|---|
| 3 个 RSS 源失效 | 36kr / huxiu / sspai 的 feed URL 404 或 parse error | 漏抓这些站点 |
| M3 thinking 标签变体没全盖 | 部分条目 `key_points` 落 fallback 默认值 | 摘要结构化字段偶尔缺 |
| fallback 测试有 race | 模拟 M3 不可达时偶尔走 M3 | 偶发,不影响主流程 |

### ❌ 明确不做(MVP 范围外)

- **Web 控制台 / GUI** — CLI 够用
- **Rust API 网关** — 当前 Python CLI 单进程足够
- **本地 Embedding 模型** — 2C2G 跑不动,等用户主动提出
- **邮件 / Webhook 推送** — 暂时 `delivery: in_app` 占位
- **关键词监控 + 自动推送** — 留 v2
- **多平台社媒爬取(微博/抖音/小红书/X)** — 合规风险大,留 v2 用搜索 API
- **行业研报生成** — 留 v2

---

## 5. 完整代码结构

```
D:\WORK\trae\fast_info\
├── .venv/                              # 虚拟环境(已装好)
├── .gitignore
├── docker-compose.yml                  # Redis(本机用)
├── README.md
├── requirements.txt
├── fastinfo.py                         # ★ CLI 入口
│
├── config/
│   └── .env.example                    # 环境变量模板
│
├── src/
│   ├── __init__.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── model_registry.py           # ★ LLMProvider + 双协议(OpenAI/Anthropic)
│   ├── crawler/
│   │   ├── __init__.py
│   │   └── rss_collector.py            # ★ RSS 7 源抓取
│   ├── storage/
│   │   ├── __init__.py
│   │   └── mongo_writer.py             # ★ MongoDB + text index
│   ├── retrieval/
│   │   ├── __init__.py                 # ★ search() + hybrid_search()
│   │   └── (embedder.py, vector_store.py  # v2 留位)
│   └── subscription/
│       ├── __init__.py
│       └── (调度器 v2 留位)
│
├── examples/
│   ├── smoke_test.py                   # 模型组 + fallback 验证
│   └── fetch_and_summarize.py          # W1 端到端 RSS + 摘要 + 入库
│
├── scripts/
│   ├── activate.ps1                    # Windows 激活
│   ├── activate.sh                     # Linux/ECS 激活
│   ├── test_protocols.py               # 协议适配测试
│   ├── test_search.py                  # MongoDB text search
│   ├── test_subscription.py            # NL → Subscription
│   └── test_subscription_v2.py         # 订阅执行
│
├── data/                               # 本地数据(可空,数据实际在 MongoDB)
│
└── docs/
    ├── fastInfo-可行性技术方案-v1.0.md
    ├── fastInfo-技术栈本地化与模型组-v1.1.md
    └── fastInfo-MVP-整体方案-v1.0.md   # ← 本文件
```

---

## 6. 日常使用流程

### 本机(开发)
```powershell
cd D:\WORK\trae\fast_info
.venv\Scripts\Activate.ps1
python fastinfo.py ingest              # 抓 RSS + 摘要 + 入库
python fastinfo.py today --limit 5     # 看最新
python fastinfo.py search "AI 推理"   # 搜索
python fastinfo.py subscribe "..."      # 创建订阅
```

### ECS 部署
```bash
# 1. 上传代码(本机 git push / scp)
scp -r fast_info/ user@ecs:/opt/

# 2. ECS 上
cd /opt/fast_info
python3.12 -m venv .venv --prompt fastinfo
source scripts/activate.sh
pip install -r requirements.txt

# 3. 配环境
export MMX_API_KEY="sk-..."
export KIMI_API_KEY="sk-..."
export MONGO_URL="mongodb://your-aliyun-mongo:27017"

# 4. 第一次跑
python fastinfo.py ingest
python fastinfo.py today

# 5. systemd timer 跑订阅
# /etc/systemd/system/fastinfo-ingest.service
[Service]
ExecStart=/opt/fast_info/.venv/bin/python /opt/fast_info/fastinfo.py ingest
```

---

## 7. 资源占用估算(ECS 2C2G)

| 组件 | 内存 | 备注 |
|---|---|---|
| MongoDB(阿里云托管) | 0(云端) | 推荐买 1C2G 版本,~¥50/月 |
| Redis(阿里云托管) | 0(云端) | 256MB 版,~¥10/月 |
| Python 进程 | ~100MB | RSS + 摘要 + CLI |
| venv + 依赖 | ~150MB | lancedb + pyarrow 是大头 |
| 系统 + 其他 | ~300MB | 操作系统本身 |
| **小计** | **~550MB** | **剩 1.4GB 备用** |

实际只需 2C2G ECS 一台就够了,内存还有富余。

---

## 8. 月度成本(ECS 2C2G)

| 项 | 价格 |
|---|---|
| ECS 经济型 2C2G(包年 ~¥30/月) | ¥30 |
| MongoDB 1C2G(阿里云) | ¥50 |
| Redis 256MB(阿里云) | ¥10 |
| LLM API(单人自用,调 M3 摘要) | ¥10-30 |
| 域名 + SSL | ¥10 |
| **合计** | **¥110-130 / 月** |

---

## 9. 后续可演进(v2+)

如果你用着用着想要更多:

| 需求 | 解法 | 工作量 |
|---|---|---|
| 想要真语义检索 | 加 DashScope Embedding + LanceDB | 半天 |
| 想要 Web 控制台 | 加 FastAPI 后端 + 单页 HTML | 1-2 天 |
| 想要邮件推送 | 加 smtp + 模板 | 半天 |
| 想要关键词监控 | 加 keyword_monitors 集合 + cron 扫描 | 1 天 |
| 想要社媒内容 | 加 Tavily / 七牛云百度搜索 API | 1 天 |
| 想要 Rust API | Axum + tokio 暴露 HTTP API | 3-5 天 |
| 想要分布式 | MongoDB 分片 + Redis Cluster | 1 周(用户量上来再说) |

---

## 10. 决策点(需要你拍板)

| # | 问题 | 我的推荐 |
|---|---|---|
| 1 | MongoDB 在 ECS 上用自建还是阿里云托管? | **托管**(免运维,数据可靠) |
| 2 | Redis 同上 | **托管**(256MB 够用) |
| 3 | venv 用什么 Python 版本? | **3.12**(3.14 不兼容 ML) |
| 4 | 数据盘挂哪里? | `/data/fastinfo/`(lancedb 留 v2) |
| 5 | 域名备案怎么办? | 国内 ECS 必须备案,先内网 IP + SSH 调试 |
| 6 | 多久真正部署? | 看你用 MVP 多久满意 |

---

## 11. 现在就 5 分钟能跑的事

```powershell
cd D:\WORK\trae\fast_info
.venv\Scripts\Activate.ps1

# 验证环境
python fastinfo.py stats
# 输出:  Items 总数: 10  ...

# 抓一波
python fastinfo.py ingest
# 抓 24 条 + 摘要 + 入库

# 试试订阅
python fastinfo.py subscribe "帮我每周三看大厂技术博客更新,包括 Google OpenAI Anthropic"
python fastinfo.py subs list
python fastinfo.py subs run <id>

# 搜索验证
python fastinfo.py search "AI 推理" --limit 3
```

---

## 🎯 一句话总结

**fastInfo MVP = Python 3.12 + MongoDB(全文索引) + Redis + M3/K2.6 双机容灾 + CLI 8 子命令,本机和 ECS 同一套代码,2C2G 完全够用,月成本 ¥110-130。**

剩余 80% 是 nice-to-have(向量检索 / Web / 邮件),MVP 已经能让你日常用了。