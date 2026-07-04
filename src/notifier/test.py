"""fastInfo · notifier 测试

一键测试渠道是否通,无论用户配置是不是完整。
返回 {channel: {ok: bool, message: str}}。
"""
from __future__ import annotations
import os
from typing import Optional

from . import get, available_channels


def _test_subject() -> str:
    return "[fastInfo] 推送通道测试"


def _test_content() -> str:
    return "🎉 这是 fastInfo 推送通道测试消息。\n\n如果你收到了这条消息,说明该通道配置成功。\n\n可以推送的真实内容会在订阅触发时到达。"


def test_channel(name: str, user: Optional[dict] = None, item: Optional[dict] = None) -> dict:
    """测试一个渠道,返回 {ok, message}"""
    user = user or {
        "username": "test_user",
        "email": os.environ.get("TEST_EMAIL", ""),
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.qq.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "465")),
        "smtp_user": os.environ.get("SMTP_USER", ""),
        "smtp_pass": os.environ.get("SMTP_PASS", ""),
        "feishu_webhook": os.environ.get("TEST_FEISHU_WEBHOOK", ""),
        "wechat_webhook": os.environ.get("TEST_WECHAT_WEBHOOK", ""),
        "webhook_url": os.environ.get("TEST_WEBHOOK_URL", ""),
    }
    item = item or {
        "title": "fastInfo 测试推送",
        "source": "test",
        "url": "https://fastinfo.local/test",
        "summary": "测试推送内容",
    }
    n = get(name)
    if n is None:
        return {"ok": False, "message": f"未知渠道 '{name}',可选:{available_channels()}"}

    try:
        ok = n.send(user, _test_subject(), _test_content(), [item])
        return {"ok": ok, "message": "发送成功" if ok else "发送失败(看 stdout)"}
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {str(e)[:200]}"}


def test_all(user: Optional[dict] = None) -> dict:
    """测试所有渠道"""
    out = {}
    for ch in available_channels():
        out[ch] = test_channel(ch, user=user)
    return out
