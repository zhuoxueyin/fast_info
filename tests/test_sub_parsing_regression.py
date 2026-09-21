"""
fastInfo · 订阅周期 / 关键词识别回归测试
=======================================
针对用户报告的两个 bug:
  Bug A:「每隔 300 分钟关注 AI」被识别成「每天 9 点」(interval 被吞)
  Bug B:有实体关键词的订阅被识别为热点,keywords 被清空

修复:
  - apply_hot_mode_defaults:仅当 L1 显式 == ["其他"] 时清 categories;
    「每日/每天」宽匹配改成「每日/每天 + 热点/热搜/要闻」严格匹配。
    「每天 N 点」cron 兜底保持原行为(用户显式说时间才生效)。
"""
import pytest

from subscription import (
    apply_hot_mode_defaults,
    should_use_hot_mode,
)


# ============================================================
# Bug A · 周期识别
# ============================================================

class TestIntervalPreservation:
    """「每隔 N 分钟」订阅不应被改成 cron 日更。"""

    def test_interval_300_preserved_when_no_hot_keyword(self):
        """主场景:「每隔 300 分钟关注 AI」—— interval 必须保留。"""
        parsed = {
            "interval_min": 300,
            "cron_expr": "* * * * *",
            "keywords": ["GPT", "Claude", "Gemini"],
            "match_mode": "keywords",
            "categories_l1": [],
        }
        nl = "每隔 300 分钟关注一下 AI 大模型的最新进展"
        result = apply_hot_mode_defaults(dict(parsed), nl)
        assert result["interval_min"] == 300, f"interval_min 被吞了:{result}"
        assert result["cron_expr"] == "* * * * *", f"cron 被改了:{result}"

    def test_interval_60_not_swallowed_by_daily_word(self):
        """「每天抓 60 分钟一次的财报」含糊场景 —— 不该硬吞 interval。"""
        parsed = {
            "interval_min": 60,
            "cron_expr": "* * * * *",
            "keywords": ["财报", "财报季"],
            "match_mode": "keywords",
            "categories_l1": [],
        }
        nl = "每60 分钟抓一次财报季的新闻"
        result = apply_hot_mode_defaults(dict(parsed), nl)
        assert result["interval_min"] == 60

    def test_daily_hot_summary_still_uses_cron(self):
        """回归保护:「每天9 点热点汇总」仍应被改成 cron 兜底。"""
        parsed = {
            "interval_min": 60,
            "cron_expr": "* * * * *",
            "keywords": ["热点", "热门"],
            "match_mode": "keywords",
            "categories_l1": [],
        }
        nl = "每天9 点给我推送今日热点汇总"
        result = apply_hot_mode_defaults(dict(parsed), nl)
        # 修复后:此场景仍被识别为「每日+热点」,cron 兜底
        assert result["interval_min"] == 0
        # 「每天 9 点」 → 北京 9 = UTC 1
        assert result["cron_expr"] == "0 1 * * *", f"cron={result['cron_expr']}"

    def test_daily_with_specific_hour_still_uses_cron(self):
        """「每天 10 点王力宏演唱会」 —— 走 cron(日期指定优先级 > interval)。"""
        parsed = {
            "interval_min": 60,
            "cron_expr": "* * * * *",
            "keywords": ["王力宏", "演唱会"],
            "match_mode": "keywords",
            "categories_l1": ["娱乐"],
        }
        nl = "每天10 点给我推送王力宏演唱会最新消息"
        result = apply_hot_mode_defaults(dict(parsed), nl)
        # 北京 10 = UTC 2
        assert result["interval_min"] == 0
        assert result["cron_expr"] == "0 2 * * *"


# ============================================================
# Bug B · 关键词保护(应该走 keywords mode 的场景)
# ============================================================

class TestKeywordsNotCleared:
    """有实体的订阅不应被强制走 hot mode 把 keywords 清空。"""

    def test_should_use_hot_mode_false_for_specific_entity(self):
        """有具体实体词的订阅,should_use_hot_mode 必须返 False。"""
        parsed = {
            "interval_min": 300,
            "keywords": ["GPT", "Claude", "Gemini"],
            "match_mode": "keywords",
        }
        nl = "每隔 300 分钟关注 GPT/Claude/Gemini 进展"
        assert should_use_hot_mode(nl, parsed) is False, (
            "实体订阅不该被识别为热点"
        )

    def test_should_use_hot_mode_false_for_track_entity(self):
        """有 track_entity(主题跟踪) → 不走热点榜。"""
        parsed = {
            "keywords": ["特朗普"],
            "track_entity": "特朗普",
            "match_mode": "keywords",
        }
        nl = "特朗普最新动态"
        assert should_use_hot_mode(nl, parsed) is False

    def test_should_use_hot_mode_true_for_daily_hot(self):
        """回归保护:「每天9 点热点汇总」仍应识别为热点。"""
        parsed = {"keywords": ["热点", "热门"]}
        nl = "每天9 点给我推送今日热点汇总"
        assert should_use_hot_mode(nl, parsed) is True

    def test_apply_hot_mode_does_not_touch_keywords_unless_called(self):
        """关键词保护(契约测试):
        apply_hot_mode_defaults 被调用时,keywords 一定被清(这是函数契约);
        实际链路 parse_nl_to_subscription 会先用 should_use_hot_mode 守门,
        只有 True 才调这个函数。所以有实体的订阅不该进这个函数。
        """
        # 这个 case 直接证明:如果 keywords 有实体,apply_hot_mode_defaults 不该被调用
        parsed = {
            "interval_min": 300,
            "keywords": ["GPT", "Claude", "Gemini"],
            "match_mode": "keywords",
        }
        nl = "每隔 300 分钟关注 GPT/Claude/Gemini 进展"
        # 守门函数必须返 False,才不会进 apply_hot_mode_defaults
        assert not should_use_hot_mode(nl, parsed), (
            "关键保护:有实体的订阅必须被守门函数挡住,不能进 hot mode"
        )


# ============================================================
# 端到端 (需要 MongoDB) - 标记 slow,默认跳过
# ============================================================

@pytest.mark.subs
class TestDailyHourExtraction:
    """「每天 N 点」的 cron 解析(Bug A 修复不破坏原行为)。"""

    @pytest.mark.parametrize("nl,expected_cst_hour", [
        ("每天9 点热点汇总", 9),
        ("每天10 点王力宏", 10),
        ("每天0 点凌晨要闻", 0),
        ("每天23 点深夜热点", 23),
    ])
    def test_daily_hour_parsed(self, nl, expected_cst_hour):
        """「每天 N 点」应被解析为北京 N 点 → UTC (N-8)%24。"""
        expected_utc = (expected_cst_hour - 8) % 24
        parsed = {"interval_min": 0, "keywords": [], "categories_l1": []}
        result = apply_hot_mode_defaults(dict(parsed), nl)
        # 必须有「每天 N 点」匹配,且 cron 反映正确的小时
        assert result["cron_expr"] == f"0 {expected_utc} * * *", (
            f"nl={nl} expected cron='0 {expected_utc} * * *' got '{result['cron_expr']}'"
        )