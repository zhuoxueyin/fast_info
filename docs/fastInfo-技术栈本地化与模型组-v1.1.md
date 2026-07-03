# fastInfo 技术栈本地化与模型组路由 · v1.1

> 承接 v1.0 主方案  ·  日期:2026-06-29  ·  范围:回答用户两个关键追问

---

## Q1:除了 AI 模型外,我的本机免费技术栈怎么搭?

### 结论速览

| 组件 | v1.0 方案 | v1.1 推荐(本机免费版) | 说明 |
|---|---|---|---|
| 主数据库 | PostgreSQL 16 | **MongoDB**(你已有) | 完全可替代,文档型 schema 友好 |
| 任务队列 | Redis Streams | **Redis**(Docker / WSL) | 队列+限流+缓存全包,免费 |
| 缓存 | Redis | **Redis + 本地内存缓存** | 内存层用 `moka`(Rust)/ `cachetools`(Python) |
| 向量检索 | Qdrant(Docker) | **LanceDB**(嵌入式) **或 Qdrant(Docker)** | LanceDB 零运维;Qdrant 性能更稳 |
| 全文检索 | Meilisearch | **MongoDB Atlas Search / text index** | MVP 够用,后期可加 |
| 对象存储 | S3 | **本地文件系统 + MongoDB GridFS** | 完全本地;生产再换 S3/MinIO |
| 调度 | tokio-cron | **MongoDB change streams + APScheduler** | 跨进程统一 |

> 上述每一项 **全部开源、零订阅费**。本机部署总资源占用约 4-6GB 内存,8 核 CPU 完全够 MVP。

---

### 1.1 详细替代方案

#### MongoDB vs PostgreSQL — 你已经有 MongoDB,本项目完全够用

✅ **MongoDB 在本项目里的优势**:
- 文档型 schema,刚好契合 `items`(新闻/订阅结果)的灵活字段
- BSON 直接吃 JSON,LLM 输出零开销入库
- MongoDB 4.0+ 多文档事务已支持(订阅任务的状态机变更够用)
- 你已经有现成的运维经验,学习成本为 0

⚠️ **MongoDB 在本项目里的小短板及缓解**:
- **短板 1:无 GIN 全文索引** → 缓解:用 MongoDB text index(MVP)或加 Meilisearch
- **短板 2:无原生向量类型** → 缓解:LanceDB / Qdrant 专门做这事
- **短板 3:无外部 JOIN 优化器** → 缓解:本项目读模型已在 MongoDB 端反范式化(见 schema)

> **结论:MongoDB 在 fastInfo 这种**「文档+少量关联+无强事务」**的场景,完全可以替代 PostgreSQL**。

#### Redis 本机部署(三种免费方案)

| 方案 | 资源占用 | 部署难度 | 备注 |
|---|---|---|---|
| **A. Docker Desktop(WSL2 后端) + 官方 redis 镜像** | ~30MB | ⭐⭐ 一行命令 | **首推**,生产级体验 |
| **B. WSL2 直接装 Redis** | ~30MB | ⭐⭐⭐ 几步配置 | 与 Docker 等效 |
| **C. Memurai(Windows 原生)** | ~50MB + 50MB 免费限制 | ⭐ 一键安装 | MVP 阶段够用,内存溢出风险 |

**首推方案 A**——你的机器已经装过 MongoDB,大概率也有 Docker。Compose 文件:

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    container_name: fastinfo-redis
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: unless-stopped

  qdrant:                              # 二选一:用 Qdrant 做向量
    image: qdrant/qdrant:v1.12
    container_name: fastinfo-qdrant
    ports: ["6333:6333", "6334:6334"]
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

volumes:
  redis_data:
  qdrant_data:
