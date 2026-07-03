"""
fastInfo · LLM Gateway(MMX M2.7-highspeed / M2.7 / M3 + K2.6 模型组路由)
========================================================

模型组路由顺序(MMX 同链路 → Kimi 兜底):
    M2.7-highspeed (priority=1) → M2.7 (priority=2) → M3 (priority=3) → Kimi K2.6 (priority=4)
- 前三个走同一链路(api.minimaxi.com/v1, 同一 MMX_API_KEY,OpenAI 协议)
- Kimi 走独立 Anthropic 协议(api.kimi.com/coding/v1, KIMI_API_KEY)作最后兜底

核心特性:
- 优先级 + 权重 负载均衡
- 熔断器(error rate 30% 触发,60s 自动恢复)
- 冷却(consecutive fail 指数退避,上限 30 分钟)
- Provider 内 retry(2 次,指数退避)
- 错误分级:内容安全/超长 → 立即切;5xx/429 → retry + cool
- OpenAI 兼容协议 + Anthropic 兼容协议(K2.6)
- 结构化日志(structlog)

Usage:
    from src.llm.model_registry import build_default_registry
    registry = build_default_registry()
    summary = registry.get("short_summary")
    result = await summary.chat(messages)
"""

from __future__ import annotations
import asyncio
import enum
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx

import logging

logger = logging.getLogger(__name__)


# ============================================================
# 错误类型
# ============================================================

class ModelErrorType(enum.Enum):
    TIMEOUT = "timeout"
    HTTP_5XX = "http_5xx"
    HTTP_429 = "http_429"
    CONTENT_FILTER = "content_filter"
    CONTEXT_TOO_LONG = "context_too_long"
    BAD_REQUEST = "bad_request"
    INTERNAL = "internal"


class ModelError(Exception):
    def __init__(self, err_type: ModelErrorType, message: str, retryable: bool = True):
        super().__init__(message)
        self.err_type = err_type
        self.retryable = retryable


# ============================================================
# 配置 dataclass
# ============================================================

@dataclass
class ProviderConfig:
    id: str
    base_url: str
    api_key_env: str         # 改成 env name,不存真实 key
    model: str
    priority: int
    weight: int = 50
    timeout_ms: int = 15000
    max_concurrency: int = 50
    extra_headers: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    protocol: str = "openai"   # 'openai' = Chat Completions; 'anthropic' = Messages
    api_key: str = field(default="", init=False)  # 运行时从 env 读取

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        if self.protocol not in ("openai", "anthropic"):
            raise ValueError(f"protocol must be 'openai' or 'anthropic', got {self.protocol!r}")
        # 立即尝试加载 key
        self.api_key = os.environ.get(self.api_key_env, "")
        if not self.api_key:
            logger.warning(
                "provider.missing_api_key",
                extra={"provider_id": self.id, "env": self.api_key_env, "protocol": self.protocol},
            )


@dataclass
class GroupPolicy:
    name: str
    max_retries: int = 2
    initial_backoff_ms: int = 200
    max_backoff_ms: int = 2000
    jitter: float = 0.2


# ============================================================
# 熔断器
# ============================================================

