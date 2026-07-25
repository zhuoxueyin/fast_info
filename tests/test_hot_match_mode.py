"""match_mode=hot 单元测试:NL 判定 + 元关键词兜底。"""
from __future__ import annotations

from subscription import (
    should_use_hot_mode,
    apply_hot_mode_defaults,
    _keywords_are_meta_only,
    _normalize_relevance,
)


def test_meta_keywords_only():
    assert _keywords_are_meta_only(["热点新闻", "今日要闻", "突发事件"])
    assert not _keywords_are_meta_only(["OpenAI", "热点"])
    assert not _keywords_are_meta_only([])


def test_should_use_hot_mode_nl():
    assert should_use_hot_mode("每天10点汇总热门新闻", {"keywords": ["热点新闻"]})
    assert should_use_hot_mode("每日热点", {})
    assert should_use_hot_mode("今日热搜推送", {})
    # 主题订阅不走 hot
    assert not should_use_hot_mode("跟踪 OpenAI", {"keywords": ["OpenAI"], "track_entity": "OpenAI"})
    assert not should_use_hot_mode("AI前沿追踪", {"keywords": ["AI", "大模型"], "categories_l1": ["AI"]})


def test_apply_hot_mode_defaults_daily_10am():
    p = {
        "keywords": ["热点新闻", "今日要闻"],
        "categories_l1": ["其他"],
        "interval_min": 120,
        "cron_expr": "* * * * *",
    }
    apply_hot_mode_defaults(p, "每天10点汇总热门新闻")
    assert p["match_mode"] == "hot"
    assert p["keywords"] == []
    assert p["categories_l1"] == []
    assert p["interval_min"] == 0
    assert p["lookback_hours"] == 24
    # 北京 10:00 → UTC 02:00
    assert p["cron_expr"] == "0 2 * * *"


def test_normalize_relevance():
    assert _normalize_relevance(0.85) == 8.5
    assert _normalize_relevance(8.5) == 8.5
    assert _normalize_relevance(85) == 8.5
    assert _normalize_relevance(None) == 5.0