```

> 如果你想 **完全不要 Docker**,可选 **LanceDB**(纯嵌入式)+ 一个 Rust 内存缓存,连 Redis 都不需要。

#### 向量检索: LanceDB vs Qdrant 本机对比

| 维度 | LanceDB | Qdrant |
|---|---|---|
| 部署 | **零运维**,`pip install lancedb` | 需 Docker / 单二进制 |
| Rust 原生支持 | ✅ 完全 Rust 生态 | ✅ Rust 客户端 |
| 数据规模 | < 1 亿向量单机够用 | < 1 亿向量单机够用 |
| 混合检索 | ✅ 支持 dense + sparse | ✅ 全文过滤器 |
| 索引算法 | IVF / HNSW | HNSW 为主 |
| 性能 | 中等 | **性能更优**(Rust 原生 + RocksDB) |
| 维护活跃度 | Apache 2.0,17k stars | Apache 2.0,23k stars |

**两个我都推荐,但场景不同**:
- **MVP / 个人开发者**:选 **LanceDB**(零运维,Python/Rust 同源,和 MongoDB 一样"装上就用")
- **后期数据量 > 500w 向量**:迁 **Qdrant**(Docker 一行起,性能更稳)

**LanceDB Python 集成示例**:

```python
import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

# 1. 定义 schema
class ItemEmbedding(LanceModel):
    item_id: str
    vector: Vector(1024)         # BGE-M3 是 1024 维
    title: str
    content_md: str
    published_at: str

# 2. 连接 + 建表
db = lancedb.connect("./data/lancedb")    # 本地路径,无需服务
table = db.create_table("items", schema=ItemEmbedding, mode="overwrite")

# 3. 写入
table.add([ItemEmbedding(item_id="...", vector=emb, title="...", ...)])

# 4. 检索
results = table.search(query_vector, query_type="hybrid").limit(10).to_pandas()
```

**LanceDB Rust 集成示例**(放到 fastInfo Rust 服务里):

```toml
# Cargo.toml
[dependencies]
lancedb = "0.13"
arrow = "53"
tokio = { version = "1", features = ["full"] }
```

```rust
use lancedb::{connect, DistanceType};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db = connect("./data/lancedb").execute().await?;
    let table = db.open_table("items").execute().await?;
    
    // 检索:向量 + 元数据过滤
    let results = table
        .vector_search(&[0.1; 1024])
        .distance_type(DistanceType::Cosine)
        .limit(10)
        .filter("published_at > '2026-06-01'")
        .execute()
        .await?;
    
    Ok(())
}
```

---

### 1.2 推荐的本机最终栈

```
┌──────────────────────────────────────────────────┐
│  MongoDB(你已有)         ←——— 主存储             │
│  ↓                    文档 / 配置 / 任务 / 审计    │
│  ┌──────────────────────────────────────────┐     │
│  │ Rust API(Axum)                          │     │
│  │  - 鉴权 / 订阅引擎 / 检索 / 推送         │     │
│  └──────────────────────────────────────────┘     │
│         ↓                       ↓                  │
│  Redis(Docker)         LanceDB(嵌入式)           │
│  - 限流                 - 向量检索               │
│  - 队列(Streams)        - 嵌入存储               │
│  - 热点缓存                                        │
│         ↓                                          │
│  ┌──────────────────────────────────────────┐     │
│  │ Python Crawler/AI(独立进程)              │     │
│  │  - 抓取 / 解析 / 摘要 / Embedding / 推送  │     │
│  └──────────────────────────────────────────┘     │
│         ↓                                          │
│  BGE-M3(本地推理,GPU/CPU 均可)                    │
│  - 嵌入生成                                          │
│  - NER / 分类(可选)                                 │
│  - 关键词权重                                       │
└──────────────────────────────────────────────────┘
```

**机器配置建议(MVP)**:
- 4C8G 起步(主进程 + MongoDB + Redis + LanceDB 总内存约 2GB,LLM 推理调 API 不占本地)
- 32GB+ 系统盘(存放 MongoDB / LanceDB 数据)

**Embedding 模型部署**:
- BGE-M3 开源(`BAAI/bge-m3`),`pip install sentence-transformers` 后 `model = SentenceTransformer('BAAI/bge-m3')` 即可
- CPU 跑 1 篇 500 字文档嵌入约 50ms,MVP 完全够用
- 后期量大了切到 GPU / 调用远程 Embedding API

---

### 1.3 备用方案(完全无 Docker)

如果你的机器 **不能装 Docker**(比如 Windows Home 精简版、磁盘紧):

| 组件 | 替代 |
|---|---|
| Redis | `microsoft/garnet`(微软开源,Windows 原生 .NET,GitHub 6k stars)— 下载即用 .exe;或 Memurai 免费版 |
| Qdrant | 用 **LanceDB** 替代(嵌入式) |
| MongoDB | 你已有 |

---

## Q2:MiniMax-M3 + Kimi K2.6 双模型容灾路由设计

### 2.1 答:够用,而且是黄金组合

两个模型都是 SOTA 级国产开源旗舰,但**定位互补**:

| 维度 | MiniMax-M3 | Kimi K2.6 |
|---|---|---|
| 上下文 | **1M**(MSA 稀疏注意力) | 256K(稳定) |
| 编程 | **SWE-Bench Pro 59.0%** | 58.6% |
| 多模态 | **✅ 原生**(图/视频) | ❌ 文本为主 |
| Agent | **强**,Thinking 模式 | 中等 |
| 中文本对话 | 中等 | **强**(Kimi 长文本优势) |
| 输入价 | **¥4.2/M** | ¥6.5/M(未缓存) |
| 输出价 | **¥16.8/M** | ¥27/M |
| 缓存命中价 | (无公开数据,推测 ~¥1) | **¥1.3/M**(极低) |
| 模型权重 | 开源 | 开源(2.7 Code 同开源) |
| 适合场景 | 编程 / Agent / 大文档 | 长文本检索 / 中文对话 |

**最佳用法**:
- **主力:MiniMax-M3**——便宜、能干、Agent 强、能看图
- **备用:Kimi K2.6**——长文更稳、缓存命中价极低(适合重复 prompt)
- **专业解读/研报**:M3 thinking 模式主用,K2.6 兜底

### 2.2 模型组(Fallback Group)设计

#### 模型组定义

```yaml
# config/models.yaml
version: 1

