-- fastInfo PostgreSQL Schema v1
-- 适用于 PostgreSQL 16+

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- 模糊检索
CREATE EXTENSION IF NOT EXISTS "pg_cron";     -- 可选:定时任务

-- ============================================================
-- 1. 用户与认证
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    display_name    VARCHAR(100),
    avatar_url      TEXT,
    password_hash   TEXT,                  -- bcrypt;OAuth 用户为 NULL
    oauth_provider  VARCHAR(20),           -- google/github/wechat
    oauth_id        VARCHAR(255),
    plan            VARCHAR(20) DEFAULT 'free',  -- free / pro / team
    status          VARCHAR(20) DEFAULT 'active', -- active / suspended / deleted
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);

-- API Key(开发者)
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100),
    key_hash        VARCHAR(255) UNIQUE NOT NULL,  -- SHA256(key)
    key_prefix      VARCHAR(12) NOT NULL,           -- 前 8 位用于显示
    scopes          TEXT[] DEFAULT ARRAY['read'],
    rate_limit      INTEGER DEFAULT 60,             -- req/min
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- ============================================================
-- 2. 订阅任务
-- ============================================================

CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 自然语言解析后的结构化定义
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    nl_query        TEXT,                              -- 原始自然语言输入
    keywords        TEXT[] NOT NULL DEFAULT '{}',
    exclude_keywords TEXT[] DEFAULT '{}',
    sources         TEXT[] DEFAULT '{}',                -- ['arxiv', '36kr', 'weibo_hot']
    categories      TEXT[] DEFAULT '{}',                -- ['AI', 'finance']
    languages       TEXT[] DEFAULT ARRAY['zh', 'en'],

    -- 调度
    cron_expr       VARCHAR(100) NOT NULL,             -- '0 9 * * *'
    timezone        VARCHAR(50) DEFAULT 'Asia/Shanghai',
    delivery        VARCHAR(20) DEFAULT 'email',      -- email / webhook / in_app

    -- 配置
    summary_style   VARCHAR(20) DEFAULT 'short',      -- short / brief / deep
    max_items       INTEGER DEFAULT 10,
    is_active       BOOLEAN DEFAULT TRUE,

    -- 状态
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    run_count       INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    last_error      TEXT,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subs_user ON subscriptions(user_id);
CREATE INDEX idx_subs_active ON subscriptions(is_active, next_run_at);
CREATE INDEX idx_subs_keywords ON subscriptions USING GIN(keywords);

-- 订阅运行历史
CREATE TABLE subscription_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'running',    -- running / success / failed / partial
    items_found     INTEGER DEFAULT 0,
    items_sent      INTEGER DEFAULT 0,
    tokens_used     INTEGER DEFAULT 0,
    cost_cents      INTEGER DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_runs_sub ON subscription_runs(subscription_id, started_at DESC);

-- ============================================================
-- 3. 采集源(Source Adapter 元数据)
-- ============================================================

CREATE TABLE sources (
    id              VARCHAR(50) PRIMARY KEY,           -- 'weibo_hot' / 'arxiv_ai'
    name            VARCHAR(100) NOT NULL,
    category        VARCHAR(50) NOT NULL,             -- rss / academic / social / blog
    homepage        TEXT,
    adapter_class   VARCHAR(200),                     -- Python class path
    config          JSONB DEFAULT '{}',               -- 抓取参数
    rate_limit      INTEGER DEFAULT 60,               -- req/min
    is_active       BOOLEAN DEFAULT TRUE,
    last_fetch_at   TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    fetch_count     BIGINT DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. 内容(原始与摘要)
-- ============================================================

CREATE TABLE items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       VARCHAR(50) NOT NULL REFERENCES sources(id),
    external_id     VARCHAR(500) NOT NULL,            -- 源站 ID
    url             TEXT NOT NULL,
    url_hash        VARCHAR(64) UNIQUE NOT NULL,      -- SHA256(url) 用于去重

    title           TEXT NOT NULL,
    content_md      TEXT,                              -- 抽取后的 Markdown
    content_html    TEXT,                              -- 原始 HTML(存 S3,这里只存路径)
    raw_path        TEXT,                              -- S3 / MinIO 路径

    author          VARCHAR(200),
    author_id       VARCHAR(200),
    published_at    TIMESTAMPTZ,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),

    language        VARCHAR(10) DEFAULT 'zh',
    category        VARCHAR(50),                       -- 自动分类
    tags            TEXT[] DEFAULT '{}',

    -- 指标
    metrics         JSONB DEFAULT '{}',                -- {views, likes, comments, shares}

    -- 摘要
    summary_short   TEXT,                              -- < 200 字
    summary_long    TEXT,                              -- < 800 字
    summary_model   VARCHAR(50),                       -- 用的模型
    key_points      TEXT[] DEFAULT '{}',

    -- 向量(仅存 ID,向量在 Qdrant)
    embedded        BOOLEAN DEFAULT FALSE,
    embedded_at     TIMESTAMPTZ,

    -- 元数据
    is_deleted      BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_items_source ON items(source_id, published_at DESC);
