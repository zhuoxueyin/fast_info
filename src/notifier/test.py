"""fastInfo · notifier 测试

一键测试渠道是否通,无论用户配置是不是完整。
返回 {ok: bool, message: str, ...}。

飞书多群:支持按群维度测试(feishu_name / feishu_webhook / feishu_index),
未指定时仍测全部已配置群(兼容旧行为)。
"""
from __future__ import annotations
import os
from typing import Optional

from . import get, available_channels, get_feishu_webhooks


def _test_subject(target_name: str | None = None) -> str:
    if target_name:
        return f"[fastInfo] 推送通道测试 · {target_name}"
    return "[fastInfo] 推送通道测试"


def _test_content(target_name: str | None = None) -> str:
    if target_name:
        return (
            f"🎉 这是 fastInfo 推送通道测试消息。\n\n"
            f"目标群: **{target_name}**\n\n"
            f"如果你在本群收到了这条消息,说明该群机器人配置成功。"
        )
    return (
        "🎉 这是 fastInfo 推送通道测试消息。\n\n"
        "如果你收到了这条消息,说明该通道配置成功。\n\n"
        "可以推送的真实内容会在订阅触发时到达。"
    )


def _resolve_feishu_user(
    user: dict,
    *,
    feishu_name: str | None = None,
    feishu_webhook: str | None = None,
    feishu_index: int | None = None,
) -> tuple[dict, str | None, str | None]:
    """按群维度裁剪 user 的飞书配置。

    返回 (user_for_send, target_label, error_message)
    - 未指定任何 target → 原样返回,测全部群
    - 指定了 → user 只保留目标群一条 webhook
    """
    # 显式 webhook:优先(前端可测未保存的输入)
    if feishu_webhook and str(feishu_webhook).strip():
        name = (feishu_name or "").strip() or "测试群"
        hook = {"name": name, "webhook": str(feishu_webhook).strip()}
        u = dict(user)
        u["feishu_webhooks"] = [hook]
        u["feishu_webhook"] = ""
        return u, name, None

    hooks = get_feishu_webhooks(user)
    if not hooks:
        return user, None, "未配置任何飞书群机器人"

    # 按 index
    if feishu_index is not None:
        try:
            idx = int(feishu_index)
        except (TypeError, ValueError):
            return user, None, f"无效的 feishu_index: {feishu_index!r}"
        if idx < 0 or idx >= len(hooks):
            return user, None, f"feishu_index={idx} 超出范围(0..{len(hooks)-1})"
        hook = hooks[idx]
        u = dict(user)
        u["feishu_webhooks"] = [hook]
        u["feishu_webhook"] = ""
        return u, hook["name"], None

    # 按 name
    if feishu_name is not None and str(feishu_name).strip():
        name = str(feishu_name).strip()
        matched = [h for h in hooks if h.get("name") == name]
        if not matched:
            # 宽松:名称包含
            matched = [h for h in hooks if name in (h.get("name") or "")]
        if not matched:
            names = ", ".join(h.get("name", "?") for h in hooks)
            return user, None, f"找不到群「{name}」,已配置: {names}"
        hook = matched[0]
        u = dict(user)
        u["feishu_webhooks"] = [hook]
        u["feishu_webhook"] = ""
        return u, hook["name"], None

    # 全量
    return user, None, None


def test_channel(
    name: str,
    user: Optional[dict] = None,
    item: Optional[dict] = None,
    *,
    feishu_name: str | None = None,
    feishu_webhook: str | None = None,
    feishu_index: int | None = None,
) -> dict:
    """测试一个渠道,返回 {ok, message, targets?}。

    飞书按群测试(推荐):
      test_channel("feishu", user, feishu_name="技术群")
      test_channel("feishu", user, feishu_webhook="https://open.feishu.cn/...")
      test_channel("feishu", user, feishu_index=0)

    未指定 target 时测全部已配置群(兼容旧调用)。
    """
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

    target_label: str | None = None
    if name == "feishu":
        user, target_label, err = _resolve_feishu_user(
            user,
            feishu_name=feishu_name,
            feishu_webhook=feishu_webhook,
            feishu_index=feishu_index,
        )
        if err:
            return {"ok": False, "message": err, "target": target_label}

    try:
        result = n.send(
            user,
            _test_subject(target_label),
            _test_content(target_label),
            [item],
            body_md=_test_content(target_label),
        )
        if isinstance(result, dict):
            ok = bool(result.get("ok"))
            targets = result.get("targets")
            out: dict = {"ok": ok, "target": target_label}
            if targets:
                parts = [
                    f"{t.get('name', '群')}: {'OK' if t.get('ok') else 'FAIL'}"
                    + (f" ({t.get('error')})" if t.get("error") else "")
                    for t in targets
                ]
                out["message"] = "; ".join(parts)
                out["targets"] = targets
            else:
                out["message"] = (
                    "发送成功" if ok else (result.get("error") or "发送失败")
                )
            if target_label and ok:
                out["message"] = f"群「{target_label}」测试通过"
            elif target_label and not ok:
                out["message"] = f"群「{target_label}」测试失败: {out.get('message')}"
            return out
        return {
            "ok": bool(result),
            "message": "发送成功" if result else "发送失败",
            "target": target_label,
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"{type(e).__name__}: {str(e)[:200]}",
            "target": target_label,
        }


def test_all(user: Optional[dict] = None) -> dict:
    """测试所有渠道(飞书测全部已配置群)"""
    out = {}
    for ch in available_channels():
        out[ch] = test_channel(ch, user=user)
    return out
