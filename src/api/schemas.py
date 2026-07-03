"""
fastInfo · API 层 Pydantic Schemas
===================================
请求/响应模型,所有 endpoint 共用。
"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================
# Auth
# ============================================================
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=6)
    email: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class UserView(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    plan: str = "free"
    role: str = "user"
    feishu_webhook: Optional[str] = None
    wechat_webhook: Optional[str] = None
    webhook_url: Optional[str] = None


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    feishu_webhook: Optional[str] = ""
    wechat_webhook: Optional[str] = ""
    webhook_url: Optional[str] = ""


class LoginResponse(BaseModel):
    token: str
    user: UserView


# ============================================================
# Items
# ============================================================
class ItemView(BaseModel):
    """单条资讯(MongoDB items 文档)"""
    id: Optional[str] = None
    source: str
    url: str
    title: str
    summary: str = ""
    category: Optional[str] = None
    category_l1: Optional[str] = None
    relevance: Optional[float] = None
    published_at: Optional[str] = None
    fetched_at: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = []
    score: Optional[float] = None     # 仅 search 时有(textScore)


# ============================================================
# Search / Today / Hot
# ============================================================
class SearchResponse(BaseModel):
    query: str
    total: int
    items: List[ItemView]


class TodayResponse(BaseModel):
    limit: int
    items: List[ItemView]


class HotResponse(BaseModel):
    hours: int
    threshold: float
    total: int
    items: List[ItemView]


# ============================================================
# Stats
# ============================================================
class StatsResponse(BaseModel):
    total_items: int
    by_source: dict
    by_category: dict
    indexes: List[str] = []


# ============================================================
# Subscriptions
# ============================================================
class SubscribeRequest(BaseModel):
    """订阅创建请求(Day 4)"""
    title: Optional[str] = None
    nl_query: str = Field(..., min_length=2, max_length=200)
    keywords: List[str] = []
    sources: List[str] = []
    categories_l1: List[str] = []   # 一级类目: ["科技", "AI"]
    categories_l2: List[str] = []   # 二级类目: ["互联网", "AI芯片"]
    cron_expr: str = "0 9 * * *"
    max_items: int = Field(10, ge=1, le=50)
    channels: List[str] = ["inbox"]   # inbox/email/feishu/wechat/webhook
    interval_min: int = 0               # 自定义间隔(分钟);0=用 cron


class SubscriptionView(BaseModel):
    id: str
    user_id: str
    title: str
    nl_query: Optional[str] = None
    keywords: List[str] = []
    sources: List[str] = []
    categories_l1: List[str] = []
    categories_l2: List[str] = []
    channels: List[str] = ["inbox"]
    cron_expr: str
    interval_min: int = 0
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    is_active: bool
    max_items: int = 10


# ============================================================
# Day 3 新增:banner / inbox / categories / admin tasks
# ============================================================
class BannerConfig(BaseModel):
    categories: List[str]
    max_per_category: int = 3
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class BannerUpdateRequest(BaseModel):
    categories: List[str]
    max_per_category: int = Field(3, ge=1, le=10)


class InboxItem(BaseModel):
    delivered_at: Optional[str] = None
    subscription_id: str
    subscription_title: Optional[str] = None
    item: dict


class InboxResponse(BaseModel):
    items: List[InboxItem]
    total: int
    page: int
    page_size: int


class SourceStatus(BaseModel):
    source: str
    fetched_24h: int = 0
    failed_24h: int = 0
    last_run_at: Optional[str] = None
    last_latency_ms: int = 0
    healthy: bool = True


class TaskRun(BaseModel):
    run_id: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    trigger: str
    operator: Optional[str] = None
    items_fetched: int = 0
    items_summarized: int = 0
    items_failed: int = 0
    per_source: dict = {}
    llm_breakdown: dict = {}


class LLMHealth(BaseModel):
    groups: dict


class SourceCategory(BaseModel):
    """公域首页某类目下 Top N items"""
    category: str
    items: List[dict]


class SubscribeResponse(BaseModel):
    sub: SubscriptionView
    parsed: dict = Field(default_factory=dict)


class SubsListResponse(BaseModel):
    total: int
    items: List[SubscriptionView]


class RunSubscriptionResponse(BaseModel):
    subscription_id: str
    scanned: int
    matched: int
    delivered: int
    skipped: Optional[str] = None


# ============================================================
# Ingest
# ============================================================
class IngestResponse(BaseModel):
    fetched: int
    new: int
    summarized: int
    failed: int
    errors: List[str] = []
