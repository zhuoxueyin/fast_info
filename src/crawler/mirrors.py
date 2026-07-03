"""fastInfo · 多镜像 fallback 注册表 (Day 5)

很多数据源 host 不稳 / 拉黑。加 mirror list,按顺序试,第一个 200 即用。
"""
from __future__ import annotations
from typing import Iterable

# 虎嗅:RSS 可能 timeout,加 RSSHub 镜像 + 反代
HUXIU_RSS = [
    "https://www.huxiu.com/rss/0.xml",
    # RSSHub 公共镜像可加;此处仅示例
    "https://rsshub.app/huxiu",
]

# X / Twitter via nitter 多 mirror
NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://xcancel.com",
]

# 微博 cookie/Referer 列表(若需要)
WEIBO_REFERERS = [
    "https://m.weibo.cn/",
    "https://weibo.com/",
]


def ordered_unique(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_huxiu_urls() -> list[str]:
    return ordered_unique(HUXIU_RSS)


def get_nitter_mirrors() -> list[str]:
    return ordered_unique(NITTER_MIRRORS)
