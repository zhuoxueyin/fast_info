# 资讯中心 fastInfo · 可行性技术方案

> 版本: v1.1  ·  初版日期: 2026-06-28  ·  更新: 2026-06-29  ·  状态: 草案(待评审)
>
> **v1.1 更新要点**(详见 `fastInfo-技术栈本地化与模型组-v1.1.md`):
> 1. **存储本地化** — 用 MongoDB(已有)+ Redis(Docker)+ LanceDB(嵌入式)替代 PostgreSQL + Redis + Qdrant,实现 100% 开源零订阅本机部署。
> 2. **模型组双机容灾** — 设计 MiniMax-M3(主力)+ Kimi K2.6(备用)优先级 + 熔断 + 冷却三级 fallback 策略。
> 3. **Embedding 单独说明** — M3 / K2.6 不擅 Embedding,推荐 BGE-M3 本地推理(零成本)。

---

## 0. TL;DR

fastInfo 是一个面向知识工作者的 **AI 情报中枢**。核心交付物是 3 件事:

1. **订阅任务引擎**:用自然语言描述"我要追踪什么",系统自动拆解关键词、平台、频率,沉淀成持续任务。
2. **多源情报采集层**:覆盖 AI/科技/财经/体育/娱乐等公开内容源,合规优先,自研爬虫 + 第三方搜索 API 混合策略。
3. **理解与生成层**:对原始内容做摘要、简报、专业解读;支持检索查询、热榜聚合、行业研报。

**推荐技术路线**:Rust(Axum + Tokio)做 API 网关与核心调度;Python 微服务集群做爬虫与 AI 推理;PostgreSQL + Redis + Qdrant 做存储;多模型路由(GPT-4o / Claude Sonnet / DeepSeek / Qwen)按场景降本。

**实施周期**:MVP 8 周,Beta 16 周,GA 24 周。**首期研发预算**:单人单月 ~¥3-5 万(主要是 LLM 调用费 + 云资源)。

---

## 1. 背景与定位

### 1.1 用户痛点

知识工作者(研究员、分析师、产品/投资/媒体人)每天需要消费大量信息,典型痛点:

| 痛点 | 现状 | 期望 |
|---|---|---|
| 信息分散 | 跨 10+ 平台切换 | 一处订阅,统一触达 |
| 噪声高 | 微博/抖音/小红书 80% 与工作无关 | 主题/关键词精准过滤 |
| 解读成本高 | 看完 30 篇文章才形成 1 个判断 | 自动摘要 + 简报 |
| 一次性查询无法沉淀 | 检索完即丢弃 | 一次提问 = 持续订阅 |
| 行业深度跟踪难 | arXiv 每天 200+ 论文、技术博客散落 | 每日 AI 论文推送、模型盘点 |

### 1.2 差异化定位

vs 通用大模型问答(ChatGPT/文心):
- fastInfo **有持续性**:任务持久化、自动调度,不是一次性对话。
- fastInfo **有源控制**:声明来源、可追溯,而不是模型编造。

vs 单一 RSS 工具(Feedly/Inoreader):
- fastInfo **支持自然语言定义主题**,而不是要求用户手动配置 RSS URL。
- fastInfo **内置 AI 解读**,不只是聚合。

vs 实时热榜(今日热榜/Dailyhot):
- fastInfo **覆盖深度内容**(论文/技术博客/行业报告),不限于热榜。
- fastInfo **支持订阅 + 推送**,不只是当下查看。

---

## 2. 调用市场

### 2.1 同类产品能力图谱