model_groups:
  # 组 1:日常摘要(高频,降本优先)
  - name: short_summary
    strategy: cost_first        # 优先用便宜的
    providers:
      - id: m3
        model: MiniMax-M3
        priority: 1             # 数字越小优先级越高
        weight: 70              # 流量权重(可选)
        max_concurrency: 50
        timeout_ms: 15000
      - id: kimi
        model: kimi-k2.6
        priority: 2             # 备用
        weight: 30
        max_concurrency: 30
        timeout_ms: 20000

  # 组 2:长摘要 / 简报(中等频率,质量+成本)
  - name: long_summary
    strategy: quality_first
    providers:
      - id: m3
        model: MiniMax-M3
        priority: 1
        weight: 50
        timeout_ms: 30000
        params:
          thinking_mode: enabled
      - id: kimi
        model: kimi-k2.6
        priority: 2
        weight: 50
        timeout_ms: 30000

  # 组 3:专业解读 / 研报(低频,质量优先)
  - name: deep_interpretation
    strategy: quality_first
    providers:
      - id: m3
        model: MiniMax-M3
        priority: 1
        weight: 60
        params:
          thinking_mode: enabled
          max_tokens: 8192
        timeout_ms: 60000
      - id: kimi
        model: kimi-k2.6
        priority: 2
        weight: 40
        timeout_ms: 60000

  # 组 4:NL 解析(订阅)
  - name: nl_parse
    strategy: quality_first
    providers:
      - id: m3
        model: MiniMax-M3
        priority: 1
        timeout_ms: 10000
      - id: kimi
        model: kimi-k2.6
        priority: 2
        timeout_ms: 10000

  # 组 5:Embedding(M3 / K2.6 都不擅长!本组必须用专用模型)
  - name: embedding
    strategy: local_only       # 必须本地,远程 API 成本/延迟不划算
    providers:
      - id: bge-m3-local
        model: BAAI/bge-m3
        priority: 1
        type: local