class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    error_rate_threshold: float = 0.30
    min_requests: int = 10
    open_duration_seconds: float = 60.0
    half_open_max_probes: int = 3

    state: CircuitState = CircuitState.CLOSED
    total: int = 0
    errors: int = 0
    opened_at: float = 0.0
    probe_success: int = 0
    probe_failure: int = 0

    def allow(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.opened_at > self.open_duration_seconds:
                self.state = CircuitState.HALF_OPEN
                self.probe_success = 0
                self.probe_failure = 0
                logger.info("circuit_breaker.half_open")
                return True
            return False
        return self.probe_success + self.probe_failure < self.half_open_max_probes

    def record(self, success: bool):
        if self.state == CircuitState.HALF_OPEN:
            if success:
                self.probe_success += 1
                if self.probe_success >= max(self.half_open_max_probes // 2, 1):
                    self.state = CircuitState.CLOSED
                    self.total = 0
                    self.errors = 0
                    logger.info("circuit_breaker.closed")
            else:
                self.probe_failure += 1
                self.opened_at = time.time()
                self.state = CircuitState.OPEN
                logger.warning("circuit_breaker.reopened")
            return

        self.total += 1
        if not success:
            self.errors += 1
        if self.total >= self.min_requests:
            err_rate = self.errors / self.total
            if err_rate >= self.error_rate_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.time()
                logger.warning(
                    "circuit_breaker.opened",
                    extra={"error_rate": err_rate, "errors": self.errors, "total": self.total},
                )


# ============================================================
# 冷却(cooldown)
# ============================================================

@dataclass
class CooldownState:
    consecutive_failures: int = 0
    cooldown_until: float = 0.0

    def is_cooling(self) -> bool:
        return time.time() < self.cooldown_until

    def record_failure(self, base_seconds: int = 300):
        self.consecutive_failures += 1
        secs = min(base_seconds * (2 ** (self.consecutive_failures - 1)), 1800)
        self.cooldown_until = time.time() + secs
        logger.warning(
            "cooldown.triggered",
            extra={"consecutive": self.consecutive_failures, "cooldown_seconds": secs},
        )

    def record_success(self):
        self.consecutive_failures = 0
        self.cooldown_until = 0.0


# ============================================================
# Provider 适配器
# ============================================================

class LLMProvider:
    def __init__(self, cfg: ProviderConfig, breaker: CircuitBreaker, cooldown: CooldownState):
        self.cfg = cfg
        self.breaker = breaker
        self.cooldown = cooldown
        # 不同协议用不同的鉴权 header:
        #   OpenAI / Chat Completions -> Authorization: Bearer <key>
        #   Anthropic / Messages      -> x-api-key: <key> + anthropic-version: 2023-06-01
        if cfg.protocol == "anthropic":
            base_headers = {
                "x-api-key": cfg.api_key,
                "anthropic-version": "2023-06-01",
                **cfg.extra_headers,
            }
        else:
            base_headers = {"Authorization": f"Bearer {cfg.api_key}", **cfg.extra_headers}
        self.client = httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_ms / 1000.0,
            headers=base_headers,
        )

    async def chat(self, messages: list[dict], **kwargs) -> dict:
        if self.cfg.protocol == "anthropic":
            return await self._chat_anthropic(messages, **kwargs)
        return await self._chat_openai(messages, **kwargs)

    async def _chat_openai(self, messages: list[dict], **kwargs) -> dict:
        body = {"model": self.cfg.model, "messages": messages, **self.cfg.params, **kwargs}
        async with self.cfg._semaphore:
            try:
                resp = await self.client.post("/chat/completions", json=body)
                self._check_response_openai(resp)
                return resp.json()
            except ModelError:
                raise
            except httpx.TimeoutException as e:
                raise ModelError(ModelErrorType.TIMEOUT, "timeout") from e
            except httpx.HTTPError as e:
                raise ModelError(ModelErrorType.INTERNAL, str(e)) from e

    async def _chat_anthropic(self, messages: list[dict], **kwargs) -> dict:
        # Anthropic Messages API:system 是顶级参数,messages 里不能含 role=system
        system_parts: list[str] = []
        filtered: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content", "")
                if isinstance(content, list):
                    content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
                if content:
                    system_parts.append(content)
            else:
                filtered.append(m)

        body: dict = {
            "model": self.cfg.model,
            "max_tokens": kwargs.pop("max_tokens", self.cfg.params.get("max_tokens", 4096)),
            "messages": filtered,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            body["temperature"] = kwargs["temperature"]
        # params 合并(Anthropic 顶级字段也支持 temperature/top_p/top_k 等)
        for k, v in self.cfg.params.items():
            if k not in body and k != "max_tokens":
                body[k] = v

        async with self.cfg._semaphore:
            try:
                resp = await self.client.post("/messages", json=body)
                self._check_response_anthropic(resp)
                data = resp.json()
            except ModelError:
                raise
            except httpx.TimeoutException as e:
                raise ModelError(ModelErrorType.TIMEOUT, "timeout") from e
            except httpx.HTTPError as e:
                raise ModelError(ModelErrorType.INTERNAL, str(e)) from e

        # 把 Anthropic 响应格式化成 OpenAI 风格,让上层逻辑统一处理
        text_parts: list[str] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        text = "".join(text_parts)
        return {
            "id": data.get("id", ""),
            "model": data.get("model", self.cfg.model),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": data.get("stop_reason", "stop"),
            }],
            "usage": data.get("usage", {}),
        }

    def _check_response_openai(self, resp: httpx.Response):
        if resp.status_code == 200:
            return
        if resp.status_code == 429:
            raise ModelError(ModelErrorType.HTTP_429, "rate limit", retryable=False)
        if resp.status_code in (400, 403):
            body = resp.text
            if "content_filter" in body or "敏感" in body or "blocked" in body.lower():
                raise ModelError(ModelErrorType.CONTENT_FILTER, "blocked", retryable=False)
            if "context_length" in body or "too long" in body or "maximum context" in body:
                raise ModelError(ModelErrorType.CONTEXT_TOO_LONG, "context too long", retryable=False)
            raise ModelError(ModelErrorType.BAD_REQUEST, body, retryable=False)
        if resp.status_code >= 500:
            raise ModelError(ModelErrorType.HTTP_5XX, f"{resp.status_code}")
        raise ModelError(ModelErrorType.INTERNAL, resp.text)

    def _check_response_anthropic(self, resp: httpx.Response):
        if resp.status_code == 200:
            return
        if resp.status_code == 429:
            raise ModelError(ModelErrorType.HTTP_429, "rate limit", retryable=False)
        if resp.status_code in (400, 403):
            try:
                data = resp.json()
                err_obj = data.get("error", {})
                err_type = err_obj.get("type", "")
                msg = err_obj.get("message", resp.text)
            except Exception:
                err_type, msg = "", resp.text
            if err_type == "authentication_error":
                raise ModelError(ModelErrorType.BAD_REQUEST, f"auth: {msg}", retryable=False)
            if "context_length" in msg.lower() or "too long" in msg.lower():
                raise ModelError(ModelErrorType.CONTEXT_TOO_LONG, msg, retryable=False)
            if "content_filter" in msg.lower() or "refused" in msg.lower():
                raise ModelError(ModelErrorType.CONTENT_FILTER, msg, retryable=False)
            raise ModelError(ModelErrorType.BAD_REQUEST, msg, retryable=False)
        if resp.status_code >= 500:
            raise ModelError(ModelErrorType.HTTP_5XX, f"{resp.status_code}")
        raise ModelError(ModelErrorType.INTERNAL, resp.text)

    async def aclose(self):
        await self.client.aclose()