| 产品 | 核心定位 | 关键能力 | 弱点 |
|---|---|---|---|
| **Perplexity** | AI 搜索 + Deep Research | 多源检索 + LLM 综合答案;有深度研究模式 | 一次性查询,无订阅任务;国内访问受限 |
| **Feedly (Leo)** | RSS + AI 聚合 | 来源管理 + AI 摘要/过滤;适合持续监控 | 需手动配源;深度解读能力弱 |
| **Glean** | 企业知识管理 | 内部文档 + 公网信息整合 | 重型企业场景,个人版缺失 |
| **Tavily** | AI 搜索 API(底层) | LLM 友好的检索 API;被 LangChain/LlamaIndex 默认集成 | 不是终端产品,需二次开发 |
| **Exa** | 神经搜索 API | 语义级网页检索;支持相似 URL 发现 | 同上,API 层 |
| **Jina AI Reader** | URL → Markdown | 任意网页转干净 Markdown | 纯提取,不聚合 |
| **秘塔 AI / 跃问** | 中文 AI 搜索 | 中文检索 + 联网答案;带学术模式 | 无订阅,无多平台热榜 |
| **今日热榜 / Dailyhot / NewsNow** | 多平台热榜 | 聚合 50+ 平台实时热点;开源可自部署 | 无内容解读,无订阅 |
| **ALAPI** | 第三方数据 API 市集 | 提供热榜/天气/物流等 API | 通用 API,非场景化产品 |

### 2.2 市场空白

fastInfo 要切入的位置:**"AI 搜索的深度"+"热榜的广度"+"订阅任务的持续性"三者交叉**。

市场上要么是 AI 搜索(Perplexity)没持续性,要么是订阅(Feedly)无 AI 解读,要么是热榜(今日热榜)无内容加工。把这三件事做到一起,且面向中文知识工作者,是清晰的差异化点。

### 2.3 商业化空间(供参考)

- 个人订阅:¥39-99/月(对比秘塔 AI 免费 + Perplexity Pro $20)。
- 团队订阅:¥299-999/月/人(对比 Glean $50+/user)。
- API 调用:开发者按 token / 按次 计费(对比 Tavily $0.008/credit)。

---

## 3. 核心功能模块

按需求拆解为 6 大模块:

```
┌────────────────────────────────────────────────────────┐
│ ① 自然语言订阅引擎(NL Subscription Engine)            │
│   - 输入"帮我每天看 AI 推理模型相关论文"               │
│   - 输出 Subscription{keywords, sources, cron, ...}   │
│   - 支持:一次性查询 → 一键升级为订阅                  │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│ ② 多源情报采集层(Multi-source Ingestion)              │
│   - 全网爬取(资讯站点)                                │
│   - 主流社媒(微博/抖音/小红书/X/公众号)              │
│   - 学术(arXiv/HuggingFace/PapersWithCode)           │
│   - 技术博客(GitHub Trending/大厂 blog/Medium)       │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│ ③ 内容理解层(Content Understanding)                    │
│   - 去重 / 去噪 / 正文抽取(Readability)              │
│   - 摘要(短摘要 200 字 / 长摘要 800 字)              │
│   - 简报(每日 / 每周聚合)                            │
│   - 专业解读(行业分析、对比、趋势)                   │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│ ④ 检索与查询层(Search & Query,Rust API)              │
│   - 全文检索 + 向量检索(双路召回)                    │
│   - 时间 / 关键字 / 类型 / 来源 多维过滤              │
│   - 公开 HTTP/JSON API + Web 控制台                  │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│ ⑤ 热点聚合与监控(Hotness Aggregator)                 │
│   - 多平台实时热榜统一视图                            │
│   - 自然语言检索热点                                  │
│   - 关键词监控 + 阈值触发推送                        │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│ ⑥ 行业研报生成(Industry Insight)                     │
│   - 每日 AI 论文推送 / 大厂技术博客追踪               │
│   - 每周新模型盘点 / KOL 观点聚合                    │
│   - 主题研报(用户自定义主题深度分析)                │
└────────────────────────────────────────────────────────┘
```

---

## 4. 系统架构

### 4.1 总体架构图