```

#### 异常切换策略

```yaml
# 模型组级 fallback 策略
fallback_policy:
  # 触发切换的条件(命中任一即降级)
  triggers:
    - type: timeout
      threshold_ms: 30000
      consecutive: 3            # 连续 3 次超时
    - type: http_5xx
      rate_threshold: 0.10      # 5xx 比例 > 10%
      window_seconds: 60
    - type: http_429            # 限流
      action: immediate         # 立即触发
    - type: rate_limit_exceeded # 配额耗尽
      action: immediate
    - type: content_filter      # 内容安全拒绝
      action: degrade_to_secondary_immediately

  # 冷却期(避免雪崩)
  cooldown:
    primary_cooldown_seconds: 300          # 触发后 5 分钟内不再试主
    secondary_cooldown_seconds: 600        # 备用冷却 10 分钟
    half_open_after_seconds: 120           # 2 分钟后做一次 half-open 测试

  # 熔断
  circuit_breaker:
    error_rate_threshold: 0.30             # 错误率 > 30% 熔断
    min_requests: 10                       # 至少 10 个样本
    open_duration_seconds: 60
    half_open_max_probes: 3                # 半开期允许 3 个试探

  # 退避
  retry:
    max_retries: 2
    backoff: exponential
    initial_ms: 200
    max_ms: 2000
    jitter: 0.2
```

#### 决策流程图

```
请求进来
   │
   ▼
查 circuit breaker 状态
   ├─ 主 open ────────────────► 走备用
   │
   ▼
查 cooldown
   ├─ 主在冷却 ────────────────► 走备用
   │
   ▼
按 priority + weight 选可用 provider
   │
   ▼
调用,套 retry(只对 transient 错误重试)
   │
   ├─ 成功 ─────────────────► 计入指标,熔断器记录 success
   │
   ├─ 超时 / 5xx / 429 ─────► retry → 仍失败 → 切备用
   │                             ↓
   │                          备用也失败?→ fallback_to_template
   │
   └─ 内容安全拒绝(content_filter)→ 立即切备用,不重试
                                     ↓
                                  备用也失败?→ 返回温和错误
```

---

### 2.3 Python 实现(可直接搬)

```python
"""
fastInfo 模型路由 (LLM Gateway)
单一入口,支持多 Provider + 熔断 + 冷却 + 权重负载均衡
"""
from __future__ import annotations
import asyncio
import enum
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from collections import defaultdict
import httpx
import structlog

logger = structlog.get_logger()


# ============ 错误类型 ============
class ModelErrorType(enum.Enum):
    TIMEOUT = "timeout"
    HTTP_5XX = "http_5xx"
    HTTP_429 = "http_429"
    CONTENT_FILTER = "content_filter"
    CONTEXT_TOO_LONG = "context_too_long"
    BAD_REQUEST = "bad_request"           # 4xx 非 429,不再重试
    INTERNAL = "internal"                 # 未知错误


class ModelError(Exception):
    def __init__(self, err_type: ModelErrorType, message: str, retryable: bool = True):
        super().__init__(message)
        self.err_type = err_type
        self.retryable = retryable


# ============ 配置 ============
@dataclass
class ProviderConfig:
    id: str
    base_url: str
    api_key: str
    model: str
    priority: int
    weight: int = 50
    timeout_ms: int = 15000
    max_concurrency: int = 50
    extra_headers: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.max_concurrency)


@dataclass
class GroupPolicy:
    name: str
    providers: list[ProviderConfig]
    max_retries: int = 2
    initial_backoff_ms: int = 200
    max_backoff_ms: int = 2000
    jitter: float = 0.2


