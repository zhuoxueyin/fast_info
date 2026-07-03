# ADR-0001: fastInfo 技术栈选型

> 状态:草案  ·  日期:2026-06-28  ·  决策者:技术负责人

## 背景

构建 fastInfo 需要在多个维度做技术选型:Rust Web 框架、爬虫语言、AI 模型、存储、调度等。
本文档记录关键决策及理由,避免反复讨论。

---

## 决策 1:Rust Web 框架 — Axum 0.8

### 决策
使用 **Axum 0.8** 作为 API 网关与核心调度服务的 Rust Web 框架。

### 评估

| 框架 | 性能 | 生态 | 易用性 | 维护性 | 评分 |
|---|---|---|---|---|---|
| Axum 0.8 | 高(35 万 RPS Hello) | Tokio/Tower/Hyper 完整 | 类型安全、提取器优雅 | Tokio 团队主维护 | ⭐⭐⭐⭐⭐ |
| Actix-Web | 极高(40 万 RPS Hello) | 自成体系,与 Tower 不兼容 | 学习曲线陡 | 社区活跃 | ⭐⭐⭐⭐ |
| Rocket | 中 | 自有生态 | 易上手但迭代慢 | 迭代慢 | ⭐⭐⭐ |
| Hyperlane | 高 | 极简、案例少 | 中文文档友好 | 1.x 未到,生产风险 | ⭐⭐ |

### 理由
1. **生态完整**:tower-http 提供 trace/cors/compress/timeout/limit 全部现成中间件。
2. **类型安全**:Extractor 设计避免运行期错误,与 sqlx 编译期 SQL 校验天然契合。
3. **Tokio 集成**:同一 Runtime 可统一调度 HTTP/爬虫/定时任务。
4. **生产案例**:Cloudflare Workers、Deno Deploy、AWS Lambda Custom Runtime 均有使用。
5. **Actix 优势(性能 +10-20%)在业务场景下被 DB/网络 IO 抹平,本项目不是性能极限场景**。

### 后果
- 团队需熟悉 Tokio 异步模型(学习成本 1-2 周)。
- 0.x 版本偶有破坏性变更,需关注 release notes。

---

## 决策 2:爬虫语言 — Python 为主,Rust 辅助

### 决策
- **复杂 JS 渲染**场景(微博/抖音/小红书/X):Python `playwright` + `scrapy-playwright`。
- **RSS / 普通 HTML**:Rust `reqwest` + `scraper`(也可 Python)。
- **统一抽象**:Python 定义 `SourceAdapter` Protocol,Rust 端通过 FFI/PyO3 调用。

### 理由
1. **生态成熟**:Python 在爬虫领域沉淀深(scrapy、playwright、undetected-chromedriver)。
2. **迭代速度**:反爬对抗变更频繁,Python 动态语言改起来快。
3. **Rust 优势**:内存安全、高并发——但本项目瓶颈不在爬虫端(目标站点已限速),而在调度与处理。
4. **工程取舍**:MVP 阶段优先 Python 快速验证,Rust 爬虫留作未来优化项。

### 后果
- 维护两套语言栈,需明确边界:Rust 只做 API/调度,Python 只做采集/AI。
- Python 性能瓶颈处(CPU 密集)可用 Rust 通过 PyO3 重写,接口兼容。

---

## 决策 3:AI 模型 — 多模型路由,默认降本

### 决策
采用 **多模型路由策略**,按场景匹配模型:

| 场景 | 模型 | 理由 |
|---|---|---|
| 短摘要(< 500 字) | DeepSeek V3 / Qwen2.5-72B | 中文强、成本极低 |
| 长摘要 + 简报 | Claude Sonnet 4.5 | 长文能力稳定 |
| 专业解读 / 研报 | Claude Sonnet/Opus 4.5 / GPT-5.1 | 用户主动触发,质量优先 |
| Embedding | BGE-M3 / BGE-large-zh-v1.5 | 中文检索 SOTA,可自部署 |
| 实体识别 / 分类 | GLM-4-Flash / Qwen2.5-7B-Instruct | 轻量任务,本地可跑 |

### 理由
1. **成本 vs 质量平衡**:全用 Opus 4.5 月成本 ¥30 万+,全用 DeepSeek 月成本 ¥3000 但质量降级。
2. **降级策略**:主供应商故障时,自动切换备用(熔断 + 多 key 轮询)。
3. **国内合规**:涉及用户数据/中文内容优先国内模型(GLM、Qwen、DeepSeek)。
4. **可控 effort**:Claude Opus 4.5 的"努力参数"支持低/中/高三档,按需调用。

### 后果
- 需维护多套 API Key + 计费监控。
- 摘要质量评测需建立内部 benchmark,持续校准。

---

## 决策 4:向量数据库 — Qdrant