```
                    ┌──────────────────────┐
                    │   Web Console / App  │  (Next.js / Tauri 可选)
                    └──────────┬───────────┘
                               │ HTTPS / WebSocket
                    ┌──────────▼───────────┐
                    │   API Gateway        │  Axum + Tower Middleware
                    │   - 鉴权 / 限流      │  身份:API Key + JWT
                    │   - 路由 / 协议适配  │  协议:REST + gRPC + WS
                    └──────────┬───────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
│ 订阅引擎    │         │ 检索引擎    │         │ 热榜聚合    │
│ Rust Worker │         │ Rust + Qdrant│        │ Rust + Redis │
└──────┬──────┘         └─────────────┘         └─────────────┘
       │ 调度(发布任务到 Redis Stream)
       ▼
┌──────────────────────────────────────────────────┐
│              Python Crawler Cluster              │
│   - 微博/抖音/小红书/X 适配器(scrapy/playwright)│
│   - RSS / Sitemap 解析器                         │
│   - 通用网页爬虫(reqwest + select)              │
│   - 反爬对抗:代理池 / UA 轮换 / 验证码识别      │
└──────────────────────┬───────────────────────────┘
                       │ 原始内容 → Kafka/Pulsar
                       ▼
┌──────────────────────────────────────────────────┐
│              Content Pipeline (Python)           │
│   1. 去重(URL hash + SimHash)                  │
│   2. 正文抽取(readability-lxml / trafilatura)  │
│   3. 多模型路由摘要                             │
│   4. 向量化(embedding) → Qdrant               │
│   5. 实体识别 / 主题分类                        │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│              Storage Layer                       │
│   - PostgreSQL(元数据 + 用户订阅)               │
│   - Qdrant(向量检索)                            │
│   - Redis(缓存 / 队列 / 限流)                  │
│   - S3 / MinIO(原始 HTML / 图片)               │
└──────────────────────────────────────────────────┘
```

### 4.2 数据流(以"订阅推送"为例)

```
用户创建订阅  →  订阅引擎生成任务定义
                          ↓
                  调度器按 cron 触发
                          ↓
              Crawler 拉取候选内容(去重)
                          ↓
                  Content Pipeline 处理
                          ↓
           Relevance 模型打分(订阅主题相关性)
                          ↓
              LLM 摘要 / 简报 / 解读
                          ↓
              写入用户收件箱 / 推送通知
```

---

## 5. 技术选型

### 5.1 Rust API 框架:推荐 Axum

| 框架 | 优势 | 劣势 | 适用 |
|---|---|---|---|
| **Axum 0.8** ✅ | Tokio 团队维护,Tower 生态,类型安全,易上手 | 0.x 版本,偶有破坏性变更 | 通用 API,本项目首选 |
| Actix-Web | 性能最佳(Actor 模型,极限下比 Axum 快 10-20%) | 与 Tokio 生态解耦,中间件不兼容 | 极致性能场景 |
| Rocket | 易用,文档好 | 迭代慢,生态弱 | 内部小工具 |
| Hyperlane | 轻量,中文社区有声音 | 1.x 未到,生产案例少 | 个人实验 |

**结论**:用 **Axum 0.8**。理由:Tokio 生态完整、tower-http 中间件丰富(trace/cors/compress/timeout 一应俱全)、社区活跃、生产案例多(Cloudflare、Deno、AWS Lambda 自定义运行时均有使用)。

**Cargo.toml 关键依赖**:

```toml
[dependencies]
axum = { version = "0.8", features = ["ws", "macros"] }
tokio = { version = "1", features = ["full"] }
tower = "0.5"
tower-http = { version = "0.6", features = ["trace", "cors", "compression-gzip"] }
sqlx = { version = "0.8", features = ["runtime-tokio-rustls", "postgres", "uuid", "chrono", "json"] }
redis = { version = "0.27", features = ["tokio-comp", "streams"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }
reqwest = { version = "0.12", features = ["json", "stream", "rustls-tls"] }
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
```

### 5.2 爬虫技术栈

| 场景 | 技术 |
|---|---|
| RSS / Sitemap / 普通 HTML | Rust `reqwest` + `scraper`(也可 Python `scrapy`) |
| 复杂 JS 渲染(微博、抖音、小红书、X) | Python `playwright` + `scrapy-playwright` |
| 反爬绕过 | 住宅代理 IP 池 + UA 轮换 + 浏览器指纹 |
| 验证码 | 2Captcha / YesCaptcha 第三方打码 |
| 内容正文抽取 | Python `trafilatura` / `readability-lxml` |