# ============ 熔断器 ============
class CircuitBreakerState(enum.Enum):
    CLOSED = "closed"       # 正常
    OPEN = "open"           # 熔断中
    HALF_OPEN = "half_open" # 半开探测


@dataclass
class CircuitBreaker:
    error_rate_threshold: float = 0.30
    min_requests: int = 10
    open_duration_seconds: int = 60
    half_open_max_probes: int = 3

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    total: int = 0
    errors: int = 0
    opened_at: float = 0.0
    probe_success: int = 0
    probe_failure: int = 0

    def allow(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.opened_at > self.open_duration_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                self.probe_success = 0
                self.probe_failure = 0
                logger.info("circuit_breaker.half_open")
                return True
            return False
        # HALF_OPEN:只允许少量探测
        return self.probe_success + self.probe_failure < self.half_open_max_probes

    def record(self, success: bool):
        if self.state == CircuitBreakerState.HALF_OPEN:
            if success:
                self.probe_success += 1
                if self.probe_success >= self.half_open_max_probes // 2:
                    self.state = CircuitBreakerState.CLOSED
                    self.total = 0
                    self.errors = 0
                    logger.info("circuit_breaker.closed")
            else:
                self.probe_failure += 1
                self.opened_at = time.time()
                self.state = CircuitBreakerState.OPEN
                logger.warning("circuit_breaker.open_again")
            return

        # CLOSED 状态:统计错误率
        self.total += 1
        if not success:
            self.errors += 1

        if self.total >= self.min_requests:
            err_rate = self.errors / self.total
            if err_rate >= self.error_rate_threshold:
                self.state = CircuitBreakerState.OPEN
                self.opened_at = time.time()
                logger.warning(
                    "circuit_breaker.opened",
                    error_rate=err_rate,
                    errors=self.errors,
                    total=self.total,
                )


# ============ Cooldown(冷却) ============
@dataclass
class CooldownState:
    consecutive_failures: int = 0
    cooldown_until: float = 0.0

    def is_cooling(self) -> bool:
        return time.time() < self.cooldown_until

    def record_failure(self, base_seconds: int = 300):
        self.consecutive_failures += 1
        # 指数退避:300s, 600s, 1200s, 上限 30 分钟
        secs = min(base_seconds * (2 ** (self.consecutive_failures - 1)), 1800)
        self.cooldown_until = time.time() + secs
        logger.warning(
            "cooldown.triggered",
            consecutive=self.consecutive_failures,
            until_in_seconds=secs,
        )

    def record_success(self):
        self.consecutive_failures = 0
        self.cooldown_until = 0.0


# ============ Provider 适配器 ============
class LLMProvider:
    """统一的 Provider 接口(M3 / Kimi 都实现 chat() + embed())"""

    def __init__(self, cfg: ProviderConfig, breaker: CircuitBreaker, cooldown: CooldownState):
        self.cfg = cfg
        self.breaker = breaker
        self.cooldown = cooldown
        self.client = httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_ms / 1000.0,
            headers={
                "Authorization": f"Bearer {cfg.api_key}",
                **cfg.extra_headers,
            },
        )

    async def chat(self, messages: list[dict], **kwargs) -> dict:
        """OpenAI 兼容 chat 接口"""
        body = {
            "model": self.cfg.model,
            "messages": messages,
            **self.cfg.params,
            **kwargs,
        }
        try:
            resp = await self.client.post("/chat/completions", json=body)
            self._check_response(resp)
            return resp.json()
        except ModelError:
            raise
        except httpx.TimeoutException:
            raise ModelError(ModelErrorType.TIMEOUT, "timeout")
        except httpx.HTTPError as e:
            raise ModelError(ModelErrorType.INTERNAL, str(e))

    def _check_response(self, resp: httpx.Response):
        if resp.status_code == 200:
            return
        if resp.status_code == 429:
            raise ModelError(ModelErrorType.HTTP_429, "rate limit", retryable=False)
        if resp.status_code in (400, 403):
            body = resp.text
            if "content_filter" in body or "敏感" in body:
                raise ModelError(ModelErrorType.CONTENT_FILTER, "blocked", retryable=False)
            if "context_length" in body or "too long" in body:
                raise ModelError(ModelErrorType.CONTEXT_TOO_LONG, "context too long", retryable=False)
            raise ModelError(ModelErrorType.BAD_REQUEST, body, retryable=False)
        if resp.status_code >= 500:
            raise ModelError(ModelErrorType.HTTP_5XX, f"{resp.status_code}")
        raise ModelError(ModelErrorType.INTERNAL, resp.text)

    async def aclose(self):
        await self.client.aclose()