# ============================================================
# 模型组(Gateway)
# ============================================================

class ModelGroup:
    def __init__(self, name: str, providers: list[LLMProvider], policy: GroupPolicy):
        self.name = name
        self.providers = sorted(providers, key=lambda p: p.cfg.priority)
        self.policy = policy

    def _select_provider(self) -> LLMProvider | None:
        available = [p for p in self.providers
                     if p.cfg.api_key                          # 单 key 降级:无 key 不参与
                     and not p.cooldown.is_cooling()
                     and p.breaker.allow()]
        if not available:
            return None  # 无可用 provider,直接报错,不再 fall back 到失败路径

        groups = defaultdict(list)
        for p in available:
            groups[p.cfg.priority].append(p)

        for prio in sorted(groups.keys()):
            same = groups[prio]
            total = sum(p.cfg.weight for p in same)
            r = random.uniform(0, total)
            acc = 0
            for p in same:
                acc += p.cfg.weight
                if r <= acc:
                    return p
            return same[0]
        return available[0]

    def _classify_cooldown(self, err_type: ModelErrorType) -> int:
        if err_type in (ModelErrorType.CONTENT_FILTER, ModelErrorType.CONTEXT_TOO_LONG):
            return 60
        if err_type == ModelErrorType.HTTP_429:
            return 120
        if err_type in (ModelErrorType.TIMEOUT, ModelErrorType.HTTP_5XX):
            return 300
        return 60

    async def chat(self, messages: list[dict], **kwargs) -> dict:
        last_error: ModelError | None = None
        primary = self._select_provider()

        if primary and primary.cfg.api_key:
            try:
                result = await self._call_with_retry(primary, messages, **kwargs)
                primary.breaker.record(success=True)
                primary.cooldown.record_success()
                return result
            except ModelError as e:
                last_error = e
                primary.breaker.record(success=False)
                primary.cooldown.record_failure(base_seconds=self._classify_cooldown(e.err_type))

        for candidate in self.providers:
            if candidate is primary:
                continue
            if candidate.cooldown.is_cooling() or not candidate.breaker.allow():
                continue
            if not candidate.cfg.api_key:
                continue
            try:
                result = await self._call_with_retry(candidate, messages, **kwargs)
                candidate.breaker.record(success=True)
                candidate.cooldown.record_success()
                logger.info(
                    "fallback.success",
                    extra={
                        "group": self.name,
                        "primary_failed": last_error.err_type.value if last_error else None,
                        "fallback_to": candidate.cfg.id,
                    },
                )
                return result
            except ModelError as e:
                candidate.breaker.record(success=False)
                last_error = e

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
                sleep_s = (backoff_ms * (1 + jitter)) / 1000
                await asyncio.sleep(sleep_s)
                backoff_ms = min(backoff_ms * 2, self.policy.max_backoff_ms)
                logger.warning(
                    "retry",
                    extra={"provider": provider.cfg.id, "attempt": attempt, "err": e.err_type.value},
                )


