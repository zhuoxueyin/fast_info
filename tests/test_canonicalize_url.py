"""URL 规范化 + title_hash 去重回归。

覆盖 2026-07-09 事故:
  头条热搜同一 topic 因 log_pb/impr_id 不同被当成多条新 item,
  导致「2026世界杯资讯」推送里「新华社：国足成绩再不好也不能造谣」重复出现。
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.rss_collector import canonicalize_url, _make_id, _title_hash


class TestCanonicalizeUrl:
    def test_toutiao_trending_strips_tracking(self):
        u1 = (
            "https://www.toutiao.com/trending/7660302074218876425/"
            "?category_name=topic_innerflow&event_type=hot_board"
            "&log_pb=%7B%22hot_board_impr_id%22%3A%22AAA%22%7D"
            "&rank=&style_id=40132&topic_id=7660302074218876425"
        )
        u2 = (
            "https://www.toutiao.com/trending/7660302074218876425/"
            "?category_name=topic_innerflow&event_type=hot_board"
            "&log_pb=%7B%22hot_board_impr_id%22%3A%22BBB%22%7D"
            "&rank=&style_id=40132&topic_id=7660302074218876425"
        )
        c1 = canonicalize_url(u1)
        c2 = canonicalize_url(u2)
        assert c1 == c2
        assert c1 == "https://www.toutiao.com/trending/7660302074218876425"
        assert "log_pb" not in c1
        assert _make_id("weibo:hot", u1) == _make_id("weibo:hot", u2)

    def test_toutiao_article_stable(self):
        u = "https://www.toutiao.com/article/7660349938194252303?utm_source=x&foo=1"
        assert canonicalize_url(u) == "https://www.toutiao.com/article/7660349938194252303"

    def test_zhihu_question_stable(self):
        u = "https://www.zhihu.com/question/2057469688892936472?utm_source=wechat"
        assert canonicalize_url(u) == "https://www.zhihu.com/question/2057469688892936472"

    def test_empty_url(self):
        assert canonicalize_url("") == ""
        assert canonicalize_url(None) == ""  # type: ignore[arg-type]

    def test_generic_strips_utm(self):
        u = "https://36kr.com/p/123?utm_source=rss&utm_medium=feed&id=1"
        c = canonicalize_url(u)
        assert "utm_source" not in c
        assert "utm_medium" not in c
        assert "id=1" in c


class TestTitleHashDedup:
    def test_same_story_same_hash(self):
        # LLM 改写前后 title_hash 应基于原始 API 标题计算;
        # 这里验证规范化:标点/空格不影响
        a = _title_hash("新华社：国足成绩再不好也不能造谣")
        b = _title_hash("新华社: 国足成绩再不好也不能造谣")
        assert a == b
        assert len(a) == 16