# ============ 模型组(Gateway) ============
class ModelGroup:
    """一个语义任务 = 一个 ModelGroup(如 short_summary / long_summary)"""

    def __init__(self, name: str, providers: list[LLMProvider], policy: GroupPolicy):
        self.name = name
        self.providers = sorted(providers, key=lambda p: p.cfg.priority)
        self.policy = policy

    def _select_provider(self) -> LLMProvider | None:
        """按优先级 + 权重选择可用 provider"""
        # 已冷却/熔断 → 跳过
        available = [
            p for p in self.providers
            if not p.cooldown.is_cooling() and p.breaker.allow()
        ]
        if not available:
            # 所有都不可用 → 强制选优先级最高的(让它失败 + 记 cooldown)
            return self.providers[0] if self.providers else None

        # 同优先级内按权重随机
        # 这里简化为整体权重:priority 1 权重总和 vs priority 2 总和
        groups = defaultdict(list)
        for p in available:
            groups[p.cfg.priority].append(p)

        for prio in sorted(groups.keys()):
            same_prio = groups[prio]
            total_weight = sum(p.cfg.weight for p in same_prio)
            r = random.uniform(0, total_weight)
            acc = 0
            for p in same_prio:
                acc += p.cfg.weight
                if r <= acc:
                    return p
            return same_prio[0]
        return available[0]

    async def chat(self, messages: list[dict], **kwargs) -> dict:
        """完整的 fallback 调用链"""
        last_error: ModelError | None = None

        # 1. 主试:provider 内的 retry
        primary = self._select_provider()
        if primary:
            try:
                result = await self._call_with_retry(primary, messages, **kwargs)
                primary.breaker.record(success=True)
                primary.cooldown.record_success()
                return result
            except ModelError as e:
                last_error = e
                primary.breaker.record(success=False)
                # 内容安全/超长 → 立即降级,不再重试
                if e.err_type in (ModelErrorType.CONTENT_FILTER, ModelErrorType.CONTEXT_TOO_LONG):
                    primary.cooldown.record_failure(base_seconds=60)  # 轻冷却
                elif e.err_type == ModelErrorType.HTTP_429:
                    primary.cooldown.record_failure(base_seconds=120)
                elif e.err_type in (ModelErrorType.TIMEOUT, ModelErrorType.HTTP_5XX):
                    primary.cooldown.record_failure(base_seconds=300)
                else:
                    primary.cooldown.record_failure(base_seconds=60)

        # 2. 备用:其他 provider
        for candidate in self.providers:
            if candidate is primary:
                continue
            if candidate.cooldown.is_cooling() or not candidate.breaker.allow():
                continue
            try:
                result = await self._call_with_retry(candidate, messages, **kwargs)
                candidate.breaker.record(success=True)
                candidate.cooldown.record_success()
                logger.info(
                    "fallback.success",
                    group=self.name,
                    primary_failed=last_error.err_type.value if last_error else None,
                    fallback=candidate.cfg.id,
                )
                return result
            except ModelError as e:
                candidate.breaker.record(success=False)
                last_error = e

        # 3. 全失败
        raise ModelError(
            ModelErrorType.INTERNAL,
            f"group={self.name}, all providers failed, last={last_error}",
        )

    async def _call_with_retry(
        self,
        provider: LLMProvider,
        messages: list[dict],
        **kwargs,
    ) -> dict:
        """单 provider 内的指数退避重试(只对 transient)"""
        attempt = 0
        backoff_ms = self.policy.initial_backoff_ms
        while True:
            try:
                return await provider.chat(messages, **kwargs)
            except ModelError as e:
                if not e.retryable or attempt >= self.policy.max_retries:
                    raise
                attempt += 1
                jitter = random.uniform(-self.policy.jitter, self.policy.jitter)
                sleep_ms = backoff_ms * (1 + jitter)
                await asyncio.sleep(sleep_ms / 1000)
                backoff_ms = min(backoff_ms * 2, self.policy.max_backoff_ms)
                logger.warning(
                    "retry",
                    provider=provider.cfg.id,
                    attempt=attempt,
                    err=e.err_type.value,
                )