CREATE INDEX idx_items_published ON items(published_at DESC);
CREATE INDEX idx_items_url_hash ON items(url_hash);
CREATE INDEX idx_items_category ON items(category, published_at DESC);
CREATE INDEX idx_items_title_trgm ON items USING GIN(title gin_trgm_ops);
CREATE INDEX idx_items_tags ON items USING GIN(tags);

-- 内容-订阅关联(推送记录)
CREATE TABLE subscription_items (
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    item_id         UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    run_id          UUID REFERENCES subscription_runs(id) ON DELETE SET NULL,
    relevance_score FLOAT,                            -- 0-1,相关性打分
    delivered_at    TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    feedback        SMALLINT,                         -- -1 / 0 / 1 用户反馈
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (subscription_id, item_id)
);

CREATE INDEX idx_sub_items_run ON subscription_items(run_id);

-- ============================================================
-- 5. 热榜
-- ============================================================

CREATE TABLE hotboard_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       VARCHAR(50) NOT NULL REFERENCES sources(id),
    rank            INTEGER NOT NULL,
    title           TEXT NOT NULL,
    url             TEXT,
    score           BIGINT,                           -- 热度值
    snapshot_at     TIMESTAMPTZ NOT NULL,
    raw             JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hotboard_source_time ON hotboard_entries(source_id, snapshot_at DESC);

-- ============================================================
-- 6. 关键词监控
-- ============================================================