> **重要决策**:复杂社媒(微博/抖音/小红书/X)不直接爬,而是 **优先使用搜索 API**(见 5.5 合规策略)。仅在搜索 API 覆盖不足时,针对单个目标站点做"温和爬取"(频率 < 1 req/s,严格遵守 robots.txt,只取公开数据)。

### 5.3 AI 模型选型

| 用途 | 推荐模型 | 备选 | 理由 |
|---|---|---|---|
| **短摘要(< 200 字)** | DeepSeek V3 / Qwen2.5-72B | GLM-4-Flash | 成本极低,中文质量好 |
| **长摘要 + 简报** | Claude Sonnet 4.5 | GPT-4o / Gemini 2.5 Pro | 长文能力强,结构化输出稳定 |
| **专业解读 / 研报** | Claude Sonnet 4.5 / Opus 4.5 | GPT-5.1 / Gemini 3 Pro | 推理深度强,可控 effort 参数 |
| **Embedding** | BGE-M3 / BGE-large-zh-v1.5 | text-embedding-3-small | 中文检索 SOTA,开源可自部署 |
| **实体识别 / 分类** | GLM-4-Flash / Qwen2.5-7B-Instruct | 本地 Llama-3.1-8B | 轻量任务,本地可跑 |

**成本估算(以 1 万订阅 × 每日 10 篇)**:

| 模型 | 输入价($/mTok) | 输出价($/mTok) | 日成本估算 |
|---|---|---|---|
| Claude Sonnet 4.5 | 3 | 15 | 摘要 ¥150/日 |
| GPT-4o | 2.5 | 10 | 摘要 ¥120/日 |
| Gemini 2.5 Flash | 0.075 | 0.30 | 摘要 ¥5/日 |
| DeepSeek V3 | 0.27 (输入缓存命中) | 1.10 | 摘要 ¥10/日 |

**降本策略**:默认用 DeepSeek V3 / Gemini Flash 处理批量摘要,Sonnet/Opus 仅在用户主动触发"专业解读"时调用。

### 5.4 存储

| 类型 | 选型 | 用途 |
|---|---|---|
| 关系数据 | PostgreSQL 16 | 用户、订阅、任务、内容元数据 |
| 向量数据库 | Qdrant(主) / Milvus(备) | Embedding 检索、相似内容去重 |
| 缓存 + 队列 | Redis 7(Streams) | 任务队列、限流、热点缓存 |
| 对象存储 | S3 / MinIO | 原始 HTML、图片、附件 |
| 全文检索(可选) | Meilisearch | 高级过滤 + 即时搜索 |

### 5.5 合规采集策略 ⚠️

这是本项目 **最重要的风险点**,必须前置决策:

| 平台 | 推荐方式 | 风险等级 |
|---|---|---|
| **官方 RSS / Sitemap**(如 36kr、爱范儿、虎嗅) | 直接拉 | 🟢 低 |
| **arXiv / HuggingFace / PapersWithCode** | 官方 API | 🟢 低 |
| **微信公众号** | 仅采集已关注的公众号 / 接入第三方合规 SCRM | 🟡 中 |
| **微博热搜** | 微博开放平台 API(需企业资质)/ ALAPI 第三方 | 🟡 中 |
| **微博普通内容** | 第三方搜索 API(七牛云/秘塔/Exa) | 🟡 中 |
| **抖音 / 小红书 / X** | **优先用搜索 API**(Tavily/Exa)间接获取 | 🟡 中 |
| **抖音 / 小红书 / X 直接爬** | **MVP 阶段不做**,Beta 阶段评估合规通道 | 🔴 高 |

**核心原则**:
1. **robots.txt 是底线**:严格遵守,违反一票否决。
2. **频率控制**:任意单一目标域名 ≤ 1 req/s,有反爬的站点 ≤ 1 req/5s。
3. **数据脱敏**:不采集个人隐私(手机号、身份证、地理位置),采集到的用户 ID 做 hash 处理。
4. **数据用途透明**:在产品中明示"数据来源 XX,仅供个人研究使用,禁止商业倒卖"。
5. **用户协议 + 版权尊重**:只保留摘要和原文链接,原文版权属于原作者,引用须注明出处。
6. **国内合规**:遵循《网络安全法》《数据安全法》《个人信息保护法》,不上传用户个人信息到境外 API。