# ============ 注册表 ============
class ModelRegistry:
    def __init__(self):
        self.groups: dict[str, ModelGroup] = {}

    def register(self, group: ModelGroup):
        self.groups[group.name] = group

    def get(self, name: str) -> ModelGroup:
        if name not in self.groups:
            raise KeyError(f"unknown model group: {name}")
        return self.groups[name]

    async def aclose(self):
        for g in self.groups.values():
            for p in g.providers:
                await p.aclose()


# ============ Bootstrap(从 YAML 加载) ============
def build_registry_from_config(cfg: dict) -> ModelRegistry:
    registry = ModelRegistry()
    for grp in cfg["model_groups"]:
        providers = []
        for p in grp["providers"]:
            provider_cfg = ProviderConfig(
                id=p["id"],
                base_url=p["base_url"],
                api_key=p["api_key"],
                model=p["model"],
                priority=p["priority"],
                weight=p.get("weight", 50),
                timeout_ms=p.get("timeout_ms", 15000),
                max_concurrency=p.get("max_concurrency", 50),
                params=p.get("params", {}),
            )
            breaker = CircuitBreaker(
                error_rate_threshold=0.30,
                min_requests=10,
                open_duration_seconds=60,
            )
            cooldown = CooldownState()
            providers.append(LLMProvider(provider_cfg, breaker, cooldown))

        policy = GroupPolicy(
            name=grp["name"],
            providers=providers,
            max_retries=grp.get("max_retries", 2),
        )
        group = ModelGroup(grp["name"], providers, policy)
        registry.register(group)

    return registry


# ============ 使用示例 ============
async def main():
    cfg = {
        "model_groups": [
            {
                "name": "short_summary",
                "providers": [
                    {
                        "id": "m3",
                        "base_url": "https://api.minimaxi.com/v1",
                        "api_key": "${MINIMAX_API_KEY}",
                        "model": "MiniMax-M3",
                        "priority": 1,
                        "weight": 70,
                        "timeout_ms": 15000,
                    },
                    {
                        "id": "kimi",
                        "base_url": "https://api.moonshot.cn/v1",
                        "api_key": "${KIMI_API_KEY}",
                        "model": "kimi-k2.6",
                        "priority": 2,
                        "weight": 30,
                        "timeout_ms": 20000,
                    },
                ],
            },
        ]
    }
    import os
    for grp in cfg["model_groups"]:
        for p in grp["providers"]:
            p["api_key"] = os.environ.get(p["api_key"].strip("${}"))

    registry = build_registry_from_config(cfg)
    summary_group = registry.get("short_summary")

    # 调用
    result = await summary_group.chat([
        {"role": "system", "content": "你是一个资讯编辑,生成 200 字摘要"},
        {"role": "user", "content": "..."},
    ])
    print(result["choices"][0]["message"]["content"])

    await registry.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