CREATE TABLE keyword_monitors (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    keyword         VARCHAR(200) NOT NULL,
    scope           VARCHAR(50) DEFAULT 'all',        -- all / hotboard / items
    threshold       INTEGER DEFAULT 1,                -- 触发阈值(分钟内出现次数)
    window_minutes  INTEGER DEFAULT 60,
    delivery        VARCHAR(20) DEFAULT 'email',
    is_active       BOOLEAN DEFAULT TRUE,
    last_trigger_at TIMESTAMPTZ,
    trigger_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_keyword_monitors_user ON keyword_monitors(user_id, is_active);

-- ============================================================
-- 7. 研报
-- ============================================================

CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    title           VARCHAR(300) NOT NULL,
    topic           TEXT,
    template        VARCHAR(50),                       -- daily_papers / weekly_models / custom
    status          VARCHAR(20) DEFAULT 'pending',    -- pending / running / success / failed
    content_md      TEXT,                              -- 最终 Markdown 内容
    content_json    JSONB,                              -- 结构化大纲与引用
    references      JSONB DEFAULT '[]',                -- 引用清单 [{item_id, url, title}]
    tokens_used     INTEGER DEFAULT 0,
    cost_cents      INTEGER DEFAULT 0,

    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reports_user ON reports(user_id, created_at DESC);
CREATE INDEX idx_reports_status ON reports(status, created_at DESC);

-- ============================================================
-- 8. 任务队列(本地简化版,生产建议用 Redis Streams)
-- ============================================================

CREATE TABLE task_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type       VARCHAR(50) NOT NULL,              -- fetch / summarize / embed / deliver
    payload         JSONB NOT NULL,
    priority        SMALLINT DEFAULT 5,
    status          VARCHAR(20) DEFAULT 'pending',    -- pending / running / done / failed
    attempts        INTEGER DEFAULT 0,
    max_attempts    INTEGER DEFAULT 3,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_queue_status ON task_queue(status, run_at);
CREATE INDEX idx_queue_type ON task_queue(task_type, status);

-- ============================================================
-- 9. 用户反馈与埋点
-- ============================================================

CREATE TABLE user_feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    item_id         UUID REFERENCES items(id) ON DELETE CASCADE,
    report_id       UUID REFERENCES reports(id) ON DELETE CASCADE,
    feedback_type   VARCHAR(50) NOT NULL,              -- useful / not_useful / spam / irrelevant
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_item ON user_feedback(item_id);

CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type      VARCHAR(100) NOT NULL,
    properties      JSONB DEFAULT '{}',
    occurred_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_type_time ON events(event_type, occurred_at DESC);

-- ============================================================
-- 10. 审计(可选,MVP 不强制)
-- ============================================================

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    actor_id        UUID,                              -- user_id 或 api_key_id
    actor_type      VARCHAR(20),                       -- user / api_key / system
    action          VARCHAR(100) NOT NULL,
    target_type     VARCHAR(50),
    target_id       VARCHAR(100),
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB DEFAULT '{}',
    occurred_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_actor ON audit_logs(actor_id, occurred_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action, occurred_at DESC);

-- ============================================================
-- 视图:用户收件箱
-- ============================================================

CREATE VIEW v_user_inbox AS
SELECT
    si.subscription_id,
    s.user_id,
    i.id            AS item_id,
    i.title,
    i.url,
    i.summary_short,
    i.summary_long,
    i.published_at,
    i.fetched_at,
    si.relevance_score,
    si.delivered_at,
    si.read_at,
    si.feedback
FROM subscription_items si
JOIN subscriptions s ON s.id = si.subscription_id
JOIN items i ON i.id = si.item_id
WHERE s.is_active = TRUE
  AND i.is_deleted = FALSE
ORDER BY si.delivered_at DESC NULLS LAST;

-- ============================================================
-- 触发器:updated_at 自动更新
-- ============================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_users
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_subscriptions
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_items
    BEFORE UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- 初始数据
-- ============================================================

INSERT INTO sources (id, name, category, homepage, adapter_class) VALUES
    ('rss_36kr', '36kr', 'rss', 'https://36kr.com', 'adapters.rss.GenericRssAdapter'),
    ('rss_huxiu', '虎嗅', 'rss', 'https://huxiu.com', 'adapters.rss.GenericRssAdapter'),
    ('rss_ithome', 'IT 之家', 'rss', 'https://ithome.com', 'adapters.rss.GenericRssAdapter'),
    ('rss_qbitai', '量子位', 'rss', 'https://qbitai.com', 'adapters.rss.GenericRssAdapter'),
    ('arxiv_ai', 'arXiv cs.AI', 'academic', 'https://arxiv.org/list/cs.AI/recent', 'adapters.arxiv.ArxivAdapter'),
    ('arxiv_cl', 'arXiv cs.CL', 'academic', 'https://arxiv.org/list/cs.CL/recent', 'adapters.arxiv.ArxivAdapter'),
    ('hf_papers', 'HuggingFace Daily Papers', 'academic', 'https://huggingface.co/papers', 'adapters.huggingface.HfPapersAdapter'),
    ('github_trending', 'GitHub Trending', 'blog', 'https://github.com/trending', 'adapters.github.TrendingAdapter'),
    ('weibo_hot', '微博热搜', 'social', 'https://s.weibo.com/top/summary', 'adapters.weibo.HotboardAdapter'),
    ('zhihu_hot', '知乎热榜', 'social', 'https://www.zhihu.com/hot', 'adapters.zhihu.HotboardAdapter'),
    ('bilibili_hot', 'B 站热门', 'social', 'https://www.bilibili.com/v/popular/rank/all', 'adapters.bilibili.HotboardAdapter');

-- 结束
-- 后续 ALTER 由 Flyway / sqlx-migrate 管理