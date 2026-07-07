"""
fastInfo · 一级分类归一化回归测试
=================================
覆盖: normalize_l1 / _l1_from_text 的映射、兜底、优先级规则
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from taxonomy import normalize_l1, _l1_from_text


class TestNormalizeL1:
    """normalize_l1 主路径"""

    def test_direct_l1(self):
        assert normalize_l1("科技") == "科技"
        assert normalize_l1("AI") == "AI"
        assert normalize_l1("其他") == "其他"

    def test_legacy_map(self):
        assert normalize_l1("人工智能") == "AI"
        assert normalize_l1("大模型") == "AI"
        assert normalize_l1("互联网") == "科技"
        assert normalize_l1("股市") == "财经"
        assert normalize_l1("足球") == "体育"

    def test_l2_map(self):
        assert normalize_l1("互联网") == "科技"
        assert normalize_l1("大模型") == "AI"
        assert normalize_l1("新能源") == "汽车"
        assert normalize_l1("影视") == "娱乐"

    def test_composite_category(self):
        assert normalize_l1("科技/AI") == "科技"
        assert normalize_l1("AI/大模型") == "AI"
        assert normalize_l1("财经/融资") == "财经"

    def test_unknown_category_text_fallback(self):
        # 空 category 但文本明确
        assert normalize_l1("", "OpenAI 发布 GPT-5 大模型") == "AI"
        assert normalize_l1("", "英伟达发布 H200 AI芯片") == "AI"
        assert normalize_l1("", "美联储宣布降息") == "财经"
        assert normalize_l1("", "小米 SU7 Ultra 上市") == "汽车"

    def test_generic_news_category_text_fallback(self):
        # LLM 常输出的"资讯/咨询/综合新闻"等泛 category,必须靠文本兜底
        assert normalize_l1("资讯", "OpenAI 发布 GPT-5 大模型") == "AI"
        assert normalize_l1("咨询", "OpenAI 发布 GPT-5 大模型") == "AI"
        assert normalize_l1("综合新闻", "美联储宣布降息") == "财经"
        assert normalize_l1("其他", "DeepSeek 发布多模态大模型") == "AI"

    def test_no_match_defaults_to_other(self):
        assert normalize_l1("完全不相关") == "其他"
        assert normalize_l1("", "") == "其他"


class TestL1FromText:
    """标题+摘要关键词兜底与优先级"""

    def test_ai_preferred_over_tech(self):
        # "AI芯片"同时命中 AI 和科技(芯片),AI 更具体应优先
        assert _l1_from_text("英伟达发布 H200 AI芯片") == "AI"
        assert _l1_from_text("GPT-5 大模型与半导体产业") == "AI"

    def test_tech_preferred_over_finance(self):
        # 科技/AI 产业新闻带融资,优先科技/AI
        assert _l1_from_text("某AI芯片公司完成B轮融资") == "AI"
        assert _l1_from_text("某半导体企业获得投资") == "科技"

    def test_finance_when_pure_finance(self):
        assert _l1_from_text("美联储降息 25 个基点") == "财经"
        assert _l1_from_text("A股 今日大涨") == "财经"

    def test_auto(self):
        assert _l1_from_text("小米 SU7 Ultra 上市") == "汽车"
        assert _l1_from_text("比亚迪发布新电池技术") == "汽车"

    def test_sports(self):
        assert _l1_from_text("世界杯决赛进球") == "体育"
        assert _l1_from_text("NBA 季后赛开打") == "体育"

    def test_entertainment(self):
        assert _l1_from_text("新电影票房破纪录") == "娱乐"
        assert _l1_from_text("演唱会门票秒空") == "娱乐"