---

## 6. 关键模块详细设计

### 6.1 自然语言订阅引擎

**输入示例**:
> "帮我每天看 AI 推理模型相关论文,中文优先,每周一上午发邮件"

**处理流程**:

```
1. LLM 解析(NL → 结构化)
   ↓
   Subscription {
     topics: ["AI 推理模型", "LLM reasoning"],
     sources: ["arXiv", "PapersWithCode", "机器之心"],
     languages: ["zh", "en"],
     schedule: "0 9 * * 1",
     delivery: "email",
     keywords: ["chain-of-thought", "reasoning", "o1", "DeepSeek-R1", "inference scaling"],
     exclude: ["survey"],
   }

2. 调度器持久化(写入 PostgreSQL)

3. 调度器按 cron 触发,从 Qdrant 检索新内容

4. 相关性打分(Embedding 相似度 + 关键词命中)

5. Top-N 内容走 LLM 摘要 → 推送
```

**关键技术点**:
- NL → 结构化:用 GPT-4o 或 Claude 一次性解析,带 JSON Schema 约束。
- 一次查询 → 订阅:在检索 API 响应里增加"一键订阅"按钮,把检索 query + filter 转换为 Subscription。
- 主题漂移检测:每周分析用户实际反馈的"有用/无用",调整关键词权重。

### 6.2 多源情报采集层

**统一抽象**:

```python
class SourceAdapter(Protocol):
    name: str
    source_type: Literal["rss", "api", "html", "social"]
    
    async def fetch(self, since: datetime) -> list[RawItem]: ...
    async def normalize(self, item: RawItem) -> NormalizedItem: ...

@dataclass
class NormalizedItem:
    id: str              # source-specific ID
    url: str
    title: str
    content: str         # 正文(Markdown)
    published_at: datetime
    author: str | None
    metrics: dict        # 阅读/点赞/评论
    language: str
    raw_html_path: str | None  # 指向 S3 原始文件
```

**内置 Adapter 清单**(MVP 阶段目标):

| 类别 | Adapter |
|---|---|
| RSS / 资讯站点 | 36kr / 虎嗅 / 爱范儿 / 少数派 / InfoQ / 机器之心 / 量子位 |
| 学术 | arXiv(cs.AI / cs.CL) / HuggingFace Daily Papers / PapersWithCode |
| 技术博客 | GitHub Trending / Vercel Blog / OpenAI Blog / Anthropic Blog / Google DeepMind |
| 社媒热搜 | 微博热搜(API) / 知乎热榜 / B 站热门 |
| X / Reddit | Tavily / Exa / Jina 间接 |
| 微信公众号 | 第三方合规 SCRM / 人工标注 |

### 6.3 内容理解层

```
RawItem → 去重 → 正文抽取 → 摘要(可选) → 向量化 → 入库
   │         │          │
   │         │          └─→ 多模型路由:
   │         │              - 短摘要(< 500 字):DeepSeek V3
   │         │              - 长摘要(> 500 字):Claude Sonnet
   │         │              - 专业解读(用户主动触发):Claude Opus / GPT-5.1
   │         │
   │         └─→ trafilatura(主) + readability(备)
   │
   └─→ SimHash + URL hash,7 天窗口去重
```

**摘要 prompt 模板**(短摘要示例):

```
你是一个专业的资讯编辑。请基于以下文章生成 200 字以内的中文摘要,
要求:
1. 保留核心事实和数字
2. 标注作者立场(如有)
3. 不引入文章外信息

文章:
{content}

输出格式(JSON):
{"summary": "...", "key_points": ["...", "..."], "category": "AI|科技|财经|..."}
```

### 6.4 检索 API(Rust,Axum)

**核心端点**:

