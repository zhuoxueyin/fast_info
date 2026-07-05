"""用户推送配置

GET  /api/settings                       读用户推送配置(密码脱敏)
PUT  /api/settings                       改配置
POST /api/notifier/test                  测试渠道(给前端 button 调用)
GET  /api/notifier/channels              列出可用渠道 + 需要字段

支持的渠道:
  - inbox      站内收件箱(无需配置)
  - email      邮件 (SMTP 配置)
  - feishu     飞书群机器人 (webhook 地址)
  - wechat     企业微信机器人 (webhook 地址)
  - webhook    通用 webhook (URL)

存储在 users 集合,user_id 主键,可选。

设计要点(P2 唯一链路):
    user dict 由 deps.require_user 填充好,这里直接用,
    不再二次 Mongo 查询 ── 旧实现每次都 ObjectId() 一次,在
    老 JWT sub='u_admin' 时崩成 500 (pre-staging 复现过)。
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_user
from storage.mongo_writer import get_db


router = APIRouter(tags=["settings"])

DEFAULT_DB = "fastinfo"

# 可用渠道 + 各需要字段(给前端表单用)
CHANNEL_FIELDS = {
    "inbox":     [],
    "email":     ["email", "smtp_host", "smtp_port", "smtp_user", "smtp_pass"],
    "feishu":    ["feishu_webhook"],
    "wechat":    ["wechat_webhook"],
    "webhook":   ["webhook_url"],
}

CHANNEL_LABEL = {
    "inbox":  "站内 Inbox",
    "email":  "邮件 SMTP",
    "feishu": "飞书群机器人",
    "wechat": "企业微信",
    "webhook": "Webhook",
}


def _available_channels(user: dict) -> set[str]:
    """根据用户 settings 实际配置,返回当前可用的推送渠道。

    一致性原则(Day 7):settings 没配齐的渠道,在前端就不该出现
    (NewSubPage / SettingsPage / MePage 都以此为唯一来源)。
    """
    out = {"inbox"}  # 站内永远可用
    if user.get("feishu_webhook"):
        out.add("feishu")
    if user.get("wechat_webhook"):
        out.add("wechat")
    if user.get("webhook_url"):
        out.add("webhook")
    # email 至少要有 收件邮箱 + SMTP 用户(授权码可后填,因为存的是加密 hash,前端未必能展示)
    if user.get("email") and user.get("smtp_user"):
        out.add("email")
    return out


def _to_view(user: dict) -> dict:
    """读用户 settings 视图(密码脱敏)。入参是 deps 已经填好的 user dict。"""
    return {
        "email":                     user.get("email", ""),
        "nickname":                  user.get("nickname", "") or "",
        "avatar_url":                user.get("avatar_url", "") or "",
        "smtp_host":                 user.get("smtp_host", "smtp.qq.com"),
        "smtp_port":                 user.get("smtp_port", 465),
        "smtp_user":                 user.get("smtp_user", ""),
        "smtp_pass_set":             bool(user.get("smtp_pass")),
        "feishu_webhook":            user.get("feishu_webhook", ""),
        "wechat_webhook":            user.get("wechat_webhook", ""),
        "webhook_url":               user.get("webhook_url", ""),
        "channels":                  user.get("default_channels") or ["inbox"],
    }


class SettingsUpdate(BaseModel):
    email:                Optional[str] = None
    nickname:             Optional[str] = None       # Day 7:昵称
    avatar_url:           Optional[str] = None       # Day 7:头像 URL
    smtp_host:            Optional[str] = None
    smtp_port:            Optional[int] = None
    smtp_user:            Optional[str] = None
    smtp_pass:            Optional[str] = None  # 留空 = 不改
    feishu_webhook:       Optional[str] = None
    wechat_webhook:       Optional[str] = None
    webhook_url:          Optional[str] = None
    default_channels:     Optional[list[str]] = None


@router.get("/settings")
async def get_my_settings(user: dict = Depends(require_user)):
    """读用户推送配置(密码脱敏)。直接用 deps 填好的 user dict,不二次查库。"""
    return _to_view(user)


@router.put("/settings")
async def update_my_settings(body: SettingsUpdate, user: dict = Depends(require_user)):
    """改用户推送配置。deps 已经验证过 user.id 是合法 ObjectId,这里直接 update_one。"""
    update: dict = {}
    if body.email is not None:
        update["email"] = body.email
    if body.nickname is not None:
        # 空字符串 = 显式清空昵称(回退显示 username)
        update["nickname"] = body.nickname.strip() or ""
    if body.avatar_url is not None:
        update["avatar_url"] = body.avatar_url.strip()
    if body.smtp_host is not None:
        update["smtp_host"] = body.smtp_host
    if body.smtp_port is not None:
        update["smtp_port"] = body.smtp_port
    if body.smtp_user is not None:
        update["smtp_user"] = body.smtp_user
    if body.smtp_pass is not None and body.smtp_pass != "":
        update["smtp_pass"] = body.smtp_pass
    if body.feishu_webhook is not None:
        update["feishu_webhook"] = body.feishu_webhook
    if body.wechat_webhook is not None:
        update["wechat_webhook"] = body.wechat_webhook
    if body.webhook_url is not None:
        update["webhook_url"] = body.webhook_url
    if body.default_channels is not None:
        valid = list(CHANNEL_FIELDS.keys())
        update["default_channels"] = [c for c in body.default_channels if c in valid]
    if not update:
        return {"ok": False, "message": "no fields to update"}

    db = get_db()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    db["users"].update_one({"_id": ObjectId(user["id"])}, {"$set": update})
    return {"ok": True, "updated": list(update.keys())}


@router.post("/notifier/test")
async def test_my_notifier(body: dict, user: dict = Depends(require_user)):
    """测试指定渠道(给前端 button)。user dict 已经是 deps 填好的完整版,不二次查库。"""
    channel = body.get("channel")
    if not channel or channel not in CHANNEL_FIELDS:
        raise HTTPException(400, f"channel must be one of {list(CHANNEL_FIELDS.keys())}")
    from notifier.test import test_channel
    # user dict 已经包含所有 channel 字段 (deps._enrich_user 一次性填齐)
    r = test_channel(channel, user=user)
    return {"channel": channel, **r}


@router.get("/notifier/channels")
async def list_channels(user: dict = Depends(require_user)):
    """列出渠道 + 标记 available(根据当前用户的 settings 实际配置)。

    前端 NewSubPage / SettingsPage / MePage 全部以此作为 single source of truth:
    未配置的渠道压根不渲染,杜绝"勾了无声失败"的体验漏洞。
    """
    available = _available_channels(user)
    defaults = user.get("default_channels") or ["inbox"]
    return {
        "channels": [
            {
                "name": name,
                "label": CHANNEL_LABEL.get(name, name),
                "required_fields": fields,
                "available": name in available,
            }
            for name, fields in CHANNEL_FIELDS.items()
        ],
        "available": sorted(available),                                # 给前端快速遍历
        "default_channels": defaults if defaults else ["inbox"],      # 给 NewSubPage 初始化用
    }