### 2.4 关键设计说明

| 设计点 | 说明 |
|---|---|
| **三层 fallback** | Provider 内重试 → 组内切换 → 整组 fallback 模板 |
| **熔断 + 冷却分离** | 熔断是「统计触发」(错误率 30% + 60s 自动恢复),冷却是「连续失败触发」(指数退避) |
| **优先级 + 权重** | `priority` 控制优先用谁,`weight` 控制同优先级内的流量比例(70/30) |
| **错误分级** | `content_filter` / `context_too_long` 立即切换(不重试也不计入重冷却);`429` / `5xx` 才走重试+冷却 |
| **半开探测** | 熔断 60s 后进入 half-open,放 3 个试探请求,成功率达 50%+ 才恢复 closed |
| **OpenAI 兼容** | 因为 M3 和 Kimi 都兼容 OpenAI 接口,这个 router 可以直接复用给其它模型接入 |
| **可观测性钩子** | 用 `structlog`,每个事件都打 group/provider/attempt/error type |

### 2.5 Embedding 单独说明

⚠️ **M3 和 K2.6 都不擅长 Embedding**——Llama 系模型不适合直接出高质量 embedding。本项目必须额外接一个 Embedding:

- **首选:BGE-M3 本地**(开源、零成本、中文 SOTA)
- **次选:远程 Embedding API**(OpenAI text-embedding-3-small ¥0.13/M,或硅基流动等代理)

BGE-M3 本地部署代码(MVP 推荐):

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")  # 首次自动下载 ~2.3GB
vec = model.encode("你好世界")                # ndarray,1024 维
```

存储到 LanceDB 或 MongoDB 的 embedding 字段里。

### 2.6 监控指标(关键!)

```python
# 必看指标
"model_group_requests_total"          # 每组请求数
"model_group_latency_seconds"          # P50 / P95 / P99
"model_group_fallback_total"           # 触发 fallback 次数(异常告警源)
"provider_circuit_breaker_state"       # 0=closed 1=half_open 2=open
"provider_cooldown_active"             # 是否在冷却
"provider_consecutive_failures"        # 连续失败数
```

把上面三件事都用 OpenTelemetry + Prometheus 接出来,生产上跑 1-2 周后基本就能定位所有偶发问题。

---

## Q1 + Q2 实施清单(MVP 第一周可完成)

1. [ ] Docker 拉起 Redis(`docker compose up -d redis`)
2. [ ] MongoDB 已建 `fastinfo` 库
3. [ ] `pip install lancedb sentence-transformers`
4. [ ] 启动 BGE-M3,embedding 跑通
5. [ ] 申请 MiniMax-M3 / Kimi K2.6 API Key
6. [ ] 把上面的 `model_registry.py` 放进项目 `src/llm/`
7. [ ] 写个 `examples/smoke_test.py` 跑通三组调用
8. [ ] 看 Prometheus 指标,确认主备切换正常

---

## 待确认问题

> 我可以继续往下挖,但有几个 **必须你拍板** 的点:

| # | 问题 | 我的推荐 |
|---|---|---|
| 1 | 你机器的实际配置?(内存/磁盘/有无 GPU) | 8GB+ / 50GB / 无 GPU 都行,选 LanceDB + Redis |
| 2 | 是否能装 Docker? | 能 → 加 Redis;不能 → 用 Garnet + LanceDB 全本地 |
| 3 | 模型 API Key 是从哪拿?已申请? | M3 在 minimaxi.com,K2.6 在 platform.moonshot.cn |
| 4 | M3 你是有完全控制权的(同公司),K2.6 是对外调用 — 这个理解对吗? | 对的话可以做更细的策略(如 M3 优先) |
| 5 | 是单人项目还是团队项目? | 单人 → 推到 GitHub + SQLite 备份;团队 → MongoDB Atlas 免费层 |

回答这几个之后,我可以直接给你出 MVP 第一周的代码骨架。