```rust
// REST API 设计(节选)
GET    /v1/search?q=...&from=...&to=...&type=...&source=...&limit=...
GET    /v1/items/{id}
POST   /v1/subscriptions              // 创建订阅
GET    /v1/subscriptions              // 列出订阅
PATCH  /v1/subscriptions/{id}         // 修改订阅
DELETE /v1/subscriptions/{id}         // 删除订阅
POST   /v1/subscriptions/{id}/run     // 立即触发一次
POST   /v1/summarize                  // 单篇摘要
POST   /v1/research                   // 生成研报
GET    /v1/hotboards                  // 多平台热榜
GET    /v1/keywords/{keyword}/timeline // 关键词时间线
WS     /v1/stream                      // 实时推送(SSE 兜底)

// 鉴权
Authorization: Bearer <JWT> | ApiKey <key>
```

**性能目标**:P99 < 300ms(检索),< 2s(摘要),< 30s(研报)。

### 6.5 热点聚合

**数据源**:
- ALAPI 热榜聚合(免费 100 次,付费 ¥10/3000 次)
- NewsNow / Dailyhot 自部署(开源)
- 各平台官方热搜(微博热搜、知乎热榜、B 站热门、抖音热搜)

**关键词监控**:
```
用户设定关键词 → 调度器每 5 分钟扫描全网热榜 →
命中 → 触发推送(站内信 / 邮件 / Webhook)
```

### 6.6 行业研报生成

**模板化生成**:
- 每日 AI 论文推送(arXiv cs.AI/cs.CL 每日新增 + LLM 摘要 + 排序)
- 每周新模型盘点(爬 HuggingFace + GitHub + 官方 blog)
- 主题研报(用户输入主题 → 采集 100+ 来源 → LLM 多步生成大纲 → 逐段填充 → 校验引用)

**研报质量保障**:
- 每段必须挂载原文链接(强制 prompt)
- 关键数据二次校验(用 Calculator 工具验证)
- 章节结构 prompt 控制(强制大纲)

---

## 7. 实施路径与里程碑

### 7.1 总览

| 阶段 | 周次 | 目标 | 关键产出 |
|---|---|---|---|
| **M0** 基础搭建 | W1-W2 | 项目骨架、CI/CD、数据库 | Rust API skeleton,PostgreSQL/Redis/Qdrant 部署 |
| **MVP** 最小可行 | W3-W8 | 核心 4 个场景跑通 | ①RSS 采集 ②短摘要 ③关键词检索 ④固定时间简报推送 |
| **Beta** 多源接入 | W9-W16 | 主流社媒 + AI 解读 | ⑤搜索 API 接入 ⑥研报生成 ⑦订阅引擎 ⑧Web Console |
| **GA** 完整功能 | W17-W24 | 全部需求 + 监控 + 商业化 | ⑨关键词监控 ⑩研报订阅 ⑪API 开放 ⑫团队协作 |

### 7.2 MVP 阶段(W3-W8)详细任务

```
W3-W4: 基础服务
  - Rust API 骨架(健康检查 / 用户鉴权 / 配置)
  - PostgreSQL schema(用户/订阅/内容/任务)
  - 部署:Docker Compose 一键起
  - CI:GitHub Actions,clippy + test + build

W5-W6: 数据采集
  - RSS 采集器(支持 20+ 站点)
  - 正文抽取(trafilatura)
  - 去重(SimHash)
  - PostgreSQL 写入 + S3 原始 HTML 归档

W7: 内容理解
  - 多模型路由(DeepSeek / Gemini Flash)
  - 短摘要 prompt + 结构化输出校验
  - Embedding 入库(Qdrant)

W8: 检索 + 推送
  - 全文 + 向量双路召回
  - REST API(/search / /summarize)
  - 邮件推送(smtp / Resend)
  - 简单的 CLI 调用示例
```

### 7.3 Beta 阶段(W9-W16)详细任务

