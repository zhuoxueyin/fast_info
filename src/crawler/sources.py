"""fastInfo · 数据源清单 (Day 4 扩展版)

设计:每条源用 (类型, 配置) 描述,统一被 SourceAdapter 拉取。
  - "rss"        : 经典 RSS/Atom(原有 7 个)
  - "html_rss"   : 不开放 RSS,用 HTML 列表 + 正则抠 RSS / JSON-LD (新增)
  - "html_atom"  : JSON-LD / Atom feed 隐藏端点 (新增)
  - "weibo_user" : 微博公开用户时间线 (KOL 跟踪)
  - "x_user"     : X / Twitter 公开用户 (nitter RSS 镜像)
  - "xhs_note"   : 小红书用户笔记(公开页 scrape)

新源覆盖娱乐/体育/财经/汽车/小红书/微博/X,共 13 个 RSS + 平台 KOL 接口。

注意:微博/X/小红书 公开接口经常变,生产建议走付费 API(Weibo OpenAPI / X API v2 Basic),
      这里用公开页/RSS 镜像做 MVP。
"""

# 源类型 → 抓取器映射在 src/crawler/collectors/*.py

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
    "hupu":      ("虎扑",        "https://bbs.hupu.com/rss.php"),  # 聚合
    "dongqiudi": ("懂球帝",      "https://www.dongqiudi.com/news/rss"),

    # ----- 娱乐 -----
    "bilibili":  ("B站热门",     "https://www.bilibili.com/ranking/rss/all/rank/0/3/7"),  # 全站日榜
    "douban":    ("豆瓣热门",    "https://www.douban.com/feed/review/movie"),

    # ----- 汽车 -----
    "autohome":  ("汽车之家",     "https://www.autohome.com.cn/rss/news.xml"),
}

# KOL 跟踪:微博/X/小红书
KOL_SOURCES = {
    # uid/handle -> 显示名
    "weibo:1887344341":  ("微博-任泽平",  "weibo_user"),
    "weibo:1643971635":  ("微博-老胡谈谈", "weibo_user"),
    "x:elonmusk":        ("X-Elon Musk", "x_user"),
    "x:sama":            ("X-Sam Altman", "x_user"),
    "xhs:5e3d6b00000000001000xxx_demo": ("小红书-demo", "xhs_note"),  # 占位,需要真实 id
}

# 调度间隔(秒),可在 admin 后台改
DEFAULT_CRON = {
    "rss":  1800,   # 30 min
    "kol":  3600,   # 1 h (平台风控更严)
}

# 一级类目(L1)和典型 L2(二级)
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

# 旧 item.category → L1 映射(数据迁移用)
CATEGORY_LEGACY_MAP = {
    "AI": "AI", "AI芯片": "AI", "AI框架": "AI", "人工智能": "AI", "机器人/人工智能": "AI", "机器人": "AI",
    "科技": "科技", "互联网科技": "科技", "科技/数码/应用推荐": "科技", "科技创新": "科技",
    "科技半导体": "科技", "科技投资": "科技", "科技融资": "科技", "数码评测": "科技",
    "汽车": "汽车", "汽车资讯": "汽车", "自动驾驶": "汽车", "新能源": "汽车",
    "财经": "财经", "财经-融资": "财经", "融资": "财经", "商业-融资": "财经", "创业分享": "财经",
    "体育赛事": "体育", "影视娱乐": "娱乐", "教育政策": "其他", "旅游": "其他", "音频技术": "科技",
    "职业发展": "其他", "综合新闻": "其他", "其他": "其他",
}

# 源 → L1 分类(admin 任务页按类目分组展示用)
SOURCE_L1_MAP = {
    "36kr": "科技", "huxiu": "科技", "ifanr": "科技", "infoq": "科技", "sspai": "科技", "ithome": "科技",
    "qbitai": "AI",
    "wallstreetcn": "财经", "cls": "财经",
    "hupu": "体育", "dongqiudi": "体育",
    "bilibili": "娱乐", "douban": "娱乐",
    "autohome": "汽车",
    "weibo:1887344341": "财经", "weibo:1643971635": "其他",
    "x:elonmusk": "科技", "x:sama": "AI",
    "xhs:5e3d6b00000000001000xxx_demo": "其他",
}