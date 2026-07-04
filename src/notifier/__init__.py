"""fastInfo · 多渠道推送 (Day 4)

支持 4 种渠道,订阅可多选:
  - email  : SMTP 邮件(QQ邮箱/126/Gmail)
  - feishu : 飞书自定义机器人 webhook
  - wechat : 企业微信机器人 webhook
  - webhook: 通用 webhook (POST JSON)
  - inbox  : 默认站内收件箱

设计:
  Notifier.register("email", EmailNotifier())
  Notifier.send("email", user, items)
"""
from __future__ import annotations
import asyncio
import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from abc import ABC, abstractmethod
from typing import Iterable

import httpx


class Notifier(ABC):
    """推送渠道抽象基类"""
    name: str = ""

    @abstractmethod
    def send(self, user: dict, subject: str, content_html: str, items: list[dict]) -> bool:
        """返回 True = 成功,False = 失败(不会抛异常)"""
        ...


# ============================================================
# Email
# ============================================================
class EmailNotifier(Notifier):
    name = "email"

    def send(self, user, subject, content_html, items):
        addr = user.get("email")
        if not addr:
            print(f"  [email] 用户 {user.get('username')} 没邮箱,跳过")
            return False
        smtp_host = os.environ.get("SMTP_HOST", "smtp.qq.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        if not smtp_user or not smtp_pass:
            print("  [email] SMTP_USER / SMTP_PASS 未配置,跳过")
            return False
        try:
            msg = MIMEMultipart()
            msg["From"] = formataddr(["fastInfo", smtp_user])
            msg["To"] = addr
            msg["Subject"] = subject
            msg.attach(MIMEText(content_html, "html", "utf-8"))
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as s:
                s.login(smtp_user, smtp_pass)
                s.sendmail(smtp_user, [addr], msg.as_string())
            print(f"  [email] → {addr} ✓")
            return True
        except Exception as e:
            print(f"  [email] ✗ {type(e).__name__}: {str(e)[:80]}")
            return False


# ============================================================
# 飞书机器人
# ============================================================
class FeishuNotifier(Notifier):
    name = "feishu"

    def send(self, user, subject, content_html, items):
        webhook = user.get("feishu_webhook")
        if not webhook:
            return False
        # 富文本卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": subject}, "template": "green"},
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content_html[:2000]}}
                ],
            },
        }
        return _post_webhook(webhook, payload, "feishu")


# ============================================================
# 企业微信机器人
# ============================================================
class WechatWorkNotifier(Notifier):
    name = "wechat"

    def send(self, user, subject, content_html, items):
        webhook = user.get("wechat_webhook")
        if not webhook:
            return False
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": f"## {subject}\n{content_html[:2000]}"},
        }
        return _post_webhook(webhook, payload, "wechat")


# ============================================================
# 通用 Webhook
# ============================================================
class WebhookNotifier(Notifier):
    name = "webhook"

    def send(self, user, subject, content_html, items):
        url = user.get("webhook_url")
        if not url:
            return False
        payload = {
            "subject": subject,
            "content_html": content_html,
            "items": items,
            "username": user.get("username"),
        }
        return _post_webhook(url, payload, "webhook")


def _post_webhook(url: str, payload: dict, tag: str) -> bool:
    try:
        r = httpx.post(url, json=payload, timeout=10)
        ok = 200 <= r.status_code < 300
        if ok:
            print(f"  [{tag}] {url[:60]}... ✓")
        else:
            print(f"  [{tag}] {url[:60]}... ✗ {r.status_code}")
        return ok
    except Exception as e:
        print(f"  [{tag}] ✗ {type(e).__name__}: {str(e)[:80]}")
        return False


# ============================================================
# Feishu DM (个人单聊) — Day 7 v0.4.0 加(需在前段)
# ============================================================
import time as _time

class FeishuDMNotifier(Notifier):
    """飞书应用→个人单聊。需 LARK_APP_ID + LARK_APP_SECRET env。
    调 im/v1/messages,需要应用有 im:message 权限。
    """
    name = "feishu_dm"

    _TOKEN_CACHE = {"token": "", "exp": 0.0}

    def _get_token(self) -> str:
        app_id = os.environ.get("LARK_APP_ID", "")
        app_secret = os.environ.get("LARK_APP_SECRET", "")
        if not app_id or not app_secret:
            return ""
        now = _time.time()
        if self._TOKEN_CACHE["token"] and self._TOKEN_CACHE["exp"] > now:
            return self._TOKEN_CACHE["token"]
        try:
            base = os.environ.get("FEISHU_BASE_URL", "https://open.feishu.cn")
            r = httpx.post(
                f"{base}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=10,
            )
            data = r.json()
            if data.get("code") != 0:
                return ""
            tok = data.get("tenant_access_token", "")
            self._TOKEN_CACHE["token"] = tok
            self._TOKEN_CACHE["exp"] = now + 20 * 60
            return tok
        except Exception as e:
            print(f"  [feishu_dm] token err: {type(e).__name__}: {e}")
            return ""

    def send(self, user, subject, content_html, items):
        open_id = user.get("feishu_open_id") or user.get("open_id") or ""
        if not open_id:
            print("  [feishu_dm] 未配 feishu_open_id,跳过")
            return False
        token = self._get_token()
        if not token:
            print("  [feishu_dm] LARK_APP_ID/SECRET 未设或 token 失败")
            return False
        card = {
            "header": {"title": {"tag": "plain_text", "content": subject}, "template": "green"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content_html[:1800]}}],
        }
        try:
            base = os.environ.get("FEISHU_BASE_URL", "https://open.feishu.cn")
            r = httpx.post(
                f"{base}/open-apis/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
                json={"receive_id": open_id, "msg_type": "interactive", "card": card},
                timeout=10,
            )
            data = r.json()
            if data.get("code") == 0:
                print(f"  [feishu_dm] → {open_id[:8]}... ✓")
                return True
            print(f"  [feishu_dm] ✗ code={data.get('code')} msg={data.get('msg')}")
            return False
        except Exception as e:
            print(f"  [feishu_dm] ✗ {type(e).__name__}: {str(e)[:120]}")
            return False


# ============================================================
# 注册表
# ============================================================
_REGISTRY: dict[str, Notifier] = {
    "email": EmailNotifier(),
    "feishu": FeishuNotifier(),
    "feishu_dm": FeishuDMNotifier(),   # Day 7 v0.4.0 新增
    "wechat": WechatWorkNotifier(),
    "webhook": WebhookNotifier(),
}


def get(name: str) -> Notifier | None:
    return _REGISTRY.get(name)


def available_channels() -> list[str]:
    return list(_REGISTRY.keys())


def send_all(user: dict, channels: list[str], subject: str, content_html: str, items: list[dict]) -> dict[str, bool]:
    """并发往多个渠道推，返回每个渠道成功与否"""
    out = {}
    for ch in channels:
        n = get(ch)
        if n is None:
            out[ch] = False
            continue
        out[ch] = n.send(user, subject, content_html, items)
    return out


# ============================================================
# Feishu DM (个人单聊) — Day 7 v0.4.0 已在上方定义
# ============================================================