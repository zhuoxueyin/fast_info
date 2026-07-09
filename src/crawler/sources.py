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
    # Day 11 修复:huxiu 官方 RSS 持续 timeout + 公共 RSSHub 镜像(rsshub.app/rssforever/injahow)全 403/404/503,
    # 已删除 huxiu,由 leiphone 雷锋网替代(科技/AI 同类,实测 RSS 200 + 600KB+ feed)
    "leiphone":  ("雷锋网",      "https://www.leiphone.com/feed"),
    "ifanr":     ("爱范儿",      "https://www.ifanr.com/feed"),
    "qbitai":    ("量子位",      "https://www.qbitai.com/feed"),
    "infoq":     ("InfoQ中国",   "https://www.infoq.cn/feed.xml"),
    "sspai":     ("少数派",      "https://sspai.com/feed"),
    "ithome":    ("IT之家",      "https://www.ithome.com/rss/"),

    # ----- 财经 -----
    # Day 6v2 修复:wallstreetcn 官方 /rss 已 404,改用 RSSHub 镜像 (rsshub.rssforever.com/wallstreetcn)
    "wallstreetcn": ("华尔街见闻",  "https://rsshub.rssforever.com/wallstreetcn"),
    # Day 11 修复:cls 公开 nodeapi 接口 418 + RSSHub 镜像全 503/404,
    # 改走主页 hotArticleData JSON(SSR 内嵌,稳定可用) — fetcher: collectors.fetch_cls_home
    "cls":       ("财联社",       "https://www.cls.cn/"),

    # ----- 体育 -----
    # ESPN Soccer RSS 已失效(202 empty),替换为新浪体育国际足球 RSS
    "sina_sports_soccer": ("新浪体育-国际足球", "https://rss.sina.com.cn/sports/global/focus.xml"),

    # ----- 娱乐 -----
    # Day 6v2 修复:bilibili 旧 RSS 端点 empty feed,改走官方 JSON 排行 API (在 fetch_all 里专门路由)
    # web_location=333.934 是 B 站给站内跳转用的"白名单参数",绕过裸 API 风控
    "bilibili":  ("B站热门",     "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all&web_location=333.934"),
    "douban":    ("豆瓣热门",    "https://www.douban.com/feed/review/movie"),

    # ----- 热榜 (Day 6v2 新增) -----
    # zhihu_hot 走 RSSHub 镜像,补财经/科技话题;30 条/次
    "zhihu_hot": ("知乎热榜",    "https://rsshub.rssforever.com/zhihu/hot"),
}