```
W9-W10: 订阅引擎
  - NL → Subscription(LLM 解析)
  - 调度器(cron 表达式解析,tokio-cron-scheduler)
  - 一次查询 → 订阅升级

W11-W12: 多源接入
  - 搜索 API 适配器(Tavily / 七牛云百度 / Exa)
  - arXiv API 适配
  - 微信公众号第三方通道
  - 微博热搜 API

W13-W14: 研报与简报
  - 研报生成 pipeline(大纲 → 填充 → 校验)
  - 每日 AI 论文推送模板
  - 每周新模型盘点模板

W15-W16: Web Console
  - Next.js 前端(订阅管理 / 检索 / 热榜 / 收件箱)
  - 实时通知(WS / SSE)
  - 基础埋点(用户行为 / 错误监控)
```

### 7.4 GA 阶段(W17-W24)详细任务

```
W17-W18: 高级功能
  - 关键词监控 + 阈值触发
  - 团队协作(共享订阅 / 共享研报)
  - API 开放 + 文档 + SDK(Python / Rust)

W19-W20: 性能与稳定性
  - 压测(wrk / k6),P99 < 300ms 检索目标
  - 多区域容灾(至少 2 个可用区)
  - LLM 调用熔断 + 降级

W21-W22: 安全与合规
  - 渗透测试
  - 隐私合规评审
  - 数据保留策略(可配置)

W23-W24: 商业化与上线
  - 计费系统(Stripe / 微信支付)
  - 试用 + 付费分层
  - 产品文档 + 帮助中心
  - 公测发布
```

### 7.5 团队配置建议

| 角色 | MVP | Beta | GA |
|---|---|---|---|
| Rust 后端 | 1 | 1 | 2 |
| Python(爬虫+AI) | 1 | 2 | 2 |
| 前端(Next.js) | 0(CLI 起步) | 1 | 1-2 |
| 全栈 / DevOps | 0.5(兼) | 1 | 1 |
| 产品 | 1(兼) | 1 | 1 |
| **合计** | **2-3** | **5-6** | **7-8** |

---

## 8. 难点 & 风险评估

### 8.1 技术难点

| 难点 | 等级 | 缓解 |
|---|---|---|
| 复杂社媒反爬(微博/抖音/小红书) | 🔴 高 | MVP 不直接爬,优先搜索 API;长期走官方开放平台 |
| LLM 成本失控 | 🟡 中 | 多模型路由 + 缓存 + 摘要长度控制 + 用量配额 |
| Embedding 模型漂移(升级版本) | 🟡 中 | 版本化 Embedding,文档存旧版本向量 ID |
| 摘要质量不稳定 | 🟡 中 | 结构化输出 + 评测集 + prompt 版本管理 |
| NL 解析失败(用户表述模糊) | 🟡 中 | 解析后回显用户确认 + 提供修正入口 |
| 调度器时钟漂移 | 🟢 低 | 用 tokio-cron + 数据库兜底状态 |
| 大文档(> 100k 字)摘要 | 🟢 低 | Map-Reduce:分段摘要 → 整体摘要 |

### 8.2 业务风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 第三方搜索 API 涨价/倒闭 | 🟡 中 | 多供应商路由,自研兜底 |
| 主流平台封禁 IP | 🟡 中 | 代理池 + 备用 API + 法律风险评估 |
| 数据版权纠纷 | 🔴 高 | 仅保留摘要 + 原文链接,引用注明出处 |
| 用户量增长慢 | 🟡 中 | MVP 阶段先服务 100 个种子用户,验证需求 |
| LLM 服务商政策变化 | 🟢 低 | 模型路由层抽象,2 周可完成切换 |

### 8.3 不可行项(明确放弃)

为避免 scope creep,以下功能 **不在 MVP 范围内**:

- ❌ 视频内容理解(抖音/小红书视频转录与分析)— 技术门槛高、版权风险大
- ❌ 实时评论监控 — 数据噪声过大,商业价值不清晰
- ❌ 自研基础大模型 — 不在项目定位
- ❌ 移动端原生 App — 用 PWA 替代,先验证 Web
- ❌ 私有数据源接入 — 需要企业 SSO,GA 之后再考虑

---

## 9. 成本估算

### 9.1 MVP 阶段(月度)

