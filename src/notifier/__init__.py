"""fastInfo · 多渠道推送 (Day 4)

支持 4 种渠道,订阅可多选:
  - email  : SMTP 邮件(QQ邮箱/126/Gmail)
  - feishu : 飞书自定义机器人 webhook
  - wechat : 企业微信机器人 webhook
  - webhook: 通用 webhook (POST JSON)

设计:
  Notifier.register("email", EmailNotifier())
  Notifier.send("email", user, items)
"""
from __future__ import annotations
import asyncio
import json
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from abc import ABC, abstractmethod
from typing import Iterable

import httpx

# Day 10 fix:推送历史 GBK 死循环 — notifier 里所有 print 改 logging,
# 而且 fallback 用 ASCII tag ([OK]/[FAIL]/[!]) 避开 Windows GBK 控制台炸 ✗/✓。
# 这样:
#  - 真实异常不被控制台编码掩盖(以前 _post_webhook try 块里 print 抛 UnicodeEncodeError,
#    让 send_all 的 except 把整个渠道当成失败, push_history 看到的不是真实 httpx 错)
#  - scheduler 子进程(默认 GBK stdout) 也不会因为 ✗ 自爆
_log = logging.getLogger("fastinfo.notifier")


class Notifier(ABC):
    """推送渠道抽象基类"""
    name: str = ""

    def send(
        self,
        user: dict,
        subject: str,
        content_html: str,
        items: list[dict],
        *,
        body_md: str | None = None,
        body_html: str | None = None,
        card: dict | None = None,
    ) -> bool:
        """返回 True = 成功,False = 失败(不会拋异常)
        body_md / body_html / card 都是可选。具体渠道选抸需要的。
        覆写时请传 **kwargs,默认 base 类只用 content_html 作为后备。
        """
        ...


# ============================================================
# Email
# ============================================================
class EmailNotifier(Notifier):
    name = "email"

    def send(
        self, user, subject, content_html, items, *, body_md=None, body_html=None, card=None,
    ) -> dict:
        addr = user.get("email")
        if not addr:
            _log.info("[email] 用户 %s 没邮箱,跳过", user.get("username"))
            return {"ok": False, "http_status": None, "error": "no recipient email"}
        smtp_host = os.environ.get("SMTP_HOST", "smtp.qq.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        if not smtp_user or not smtp_pass:
            _log.info("[email] SMTP_USER / SMTP_PASS 未配置,跳过")
            return {"ok": False, "http_status": None, "error": "smtp not configured"}
        try:
            msg = MIMEMultipart()
            msg["From"] = formataddr(["fastInfo", smtp_user])
            msg["To"] = addr
            msg["Subject"] = subject
            email_body = body_html or content_html
            msg.attach(MIMEText(email_body, "html", "utf-8"))
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as s:
                s.login(smtp_user, smtp_pass)
                s.sendmail(smtp_user, [addr], msg.as_string())
            _log.info("[email] -> %s [OK]", addr)
            return {"ok": True, "http_status": None, "error": None}
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:120]}"
            _log.warning("[email] [FAIL] %s", msg)
            return {"ok": False, "http_status": None, "error": msg}


# ============================================================
# 飞书机器人(支持多群)
# ============================================================
def get_feishu_webhooks(user: dict) -> list[dict]:
    """统一读取用户配置的多飞书群机器人,兼容旧版单字段 feishu_webhook。

    返回: [{"name": "群名", "webhook": "url"}, ...]
    """
    hooks = user.get("feishu_webhooks")
    if isinstance(hooks, list) and hooks:
        return [
            {"name": h.get("name") or f"群{i+1}", "webhook": h["webhook"]}
            for i, h in enumerate(hooks)
            if isinstance(h, dict) and h.get("webhook")
        ]
    old = user.get("feishu_webhook")
    if old:
        return [{"name": "默认群", "webhook": old}]
    return []


class FeishuNotifier(Notifier):
    name = "feishu"

    def send(
        self, user, subject, content_html, items, *, body_md=None, body_html=None, card=None,
    ) -> dict:
        webhooks = get_feishu_webhooks(user)
        if not webhooks:
            return {"ok": False, "http_status": None, "error": "no feishu_webhook"}
        if card and "card" in card:
            payload = {"msg_type": "interactive", "card": card["card"]}
        elif card:
            payload = {"msg_type": "interactive", "card": card}
        else:
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {"title": {"tag": "plain_text", "content": subject}, "template": "green"},
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": (body_md or content_html)[:2000]}}
                    ],
                },
            }

        targets: list[dict] = []
        for hook in webhooks:
            res = _post_webhook(hook["webhook"], payload, "feishu")
            targets.append({"name": hook["name"], **res})

        # 汇总:任一成功即算渠道成功;http_status 取第一个成功的状态码
        ok = any(t["ok"] for t in targets)
        http_status = next((t["http_status"] for t in targets if t["ok"]), None)
        if http_status is None and targets:
            http_status = targets[-1].get("http_status")
        errors = [f"{t['name']}: {t['error']}" for t in targets if not t["ok"] and t.get("error")]
        error = "; ".join(errors) if errors else (None if ok else "all failed")
        return {"ok": ok, "http_status": http_status, "error": error, "targets": targets}