KOL_SOURCES = {
    # uid/handle -> 显示名, kind
    # Day 6v2 修复:微博公开 m.weibo.cn/u/{uid} scrape 被风控 302 到登录页
    # 原 weibo:1887344341 / weibo:1643971635 已 disable,等 Phase 4 接入 OpenAPI 后再恢复
    # "weibo:1887344341":  ("微博-任泽平",  "weibo_user"),
    # "weibo:1643971635":  ("微博-老胡谈谈", "weibo_user"),
    "x:sama":            ("X-Sam Altman", "x_user"),
    # xhs demo 已 Day 5 删除;Phase 4 接真实 API 后再加
    # Day 6v2:热搜词热榜 (原想接微博热搜,但 m.weibo.cn 容器 API 被风控,
    #  实际走头条公开 JSON 热点 API,source_id 仍叫 weibo:hot 是为了避免 Mongo 数据迁移)
    "weibo:hot":         ("热搜词热榜",    "weibo_hot"),
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
    # AI
    "AI": "AI", "人工智能": "AI", "大模型": "AI", "机器学习": "AI", "深度学习": "AI",
    "AIGC": "AI", "生成式AI": "AI", "多模态": "AI", "智能体": "AI", "具身智能": "AI",
    "AI芯片": "AI", "AI框架": "AI", "AI应用": "AI",
    "机器人/人工智能": "AI", "机器人": "AI", "人形机器人": "AI",
    "ChatGPT": "AI", "GPT": "AI", "LLM": "AI", "NLP": "AI", "计算机视觉": "AI",
    # 科技
    "科技": "科技", "互联网科技": "科技", "科技/数码/应用推荐": "科技",
    "科技创新": "科技", "科技半导体": "科技", "科技投资": "科技",
    "科技融资": "科技", "数码评测": "科技", "互联网": "科技",
    "半导体": "科技", "芯片": "科技", "存储": "科技", "CPU": "科技", "GPU": "科技",
    "消费电子": "科技", "通信": "科技", "5G": "科技", "物联网": "科技",
    "云计算": "科技", "SaaS": "科技", "开源": "科技", "软件": "科技",
    "网络安全": "科技", "量子计算": "科技", "生物科技": "科技",
    "航空": "科技", "航天": "科技", "无人机": "科技", "VR": "科技", "AR": "科技",
    "元宇宙": "科技", "3D打印": "科技", "制造": "科技", "工业": "科技",
    "科技职场": "科技", "职场": "科技", "音频技术": "科技",
    # 体育
    "体育赛事": "体育", "体育": "体育", "足球": "体育", "篮球": "体育",
    "电竞": "体育", "NBA": "体育", "CBA": "体育", "世界杯": "体育", "欧冠": "体育",
    "奥运会": "体育", "网球": "体育", "乒乓球": "体育", "羽毛球": "体育",
    "F1": "体育", "赛车": "体育", "马拉松": "体育", "运动": "体育",
    # 娱乐
    "影视娱乐": "娱乐", "娱乐": "娱乐", "影视": "娱乐", "电影": "娱乐",
    "电视剧": "娱乐", "音乐": "娱乐", "明星": "娱乐", "综艺": "娱乐",
    "动漫": "娱乐", "动画": "娱乐", "漫画": "娱乐", "二次元": "娱乐",
    "游戏": "娱乐", "直播": "娱乐", "短视频": "娱乐", "社交媒体": "娱乐",
    "文化": "娱乐", "美食": "娱乐", "旅游": "娱乐", "时尚": "娱乐", "艺术": "娱乐",
    # 财经
    "财经": "财经", "财经-融资": "财经", "融资": "财经",
    "商业-融资": "财经", "创业分享": "财经", "商业": "财经", "经济": "财经",
    "股市": "财经", "股票": "财经", "IPO": "财经", "上市": "财经", "投资": "财经",
    "A股": "财经", "港股": "财经", "美股": "财经", "中概股": "财经",
    "基金": "财经", "债券": "财经", "宏观": "财经", "央行": "财经",
    "GDP": "财经", "CPI": "财经", "降息": "财经", "加息": "财经",
    "银行": "财经", "保险": "财经", "房地产": "财经", "金融": "财经",
    "币圈": "财经", "比特币": "财经", "以太坊": "财经", "区块链": "财经",
    "加密货币": "财经", "创业": "财经", "独角兽": "财经", "VC": "财经", "PE": "财经",
    "公司": "财经", "企业": "财经", "人事": "财经", "金融人事": "财经",
    # 汽车
    "汽车": "汽车", "汽车资讯": "汽车", "自动驾驶": "汽车", "智能驾驶": "汽车",
    "新能源": "汽车", "电动车": "汽车", "电池": "汽车", "充电": "汽车", "充电桩": "汽车",
    "传统车企": "汽车", "新势力": "汽车", "小米SU7": "汽车", "小米su7": "汽车",
    # 其他兜底
    "教育政策": "其他", "综合新闻": "其他", "其他": "其他",
}

# 类目-默认映射(Day 5 用于 seed source_config 时填 l1)
SOURCE_L1_DEFAULT = {
    "36kr": "科技", "leiphone": "AI", "ifanr": "科技",
    "infoq": "科技", "sspai": "科技", "ithome": "科技",
    "qbitai": "AI",
    "wallstreetcn": "财经", "cls": "财经",
    "sina_sports_soccer": "体育",
    "bilibili": "娱乐", "douban": "娱乐",
    "zhihu_hot": "科技",
    "weibo:1887344341": "财经", "weibo:1643971635": "其他",
    "weibo:hot": "其他",
    "x:sama": "AI",
}

# 向后兼容别名
SOURCE_L1_MAP = SOURCE_L1_DEFAULT