| 项目 | 金额 |
|---|---|
| 云资源(2C4G × 2 + 1C2G × 1) | ¥800 |
| PostgreSQL + Redis + Qdrant(托管) | ¥500 |
| LLM 调用(摘要 + Embedding,假设 500 用户 × 30 订阅 × 10 篇/日) | ¥1500-3000 |
| 第三方搜索 API(Tavily / 七牛云百度) | ¥500 |
| 域名 + SSL + 邮件 | ¥100 |
| **小计** | **¥3500-4900 / 月** |

### 9.2 GA 阶段(月度,假设 1 万付费用户)

| 项目 | 金额 |
|---|---|
| 云资源(20C40G × 4 + GPU × 1) | ¥15000 |
| PostgreSQL + Redis + Qdrant(集群) | ¥8000 |
| LLM 调用 | ¥30000-60000 |
| 第三方搜索 API + 反爬代理 | ¥8000 |
| 监控 + 日志 + 备份 | ¥3000 |
| **小计** | **¥6-10 万 / 月** |

### 9.3 人力成本(北京/上海)

- 全职工程师:¥25-50k/月 × 7-8 人 = ¥17.5-40 万/月
- MVP 阶段建议 2-3 人精干小团队,降本试错。

---

## 10. 降级方案(兜底策略)

当外部依赖故障时,必须能优雅降级:

| 主路径 | 降级路径 |
|---|---|
| GPT-4o 摘要 | → Claude Sonnet → Gemini Flash → DeepSeek V3 → 本地 Qwen-7B → 仅返回正文前 500 字 |
| Tavily 检索 | → Exa → Jina → Serper → 七牛云百度 → 自有缓存库 → 503 + 友好提示 |
| 微博热搜 API | → 微博开放平台 → 第三方聚合 → 人工标注热词 → 仅返回本地热榜 |
| 邮件推送 | → 站内消息 → 微信/钉钉 Webhook → 用户登录后查看 |
| WebSocket 推送 | → SSE → 轮询(10s 间隔) |
| PostgreSQL 故障 | → 只读模式(返回最近 24h 缓存) → 完全只读模式 |

**熔断阈值**(建议):
- LLM API 5xx > 10% 持续 1 分钟 → 熔断 30s
- 搜索 API 超时 > 5% → 切换备用供应商
- 数据库连接池满 → 启用只读副本

---

## 11. 验证指标

MVP 阶段需明确达成的核心指标:

| 指标 | 目标 | 验证方式 |
|---|---|---|
| 端到端流程跑通 | 用户创建订阅 → 24h 内收到推送 | 自动化 e2e 测试 |
| 检索 P99 延迟 | < 300ms | 压测 + 生产监控 |
| 摘要相关性(人工评估) | ≥ 80% 用户认为"有用" | 100 用户盲测 |
| 系统可用性 | ≥ 99.5%(MVP)/ 99.9%(GA) | 监控告警 |
| LLM 成本 | < ¥0.05 / 篇摘要 | 用量计费 |
| 采集覆盖率 | 主流 20+ 站点每日更新 | 监控采集成功率 |

---

## 12. 后续路线图(GA 之后)

| 季度 | 主题 |
|---|---|
| Q3+1 | 移动端 PWA / 浏览器插件 / 微信小程序 |
| Q3+2 | 团队协作 / 共享知识库 / 权限管理 |
| Q3+3 | 私有化部署(企业版)/ 私有数据源接入 |
| Q4+1 | 多模态(图文理解、视频关键帧摘要) |
| Q4+2 | 主动推送(基于用户行为预测兴趣) |
| Q4+3 | Marketplace(用户分享订阅模板、研报模板) |

---

## 附录

- 附录 A:关键技术决策(ADR)— 见 `docs/adr/0001-tech-stack.md`
- 附录 B:PostgreSQL Schema 初稿 — 见 `docs/schema/schema-v1.sql`
- 附录 C:Rust 项目结构 — 见 `docs/architecture/rust-layout.md`
- 附录 D:合规风险评估表 — 见 `docs/compliance/risk-matrix.md`

---

**评审签字栏**

| 角色 | 姓名 | 日期 | 意见 |
|---|---|---|---|
| 产品负责人 | | | |
| 技术负责人 | | | |
| 合规/法务 | | | |
| 业务负责人 | | | |