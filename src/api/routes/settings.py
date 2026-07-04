"""用户推送配置 (Day 7 v0.4.0)

GET  /api/settings                       读用户推送配置(SMTP/feishu/wechat/webhook,密码脱敏)
PUT  /api/settings                       改配置
POST /api/notifier/test                  一键测试 5 个渠道(给前端 button 调用)
GET  /api/notifier/channels              列出 5 个渠道 + 是否需要哪些字段

SMTP 字段:smtp_host / smtp_port / smtp_user / smtp_pass / from_addr
Webhook 字段:feishu_webhook / wechat_webhook / webhook_url

存储在 users 集合,user_id 主键,可选。
"""
from __future__ import annotations
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_user
from storage.mongo_writer import get_db


router = APIRouter(tags=["settings"])

DEFAULT_DB = "fastinfo"

# 5 个渠道 + 各需要字段(给前端表单用)
CHANNEL_FIELDS = {
    "inbox":   [],
    "email":   ["email", "smtp_host", "smtp_port", "smtp_user", "smtp_pass"],
    "feishu":  ["feishu_webhook"],
    "wechat":  ["wechat_webhook"],
    "webhook": ["webhook_url"],
}


def _to_view(user_doc: dict) -> dict:
    """读用户 settings 视图(密码脱敏为 boolean 是否设置)"""
    return {
        "email":          user_doc.get("email", ""),
        "smtp_host":      user_doc.get("smtp_host", "smtp.qq.com"),
        "smtp_port":      int(user_doc.get("smtp_port", 465) or 465),
        "smtp_user":      user_doc.get("smtp_user", ""),
        "smtp_pass_set":  bool(user_doc.get("smtp_pass")),
        "feishu_webhook": user_doc.get("feishu_webhook", ""),
        "wechat_webhook": user_doc.get("wechat_webhook", ""),
        "webhook_url":    user_doc.get("webhook_url", ""),
        "channels":       user_doc.get("default_channels", ["inbox"]),
    }


class SettingsUpdate(BaseModel):
    email:          Optional[str] = None
    smtp_host:      Optional[str] = None
    smtp_port:      Optional[int] = None
    smtp_user:      Optional[str] = None
    smtp_pass:      Optional[str] = None  # 留空 = 不改
    feishu_webhook: Optional[str] = None
    wechat_webhook: Optional[str] = None
    webhook_url:    Optional[str] = None
    default_channels: Optional[list[str]] = None


@router.get("/settings")
async def get_my_settings(user: dict = Depends(require_user)):
    db = get_db()
    doc = db["users"].find_one({"_id": user["id"]}) or {}
    return _to_view(doc)


@router.put("/settings")
async def update_my_settings(body: SettingsUpdate, user: dict = Depends(require_user)):
    db = get_db()
    update: dict = {}
    if body.email is not None:
        update["email"] = body.email
    if body.smtp_host is not None:
        update["smtp_host"] = body.smtp_host
    if body.smtp_port is not None:
        update["smtp_port"] = int(body.smtp_port)
    if body.smtp_user is not None:
        update["smtp_user"] = body.smtp_user
    if body.smtp_pass is not None and body.smtp_pass != "":
        update["smtp_pass"] = body.smtp_pass
    if body.feishu_webhook is not None:
        update["feishu_webhook"] = body.feishu_webhook
    if body.feishu_open_id is not None:
        update["feishu_open_id"] = body.feishu_open_id
    if body.wechat_webhook is not None:
        update["wechat_webhook"] = body.wechat_wechat if False else body.wechat_webhook
    if body.webhook_url is not None:
        update["webhook_url"] = body.webhook_url
    if body.default_channels is not None:
        valid = list(CHANNEL_FIELDS.keys())
        update["default_channels"] = [c for c in body.default_channels if c in valid]
    if not update:
        return {"ok": False, "message": "no fields to update"}
    from datetime import datetime, timezone
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    db["users"].update_one({"_id": user["id"]}, {"$set": update}, upsert=True)
    return {"ok": True, "updated": list(update.keys())}


@router.post("/notifier/test")
async def test_my_notifier(body: dict, user: dict = Depends(require_user)):
    """一键测试指定渠道(给前端 button)"""
    channel = body.get("channel")
    if not channel or channel not in CHANNEL_FIELDS:
        raise HTTPException(400, f"channel must be one of {list(CHANNEL_FIELDS.keys())}")
    from notifier.test import test_channel
    db = get_db()
    user_doc = db["users"].find_one({"_id": user["id"]}) or user
    # 把用户 settings 字段映射到 notifier 期望的字段名(notifier 期望 feishu_webhook/wechat_webhook/webhook_url/email)
    test_user = {
        **user_doc,
        "email": user_doc.get("email", ""),
        "feishu_webhook": user_doc.get("feishu_webhook", ""),
        "feishu_open_id": user_doc.get("feishu_open_id", ""),
        "wechat_webhook": user_doc.get("wechat_webhook", ""),
        "webhook_url": user_doc.get("webhook_url", ""),
        "username": user_doc.get("username", "test"),
    }
    r = test_channel(channel, user=test_user)
    return {"channel": channel, **r}


@router.get("/notifier/channels")
async def list_channels():
    """列 5 个渠道 + 各需要哪些字段(给前端表单用)"""
    return {
        "channels": [
            {
                "name": name,
                "label": {"inbox": "站内 Inbox", "email": "邮箱 SMTP", "feishu": "飞书机器人", "wechat": "企业微信机器人", "webhook": "通用 Webhook"}.get(name, name),
                "required_fields": fields,
                "configured": "auto-check-in-frontend",
            }
            for name, fields in CHANNEL_FIELDS.items()
        ]
    }
