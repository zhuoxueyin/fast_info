"""fastInfo · 一级 / 二级分类 (Day 4)

L1: 科技 / AI / 体育 / 娱乐 / 财经 / 汽车 / 其他  (顶部导航维度)
L2: 细分类,例 科技 → 互联网 / 硬件 / 数码评测 ...
"""
from __future__ import annotations
from typing import Optional
from crawler.sources import CATEGORY_L1, CATEGORY_L2, CATEGORY_LEGACY_MAP


# 当 category 字段无法归一时，用标题+摘要做最后一道兜底
_TEXT_L1_KEYWORDS = {
    "AI": [
        "人工智能", "大模型", "aigc", "生成式", "chatgpt", "gpt", "llm", "claude",
        "gemini", "deepseek", "多模态", "智能体", "agent", "nlp", "计算机视觉",
        "具身智能", "ai芯片",
    ],
    "科技": [
        "互联网", "半导体", "芯片", "存储", "cpu", "gpu", "消费电子", "通信", "5g",
        "物联网", "云计算", "saas", "开源", "软件", "网络安全", "量子计算",
        "生物科技", "航空", "航天", "无人机", "vr", "ar", "元宇宙", "3d打印",
        "制造", "工业互联网", "硬件", "数码", "手机", "笔记本",
    ],
    "体育": [
        "足球", "篮球", "电竞", "lol", "dota", "王者", "csgo", "nba", "cba",
        "世界杯", "欧冠", "奥运会", "f1", "马拉松", "网球", "乒乓球", "羽毛球",
    ],
    "娱乐": [
        "电影", "电视剧", "票房", "导演", "演员", "音乐", "歌手", "专辑", "演唱会",
        "综艺", "动漫", "动画", "漫画", "二次元", "游戏", "直播", "短视频", "美食",
        "旅游", "时尚", "艺术", "文化",
    ],
    "财经": [
        "股市", "股票", "ipo", "上市", "融资", "投资", "a股", "港股", "美股",
        "中概股", "基金", "债券", "宏观", "央行", "gdp", "cpi", "降息", "加息",
        "银行", "保险", "房地产", "比特币", "以太坊", "区块链", "加密货币", "币圈",
        "创业", "独角兽", "vc", "pe", "财报", "并购",
    ],
    "汽车": [
        "汽车", "新能源车", "电动车", "自动驾驶", "智能驾驶", "小米su7", "su7", "比亚迪",
        "特斯拉", "蔚来", "小鹏", "理想", "极氪", "华为智选", "宁德时代", "电池",
        "充电", "充电桩", "传统车企", "新势力",
    ],
}


def _l1_from_text(text: Optional[str]) -> str:
    """标题+摘要关键词兜底，只在 category 无法归一时使用"""
    if not text:
        return "其他"
    t = text.lower()
    scores: dict[str, int] = {l1: 0 for l1 in CATEGORY_L1}
    for l1, kws in _TEXT_L1_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                scores[l1] += 1
    if not any(scores.values()):
        return "其他"
    # AI/科技容易混淆：AI 是科技的子集，命中 AI 关键词时优先 AI
    if scores["AI"] > 0 and scores["科技"] > 0:
        return "AI"
    # 财经/科技容易混淆：若同时命中科技且命中财经，优先科技（科技产业新闻更常带融资）
    if scores["科技"] > 0 and scores["财经"] > 0:
        return "科技"
    # 汽车/财经容易混淆："新车上市"常被误判为 IPO，优先汽车
    if scores["汽车"] > 0 and scores["财经"] > 0:
        return "汽车"
    return max(scores, key=lambda k: scores[k])


def normalize_l1(category: Optional[str], text: Optional[str] = None) -> str:
    """把任意 category 字符串归到 7 个 L1 之一(优先查 legacy map,再模糊匹配,最后文本兜底)"""
    if not category:
        result = "其他"
    else:
        cat = category.strip()
        # 处理带斜杠的复合分类，如"科技/AI"、"AI/大模型"等
        if "/" in cat:
            parts = [p.strip() for p in cat.split("/") if p.strip()]
            for p in parts:
                r = normalize_l1(p, text=None)
                if r != "其他":
                    return r
        if cat in CATEGORY_L1:
            result = cat
        elif cat in CATEGORY_LEGACY_MAP:
            result = CATEGORY_LEGACY_MAP[cat]
        else:
            # 模糊:L2 → L1
            result = "其他"
            for l1, l2_list in CATEGORY_L2.items():
                if cat in l2_list:
                    result = l1
                    break
                for l2 in l2_list:
                    if l2 and (l2 in cat or cat in l2):
                        result = l1
                        break
                if result != "其他":
                    break
    if result == "其他" and text:
        result = _l1_from_text(text)
    return result


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