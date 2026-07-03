"""Day 5 · Alarm 派发器

触发场景:
  - 单源连续失败 ≥ source_config.auto_disable_threshold → 自动禁用 + 触发 alarm
  - 单源空 feed > N 次 → 触发 warning
  - 全平台 1h 内失败 ≥ 80% → 触发 critical(下一阶段)

告警渠道(按优先级):
  1. 写 system_alerts 集合(总账,可查)
  2. Feishu / WeChat / Webhook / SMTP(复用 src.notifier 已有抽象)— 通过环境变量配置
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Literal

import httpx
from storage.mongo_writer import get_db

Severity = Literal["info", "warning", "critical"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fire(
    *,
    source_id: str,
    kind: str,
    severity: Severity,
    message: str,
    extra: dict | None = None,
):
    """触发一条告警,写 system_alerts collection + 调 webhook。"""
    db = get_db()
    doc = {
        "source_id": source_id,
        "kind": kind,                                    # "auto_disabled" | "consecutive_fail" | ...
        "severity": severity,
        "message": message,
        "extra": extra or {},
        "created_at": now_iso(),
        "ack": False,                                    # 是否已确认
    }
    db["system_alerts"].insert_one(doc)

    # webhook (per env)
    webhook = os.environ.get("FASTINFO_ALARM_WEBHOOK_URL", "").strip()
    if webhook:
        try:
            payload = {
                "type": "fastinfo_alarm",
                "severity": severity,
                "kind": kind,
                "source_id": source_id,
                "message": message,
                "extra": extra or {},
                "ts": doc["created_at"],
            }
            httpx.post(webhook, json=payload, timeout=5.0)
        except Exception as e:
            db["system_alerts"].update_one(
                {"_id": doc["_id"]},
                {"$set": {"webhook_error": f"{type(e).__name__}: {str(e)[:200]}"}},
            )


def ensure_indexes():
    db = get_db()
    db["system_alerts"].create_index([("source_id", 1), ("created_at", -1)])
    db["system_alerts"].create_index([("severity", 1), ("ack", 1)])
    db["system_alerts"].create_index([("created_at", -1)])
