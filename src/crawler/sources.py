"""fastInfo · 数据源清单 (Day 5 升级版)

单源管理迁移到 MongoDB `source_config` collection,代码里这份仅作只读注册表:
- 用于首次 migration (seed source_config)
- 用于代码内未持久化时的 fallback

源类型 → 抓取器映射在 src/crawler/collectors.py + 子模块。

注意:
- Day 5 已删除 xhs demo 占位 (Phase 4 真实 API 接入待办)
- Day 5 huxiu 走 mirrors.HUXIU_RSS 多 URL fallback
- Day 5 X 用 mirrors.NITTER_MIRRORS 多镜像 fallback
- 微博经 weibo_openapi.WeiboClient:有 access_token 走 OpenAPI,否则 scrape
"""

# === RSS / Hot Ranking 注册表 (only read-only registry) ===
RSS_SOURCES = {
    # ----- 科技 / AI -----
    "36kr":      ("36氪",       "https://36kr.com/feed"),
    "huxiu":     ("虎嗅",       "https://www.huxiu.com/rss/0.xml"),
    "ifanr":     ("爱范儿",      "https://www.ifanr.com/feed"),
    "qbitai":    ("量子位",      "https://www.qbitai.com/feed"),
    "infoq":     ("InfoQ中国",   "https://www.infoq.cn/feed.xml"),
    "sspai":     ("少数派",      "https://sspai.com/feed"),
    "ithome":    ("IT之家",      "https://www.ithome.com/rss/"),

    # ----- 财经 -----
    "wallstreetcn": ("华尔街见闻",  "https://wallstreetcn.com/rss"),
    "cls":       ("财联社",       "https://www.cls.cn/nodeapi/updateTelegraphList?app=CailianpressWeb&category=&hasFirstVipArticle=1&os=web&refresh_type=1&rn=20&subscribedColumnIds=&sv=7.7.5"),

    # ----- 体育 -----
    "hupu":      ("虎扑",        "https://bbs.hupu.com/rss.php"),
    "dongqiudi": ("懂球帝",      "https://www.dongqiudi.com/news/rss"),

    # ----- 娱乐 -----
    "bilibili":  ("B站热门",     "https://www.bilibili.com/ranking/rss/all/rank/0/3/7"),
    "douban":    ("豆瓣热门",    "https://www.douban.com/feed/review/movie"),

    # ----- 汽车 -----
    "autohome":  ("汽车之家",     "https://www.autohome.com.cn/rss/news.xml"),

    # ----- Day 6 v0.3.0 新增(主流国内 + 国外补充) -----
    "geekpark":  ("极客公园",     "https://www.geekpark.net/rss"),         # 主流科技深度
    "tmtpost":   ("钛媒体",       "https://www.tmtpost.com/rss.xml"),       # TMT 行业深度
    "jiqizhixin":("机器之心",    "https://www.jiqizhixin.com/rss"),        # AI 深度(与量子位互补)
    "nbd":       ("每日经济新闻", "https://www.nbd.com.cn/rss"),             # 财经政经
    "ars":       ("Ars Technica","https://feeds.arstechnica.com/arstechnica/index"),  # 国外 1
    "reuters_zh":("Reuters 中文", "https://www.reutersagency.com/feed/?best-topics=top-news&post_type=best"),  # 国外 2

    # ----- Day 7 v0.4.0 主流覆盖补源 -----
    # AI 类目(4 个,不扭转 fastInfo 定位)
    "anthropic": ("Anthropic 官方博客", "https://www.anthropic.com/news/rss.xml"),
    "openai":    ("OpenAI 博客",         "https://openai.com/blog/rss.xml"),
    "deepmind":  ("DeepMind Blog",       "https://deepmind.google/blog/rss.xml"),
    "huggingface":("Hugging Face Blog",  "https://huggingface.co/blog/feed.xml"),
    # 汽车类目(摆脱单点)
    "diandong":  ("电动邦",              "https://www.diandong.com/rss"),
    "chedongxi": ("车东西",              "https://www.chedongxi.com/rss"),
    # 娱乐类目加热点
    "weibo_hot": ("微博热搜",            "https://rsshub.app/weibo/search/hot"),
    "douyin_hot":("抖音热榜",            "https://rsshub.app/douyin/hot"),
    # 36氪深度/汽车(复用 URL 加分类)
    # 已有 36kr 上加分类映射,不重复加
}