### 决策
使用 **Qdrant** 作为主向量数据库。

### 评估

| 数据库 | 性能 | 部署复杂度 | Rust 客户端 | 评分 |
|---|---|---|---|---|
| Qdrant | 高(Rust 实现) | 单二进制,部署简单 | 官方维护 | ⭐⭐⭐⭐⭐ |
| Milvus | 高(分布式) | 需 etcd + MinIO + Pulsar | 社区维护 | ⭐⭐⭐⭐ |
| pgvector | 中 | 复用 PostgreSQL | sqlx 支持 | ⭐⭐⭐ |
| Weaviate | 高 | Go 模块较多 | 社区维护 | ⭐⭐⭐ |

### 理由
1. **Rust 原生**:与项目主语言同构,API 性能最佳。
2. **部署简单**:单二进制文件 + 配置文件,Docker Compose 一键起。
3. **混合检索**:支持 dense + sparse 混合(对中文更友好)。
4. **活跃维护**:GitHub 20k+ stars,周更节奏。

### 后果
- 集群方案稍弱(社区版需自己分片),MVP 阶段单机够用,GA 评估分布式。

---

## 决策 5:调度器 — tokio-cron-scheduler + Redis Streams

### 决策
- **短期调度**(< 1 分钟):`tokio-cron-scheduler`(Rust 内嵌)。
- **任务队列**(跨服务):Redis Streams。
- **长期归档任务**(可选):PostgreSQL `pg_cron`。

### 理由
1. **简单优先**:Redis Stream 已经是事实标准,生态成熟。
2. **避免外部依赖**:不引入 Kafka/Pulsar(运维成本高),MVP 阶段 Redis Streams 足够。
3. **可演进**:Redis Stream 不够时,平滑迁移到 Kafka(接口已封装)。

---

## 决策 6:合规采集 — 优先搜索 API,谨慎自研

### 决策

| 数据源 | 方式 |
|---|---|
| 公开 RSS / Sitemap | 直接爬,严守 robots.txt |
| 学术(arXiv / HF / PwC) | 官方 API |
| 微信公众号 | 第三方合规通道(SCRM) |
| 微博热搜 / 抖音热搜 | 官方开放平台 + ALAPI 等聚合 |
| 微博 / 抖音 / 小红书 / X 普通内容 | **优先用 Tavily / Exa / Jina 等搜索 API 间接获取** |
| 直接爬社媒 | **MVP 不做**,Beta 评估 |

### 理由
1. **法律风险**:微博/抖音/小红书均有平台协议禁止未经授权抓取,违反可能触发账号封禁 + 法律诉讼。
2. **反爬对抗成本**:签名算法 + 设备指纹 + 行为检测,自研投入产出比低。
3. **搜索 API 已成熟**:Tavily SimpleQA 准确率 93.3%,P50 延迟 180ms,完全够用。
4. **国内合规**:百度搜索 API(七牛云封装)对中文内容收录更深,合规风险低。

### 后果
- 长期内容深度(单平台完整时间线)做不到,只能拿到搜索 API 返回的 Top-N。
- 单篇内容仍可通过 Jina Reader(`r.jina.ai/<url>`)拉到正文 Markdown,作为摘要输入。

---

## 决策 7:鉴权 — JWT(用户) + API Key(开发者)

### 决策
- **终端用户**:JWT(短期 access + 长期 refresh)。
- **开发者 API 调用**:API Key + HMAC 签名(可选)。
- **管理后台**:OIDC + RBAC(后期接入)。

### 理由
1. **Web Console + API 共用一套身份**,JWT 天然支持。
2. **API Key 适合脚本/CLI 场景**,无需每次登录。
3. **MVP 阶段不引入 SSO**,避免早期过度工程。

---

## 决策 8:可观测性 — OpenTelemetry + Grafana

### 决策
- **Trace**:OpenTelemetry → Tempo(或 Jaeger)。
- **Metric**:Prometheus + Grafana。
- **Log**:tracing(结构化 JSON) → Loki(或 ES)。

### 理由
1. **标准化**:OpenTelemetry 跨语言,Python/Rust 统一接入。
2. **轻量**:tracing-subscriber 即可,无需复杂 APM。
3. **自托管友好**:Grafana 全家桶单 Docker Compose 起。

---

## 不决策项(明确推迟)

- ❌ Kubernetes:GA 之后再考虑,先用 Docker Compose / 单机部署。
- ❌ 微服务拆分:MVP 单体,服务边界在代码层明确但不物理拆分。
- ❌ GraphQL:REST 足够,GraphQL 学习成本不划算。
- ❌ 实时音视频:不在项目范围。
- ❌ 自研 Embedding 模型:用 BGE 现成。

---

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| 0.1 | 2026-06-28 | 初稿 | Mavis |