# ============================================================
# 注册表
# ============================================================

class ModelRegistry:
    def __init__(self):
        self.groups: dict[str, ModelGroup] = {}

    def register(self, group: ModelGroup):
        self.groups[group.name] = group

    def get(self, name: str) -> ModelGroup:
        if name not in self.groups:
            raise KeyError(f"unknown model group: {name}")
        return self.groups[name]

    def list_groups(self) -> list[str]:
        return list(self.groups.keys())

    async def aclose(self):
        for g in self.groups.values():
            for p in g.providers:
                await p.aclose()


# ============================================================
# Bootstrap: 默认配置(MMX 链路:highspeed → m2.7 → m3,Kimi 兜底)
#
# 路由顺序(priority 越小越优先):
#   1) M2.7-highspeed (主力,高速档,OpenAI 协议,api.minimaxi.com,同 MMX_API_KEY)
#   2) M2.7          (兜底1,标准档,OpenAI 协议,api.minimaxi.com,同 MMX_API_KEY)
#   3) M3            (兜底2,标准档,OpenAI 协议,api.minimaxi.com,同 MMX_API_KEY)
#   4) Kimi K2.6     (兜底3,Anthropic 协议,api.kimi.com/coding,KIMI_API_KEY)
#   没设 key 时 provider 自动跳过,不影响更高优先级调用
# ============================================================

def _make_provider(spec: dict) -> LLMProvider:
    cfg = ProviderConfig(
        id=spec["id"],
        base_url=spec["base_url"],
        api_key_env=spec["api_key_env"],
        model=spec["model"],
        priority=spec["priority"],
        weight=spec.get("weight", 100),
        timeout_ms=spec.get("timeout_ms", 15000),
        max_concurrency=spec.get("max_concurrency", 50),
        params=spec.get("params", {}),
        extra_headers=spec.get("extra_headers", {}),
        protocol=spec.get("protocol", "openai"),
    )
    return LLMProvider(cfg, CircuitBreaker(), CooldownState())


def _mmx(spec: dict) -> dict:
    """MMX 链路 helper:同 base_url / 同 api_key_env / OpenAI 协议
    在 DEFAULT_GROUPS_SPEC 里给 MMX 系列模型(M2.7-highspeed / M2.7 / M3)复用配置。"""
    base = {
        "base_url": "https://api.minimaxi.com/v1",
        "api_key_env": "MMX_API_KEY",
    }
    return {**base, **spec}