# ============================================================
# 企业微信机器人
# ============================================================
class WechatWorkNotifier(Notifier):
    name = "wechat"

    def send(
        self, user, subject, content_html, items, *, body_md=None, body_html=None, card=None,
    ) -> dict:
        webhook = user.get("wechat_webhook")
        if not webhook:
            return {"ok": False, "http_status": None, "error": "no wechat_webhook"}
        body = body_md or content_html
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": f"## {subject}\n{body[:4000]}"},
        }
        return _post_webhook(webhook, payload, "wechat")


# ============================================================
# 通用 Webhook
# ============================================================
class WebhookNotifier(Notifier):
    name = "webhook"

    def send(
        self, user, subject, content_html, items, *, body_md=None, body_html=None, card=None,
    ) -> dict:
        url = user.get("webhook_url")
        if not url:
            return {"ok": False, "http_status": None, "error": "no webhook_url"}
        # Day 7:优先 body_html(订阅服务端的真正 HTML),其次 content_html 兜底
        payload = {
            "subject": subject,
            "content_html": body_html or content_html or "",
            "content_md": body_md or "",
            "items": items,
            "username": user.get("username"),
        }
        return _post_webhook(url, payload, "webhook")


def _post_webhook(url: str, payload: dict, tag: str) -> dict:
    """Day 9:返回结构化结果 {ok, http_status, error} 给 push_history 用。

    Day 10 fix:返回路径绝不抛异常,所有日志改 logging + ASCII tag。
    之前 try 块里 print 含 ✗ → Windows GBK 控制台抛 UnicodeEncodeError
    → 被 send_all 的 except 兜成「推送失败」,掩盖真实的 httpx 错。
    """
    try:
        r = httpx.post(url, json=payload, timeout=10)
        ok = 200 <= r.status_code < 300
        if ok:
            _log.info("[%s] %s... [OK] status=%s", tag, url[:60], r.status_code)
            return {"ok": True, "http_status": r.status_code, "error": None}
        _log.warning("[%s] %s... [FAIL] status=%s", tag, url[:60], r.status_code)
        return {"ok": False, "http_status": r.status_code, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:80]}"
        _log.warning("[%s] [FAIL] %s", tag, msg)
        return {"ok": False, "http_status": None, "error": msg}



# ============================================================
# 注册表
# ============================================================
_REGISTRY: dict[str, Notifier] = {
    "email": EmailNotifier(),
    "feishu": FeishuNotifier(),
    "wechat": WechatWorkNotifier(),
    "webhook": WebhookNotifier(),
}


def get(name: str) -> Notifier | None:
    return _REGISTRY.get(name)


def available_channels() -> list[str]:
    return list(_REGISTRY.keys())


def send_all(
    user: dict,
    channels: list[str],
    subject: str,
    content_html: str,
    items: list[dict],
    *,
    body_md: str | None = None,
    body_html: str | None = None,
    card: dict | None = None,
) -> dict[str, dict]:
    """Day 9 改造:返回每个渠道的结构化结果 {ok, http_status, error}。

    旧版返回 dict[str, bool](True/False),新版本兼容调用方 —— 列出「成功」/「失败」
    两套渠道数组,供 push_history 落库时使用。
    """
    out: dict[str, dict] = {}
    for ch in channels:
        n = get(ch)
        if n is None:
            out[ch] = {"ok": False, "http_status": None, "error": f"unknown channel {ch!r}"}
            continue
        try:
            result = n.send(
                user, subject, content_html, items,
                body_md=body_md, body_html=body_html, card=card,
            )
            # Day 10 fix: 各 notifier.send() 已统一返回 dict(Email/Feishu/Wechat/Webhook),
            # 直接透传,别再 if result: 包一下 — 之前那段会把真实的 http_status 丢掉 (None)。
            if isinstance(result, dict):
                out[ch] = result
            else:
                # 兼容旧 Notifier.send() 返 bool 的实现
                out[ch] = {
                    "ok": bool(result),
                    "http_status": None,
                    "error": None if result else "send() returned False",
                }
        except Exception as e:
            _log.warning("[notifier] %s err: %s: %s", ch, type(e).__name__, str(e)[:120])
            out[ch] = {"ok": False, "http_status": None,
                       "error": f"{type(e).__name__}: {str(e)[:120]}"}
    return out


# ============================================================
# Feishu DM (个人单聊) — Day 7 v0.4.0 已在上方定义
# ============================================================