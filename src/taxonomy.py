"""fastInfo · 一级 / 二级分类 (Day 4)

L1: 科技 / AI / 体育 / 娱乐 / 财经 / 汽车 / 其他  (顶部导航维度)
L2: 细分类,例 科技 → 互联网 / 硬件 / 数码评测 ...
"""
from __future__ import annotations
from typing import Optional
from crawler.sources import CATEGORY_L1, CATEGORY_L2, CATEGORY_LEGACY_MAP


def normalize_l1(category: Optional[str]) -> str:
    """把任意 category 字符串归到 7 个 L1 之一(优先查 legacy map,再模糊匹配)"""
    if not category:
        return "其他"
    cat = category.strip()
    # 处理带斜杠的复合分类，如"科技/AI"、"AI/大模型"等
    if "/" in cat:
        parts = [p.strip() for p in cat.split("/") if p.strip()]
        for p in parts:
            result = normalize_l1(p)
            if result != "其他":
                return result
    if cat in CATEGORY_L1:
        return cat
    if cat in CATEGORY_LEGACY_MAP:
        return CATEGORY_LEGACY_MAP[cat]
    # 模糊:L2 → L1
    for l1, l2_list in CATEGORY_L2.items():
        if cat in l2_list:
            return l1
        for l2 in l2_list:
            if l2 and (l2 in cat or cat in l2):
                return l1
    # 关键词 fallback
    keys = {
        "AI": ["ai", "gpt", "llm", "大模型", "人工智能", "机器人", "agent"],
        "科技": ["科技", "互联网", "数码", "硬件", "芯片", "半导体", "it", "tech"],
        "体育": ["体育", "足球", "篮球", "电竞", "nba", "cba", "c罗", "梅西"],
        "娱乐": ["娱乐", "影视", "音乐", "明星", "综艺", "动漫"],
        "财经": ["财经", "股市", "股票", "融资", "创业", "币", "宏观", "美股", "港股", "a股"],
        "汽车": ["汽车", "新能源", "自动驾驶", "小鹏", "比亚迪", "特斯拉", "蔚来"],
    }
    cl = cat.lower()
    for l1, kws in keys.items():
        for kw in kws:
            if kw in cl:
                return l1
    return "其他"


def suggest_l2(l1: str, content: str = "") -> str:
    """根据 L1 + 内容文本建议一个 L2(简单关键词匹配)"""
    rules = {
        "AI": [("大模型", ["gpt", "llm", "大模型", "chatgpt", "claude", "gemini", "deepseek"]),
               ("AI芯片", ["gpu", "芯片", "nvidia", "h100", "h200", "tpu"]),
               ("AI应用", ["agent", "应用", "产品", "插件"]),
               ("AI框架", ["pytorch", "tensorflow", "huggingface", "框架", "langchain"]),
               ("机器人", ["机器人", "robot", "humanoid"])],
        "科技": [("互联网", ["互联网", "app", "app store", "google", "facebook", "微信", "微博", "小红书"]),
                 ("硬件", ["硬件", "手机", "电脑", "笔记本", "cpu", "intel", "amd"]),
                 ("数码评测", ["评测", "对比", "上手", "体验"]),
                 ("科技融资", ["融资", "ipo", "上市", "投资", "a轮", "b轮"]),
                 ("开源", ["开源", "github", "license", "apache", "mit"])],
        "体育": [("足球", ["足球", "世界杯", "c罗", "梅西", "欧冠", "西甲", "德甲"]),
                 ("篮球", ["篮球", "nba", "cba", "湖人", "勇士"]),
                 ("电竞", ["电竞", "lol", "dota", "王者", "csgo"])],
        "娱乐": [("影视", ["电影", "电视剧", "票房", "导演", "演员", "奥斯卡"]),
                 ("音乐", ["音乐", "歌手", "专辑", "演唱会", "billboard"]),
                 ("综艺", ["综艺", "选秀", "真人秀", "歌手"]),
                 ("动漫", ["动漫", "动画", "漫画", "二次元"])],
        "财经": [("宏观", ["宏观", "央行", "降息", "加息", "gdp", "cpi"]),
                 ("A股", ["a股", "上证", "深证", "创业板"]),
                 ("美股", ["美股", "纳斯达克", "标普", "道琼斯", "苹果", "特斯拉"]),
                 ("港股", ["港股", "恒生", "港交所"]),
                 ("币圈", ["比特币", "以太坊", "区块链", "加密", "btc", "eth"]),
                 ("创业", ["创业", "融资", "天使轮", "a轮", "b轮"])],
        "汽车": [("新能源", ["电动车", "ev", "电池", "续航", "充电"]),
                 ("自动驾驶", ["自动驾驶", "无人驾驶", "fsd", "智驾"]),
                 ("新势力", ["蔚来", "小鹏", "理想", "小米su7"]),
                 ("传统车企", ["奔驰", "宝马", "奥迪", "丰田", "大众", "比亚迪"])],
    }
    rules_l1 = rules.get(l1, [])
    content_l = (content or "").lower()
    for l2, kws in rules_l1:
        for kw in kws:
            if kw in content_l:
                return l2
    return CATEGORY_L2.get(l1, ["其他"])[0] if CATEGORY_L2.get(l1) else "其他"