# 任务 → 模型组映射
# 路由顺序:highspeed(1) → m2.7(2) → m3(3) → kimi(4)
DEFAULT_GROUPS_SPEC = [
    {
        "name": "short_summary",
        "providers": [
            _mmx({"id": "m2_7_highspeed", "model": "MiniMax-M2.7-highspeed",
                   "priority": 1, "timeout_ms": 15000,
                   "params": {"max_tokens": 600}}),
            _mmx({"id": "m2_7",            "model": "MiniMax-M2.7",
                   "priority": 2, "timeout_ms": 15000,
                   "params": {"max_tokens": 600}}),
            _mmx({"id": "m3",              "model": "MiniMax-M3",
                   "priority": 3, "timeout_ms": 15000,
                   "params": {"max_tokens": 600}}),
            {"id": "kimi",
             "base_url": "https://api.kimi.com/coding/v1",
             "api_key_env": "KIMI_API_KEY",
             "model": "kimi-k2.6",
             "priority": 4, "timeout_ms": 20000, "protocol": "anthropic",
             "params": {"max_tokens": 600}},
        ],
    },
    {
        "name": "long_summary",
        "providers": [
            _mmx({"id": "m2_7_highspeed", "model": "MiniMax-M2.7-highspeed",
                   "priority": 1, "timeout_ms": 45000,
                   "params": {"max_tokens": 2000}}),
            _mmx({"id": "m2_7",            "model": "MiniMax-M2.7",
                   "priority": 2, "timeout_ms": 45000,
                   "params": {"max_tokens": 2000}}),
            _mmx({"id": "m3",              "model": "MiniMax-M3",
                   "priority": 3, "timeout_ms": 45000,
                   "params": {"max_tokens": 2000}}),
            {"id": "kimi",
             "base_url": "https://api.kimi.com/coding/v1",
             "api_key_env": "KIMI_API_KEY",
             "model": "kimi-k2.6",
             "priority": 4, "timeout_ms": 45000, "protocol": "anthropic",
             "params": {"max_tokens": 2000}},
        ],
    },
    {
        "name": "deep_interpretation",
        "providers": [
            _mmx({"id": "m2_7_highspeed", "model": "MiniMax-M2.7-highspeed",
                   "priority": 1, "timeout_ms": 90000,
                   "params": {"max_tokens": 8192}}),
            _mmx({"id": "m2_7",            "model": "MiniMax-M2.7",
                   "priority": 2, "timeout_ms": 90000,
                   "params": {"max_tokens": 8192}}),
            _mmx({"id": "m3-thinking",     "model": "MiniMax-M3",
                   "priority": 3, "timeout_ms": 90000,
                   "params": {"max_tokens": 8192},
                   # 后续按 M3 文档加 thinking mode 参数
                   }),
            {"id": "kimi",
             "base_url": "https://api.kimi.com/coding/v1",
             "api_key_env": "KIMI_API_KEY",
             "model": "kimi-k2.6",
             "priority": 4, "timeout_ms": 90000, "protocol": "anthropic",
             "params": {"max_tokens": 8192}},
        ],
    },
    {
        "name": "nl_parse",
        "providers": [
            _mmx({"id": "m2_7_highspeed", "model": "MiniMax-M2.7-highspeed",
                   "priority": 1, "timeout_ms": 10000,
                   "params": {"max_tokens": 500, "temperature": 0.2}}),
            _mmx({"id": "m2_7",            "model": "MiniMax-M2.7",
                   "priority": 2, "timeout_ms": 10000,
                   "params": {"max_tokens": 500, "temperature": 0.2}}),
            _mmx({"id": "m3",              "model": "MiniMax-M3",
                   "priority": 3, "timeout_ms": 10000,
                   "params": {"max_tokens": 500, "temperature": 0.2}}),
            {"id": "kimi",
             "base_url": "https://api.kimi.com/coding/v1",
             "api_key_env": "KIMI_API_KEY",
             "model": "kimi-k2.6",
             "priority": 4, "timeout_ms": 10000, "protocol": "anthropic",
             "params": {"max_tokens": 500, "temperature": 0.2}},
        ],
    },
]


def build_default_registry() -> ModelRegistry:
    registry = ModelRegistry()
    for spec in DEFAULT_GROUPS_SPEC:
        providers = [_make_provider(p) for p in spec["providers"]]
        policy = GroupPolicy(
            name=spec["name"],
            max_retries=spec.get("max_retries", 2),
        )
        registry.register(ModelGroup(spec["name"], providers, policy))
    return registry