KOL_SOURCES = {
    # uid/handle -> 显示名, kind
    "weibo:1887344341":  ("微博-任泽平",  "weibo_user"),
    "weibo:1643971635":  ("微博-老胡谈谈", "weibo_user"),
    "x:elonmusk":        ("X-Elon Musk", "x_user"),
    "x:sama":            ("X-Sam Altman", "x_user"),
    # xhs demo 已 Day 5 删除;Phase 4 接真实 API 后再加
}

DEFAULT_CRON = {
    "rss":        1800,   # 30 min
    "kol":        3600,   # 1 h
    "hot_ranking": 1800,  # 30 min
}

CATEGORY_L1 = ["科技", "AI", "体育", "娱乐", "财经", "汽车", "其他"]

CATEGORY_L2 = {
    "科技": ["互联网", "硬件", "数码评测", "科技融资", "科技投资", "开源"],
    "AI": ["AI框架", "AI芯片", "大模型", "AI应用", "机器人"],
    "体育": ["足球", "篮球", "电竞", "综合"],
    "娱乐": ["影视", "音乐", "明星", "综艺", "动漫"],
    "财经": ["宏观", "A股", "港股", "美股", "币圈", "公司", "创业"],
    "汽车": ["新能源", "自动驾驶", "传统车企", "新势力"],
    "其他": ["社会", "教育", "健康", "其他"],
}

CATEGORY_LEGACY_MAP = {
    "AI": "AI", "AI芯片": "AI", "AI框架": "AI", "人工智能": "AI",
    "机器人/人工智能": "AI", "机器人": "AI",
    "科技": "科技", "互联网科技": "科技", "科技/数码/应用推荐": "科技",
    "科技创新": "科技", "科技半导体": "科技", "科技投资": "科技",
    "科技融资": "科技", "数码评测": "科技",
    "汽车": "汽车", "汽车资讯": "汽车", "自动驾驶": "汽车", "新能源": "汽车",
    "财经": "财经", "财经-融资": "财经", "融资": "财经",
    "商业-融资": "财经", "创业分享": "财经",
    "体育赛事": "体育", "影视娱乐": "娱乐", "教育政策": "其他",
    "旅游": "其他", "音频技术": "科技",
    "职业发展": "其他", "综合新闻": "其他", "其他": "其他",
}

# 类目-默认映射(Day 5 用于 seed source_config 时填 l1)
SOURCE_L1_DEFAULT = {
    "36kr": "科技", "huxiu": "科技", "ifanr": "科技",
    "infoq": "科技", "sspai": "科技", "ithome": "科技",
    "qbitai": "AI",
    "wallstreetcn": "财经", "cls": "财经",
    "hupu": "体育", "dongqiudi": "体育",
    "bilibili": "娱乐", "douban": "娱乐",
    "autohome": "汽车",
    "weibo:1887344341": "财经", "weibo:1643971635": "其他",
    "x:elonmusk": "科技", "x:sama": "AI",
    # Day 6 v0.3.0 新增
    "geekpark": "科技", "tmtpost": "科技", "jiqizhixin": "AI", "nbd": "财经",
    "ars": "科技", "reuters_zh": "财经",  # 英文源后续走翻译
    # Day 7 v0.4.0 新增
    "anthropic": "AI", "openai": "AI", "deepmind": "AI", "huggingface": "AI",
    "diandong": "汽车", "chedongxi": "汽车",
    "weibo_hot": "娱乐", "douyin_hot": "娱乐",
}

SOURCE_LANG = {
    "ars": "en", "reuters_zh": "en", "anthropic": "en", "openai": "en",
    "deepmind": "en", "huggingface": "en",
    # 其他都是中文(包含 reuters_zh 的标题中文版)
}

# 向后兼容别名
SOURCE_L1_MAP = SOURCE_L1_DEFAULT
