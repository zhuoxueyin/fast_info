"""统一推送格式 (Day 8 v0.5.0)

快快阅读:同一份推送内容需要适配 4 个渠道:
  - inbox 站内 (Mongo 存为 subscriptions_delivered)
  - email SMTP (HTML)
  - feishu / feishu_dm (interactive card)
  - webhook (Markdown)
  - wechat (Markdown)

每条 item 必须含以下字段才能接入推送:
  - url (原文地址) — 用户场景频发,送原文到点
  - source / category / fetched_at / relevance
  - summary / title

不同渠道使用不同 *body* 字段,后台调用 send_all() 时多调要提供:
  body_html:  邮件用 HTML
  body_md:    markdown (通用 webhook / wechat)
  card:       飞书多元素 interactive card (inter 手手写)
"""
from __future__ import annotations
from typing import Iterable, Optional
from datetime import datetime, timezone
import re
import html as _html


def _esc(s: str) -> str:
    """防 XSS 转义"""
    return _html.escape(s or "", quote=True)


def _fmt_time(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        # 转 +8 中文时间
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC"
    except Exception:
        return ""


def _strip_url(url: str) -> str:
    """推文 URL 限制长度(飞书 card 不能超过 256 字符)"""
    if not url:
        return ""
    if len(url) > 250:
        return url[:240] + "...(URL过长请打开查看)"
    return url


def format_html(sub: dict, items: Iterable[dict], inbox_url: Optional[str] = None) -> str:
    """HTML body for email / 站内 (UI 渲染还会重编排)
    返回拼接的 HTML 字符串
    """
    items = list(items)
    lines: list[str] = []
    title = sub.get("title") or sub.get("nl_query", "订阅")
    lines.append(f"<h2 style='margin:0 0 6px;font:600 18px ui-sans-serif;'>📬 { _esc(title) }</h2>")
    lines.append(f"<p style='margin:0 0 16px;color:#64748b;font:13px ui-sans-serif;'>共 {len(items)} 条新内容 · 来自 fastInfo AI 情报中枢</p>")

    for i, it in enumerate(items, 1):
        url = _strip_url(it.get("url", ""))
        src = it.get("source") or ""
        cat = it.get("category") or it.get("category_l1") or ""
        rel = it.get("relevance")
        rel_str = f" · 相关度 {int(round((rel or 0.5) * 100))}%" if rel else ""
        t = _fmt_time(it.get("fetched_at"))

        lines.append("<div style='margin:0 0 18px;padding:12px 14px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;'>")
        # title link
        lines.append(f"<div style='font:600 15px ui-sans-serif;margin:0 0 6px;'>{i}. ")
        if url:
            lines.append(f"<a href='{_esc(url)}' style='color:#0f766e;text-decoration:none;' target='_blank'>{_esc(it.get('title', '')[:120])}</a>")
        else:
            lines.append(_esc(it.get("title", "")[:120]))
        lines.append("</div>")
        # meta
        meta_bits = []
        if src: meta_bits.append(f"来源: <b>{_esc(src)}</b>")
        if cat: meta_bits.append(f"<span style='background:#dbeafe;color:#1d4ed8;padding:1px 8px;border-radius:10px;font-size:11px;'>{_esc(cat)}</span>")
        if rel_str: meta_bits.append(f"<span style='color:#94a3b8;font-size:11px;'>{rel_str}</span>")
        if t: meta_bits.append(f"<span style='color:#94a3b8;font-size:11px;'>{_esc(t)}</span>")
        lines.append(f"<div style='font:12px ui-sans-serif;color:#475569;margin:0 0 8px;'>{' · '.join(meta_bits)}</div>")
        # summary
        sm = it.get("summary_zh") or it.get("summary") or it.get("title_zh") or ""
        if sm:
            lines.append(f"<div style='font:13px ui-sans-serif;color:#1e293b;line-height:1.6;margin:0 0 6px;'>{_esc(sm[:280])}</div>")
        # zh title (翻译)
        if it.get("title_zh") and it.get("title_zh") != it.get("title"):
            lines.append(f"<div style='font:12px ui-sans-serif;color:#0f766e;margin:0 0 8px;'>📍 译: {_esc(it['title_zh'][:80])}</div>")
        # url button
        if url:
            lines.append(f"<div style='margin-top:6px;'><a href='{_esc(url)}' target='_blank' style='display:inline-block;padding:4px 14px;background:#0f766e;color:#fff;text-decoration:none;border-radius:6px;font:600 12px ui-sans-serif;'>↗ 阅读原文</a></div>")
        lines.append("</div>")

    if inbox_url:
        lines.append(f"<p style='margin:16px 0 0;text-align:center;'><a href='{_esc(inbox_url)}' style='color:#0f766e;font:13px ui-sans-serif;'>📥 在 fastInfo 网站查看全部 / 标记已读</a></p>")
    return "\n".join(lines)


def format_markdown(sub: dict, items: Iterable[dict], inbox_url: Optional[str] = None) -> str:
    """Markdown body for webhook / wechat / 站内 fallback"""
    items = list(items)
    title = sub.get("title") or sub.get("nl_query", "订阅")
    lines: list[str] = [f"📬 **{title}** · {len(items)} 条新内容", ""]
    for i, it in enumerate(items, 1):
        url = _strip_url(it.get("url", ""))
        src = it.get("source") or ""
        cat = it.get("category") or ""
        t = _fmt_time(it.get("fetched_at"))
        sm = it.get("summary_zh") or it.get("summary") or ""

        lines.append(f"**{i}. [{_strip_md(it.get('title', '')[:100])}]({url})**" if url else f"**{i}. {it.get('title', '')[:100]}**")
        meta = []
        if src: meta.append(f"`{src}`")
        if cat: meta.append(f"`{cat}`")
        if t: meta.append(t)
        if meta: lines.append("  " + " · ".join(meta))
        if sm: lines.append(f"  {sm[:240]}")
        if it.get("title_zh") and it.get("title_zh") != it.get("title"):
            lines.append(f"  📍 译: {it['title_zh'][:80]}")
        lines.append("")
    if inbox_url:
        lines.append(f"\n📥 [在 fastInfo 网站查看全部]({inbox_url})")
    return "\n".join(lines)


def format_feishu_card(sub: dict, items: Iterable[dict], inbox_url: Optional[str] = None) -> dict:
    """飞书 / 飞书个人单聊 interactive card JSON"""
    items = list(items)
    title = sub.get("title") or sub.get("nl_query", "订阅")
    elements: list[dict] = []

    # header
    header_text = f"📬 {title} · {len(items)} 条新内容"

    for i, it in enumerate(items, 1):
        url = _strip_url(it.get("url", ""))
        src = it.get("source") or ""
        cat = it.get("category") or ""
        sm = (it.get("summary_zh") or it.get("summary") or "")[:280]

        # 一条 item = 一块 lark_md
        md_lines: list[str] = []
        if url:
            md_lines.append(f"**[{it.get('title', '')[:100]}]({url})**")
        else:
            md_lines.append(f"**{it.get('title', '')[:100]}**")
        meta = []
        if src: meta.append(f"`{src}`")
        if cat: meta.append(f"`{cat}`")
        if meta: md_lines.append("  " + " · ".join(meta))
        if sm: md_lines.append(f"  {sm[:240]}")
        if it.get("title_zh") and it.get("title_zh") != it.get("title"):
            md_lines.append(f"  📍 译: {it['title_zh'][:80]}")

        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(md_lines)},
        })
        # 每条后面加分隔线
        if i < len(items):
            elements.append({"tag": "hr"})

        # 加「原文」按钮(手起手起手手手手手起起起起起,feishu 格式如下)
        if url:
            # 作为一个 action button 在该 item 卡片后面
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": f"↗ 阅读原文({i}/{len(items)})"},
                    "type": "primary",
                    "url": url,
                }],
            })

    if inbox_url:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📥 在 fastInfo 网站查看全部"},
                "type": "default",
                "url": inbox_url,
            }],
        })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": header_text},
                "template": "green",
            },
            "elements": elements,
        },
    }


def _strip_md(s: str) -> str:
    """去掉 markdown 特殊字符"""
    return re.sub(r"[\[\]()#*_`]", "", s or "")


def inbox_url_for(site_base: str) -> str:
    """返回用户在快信网站看到的 inbox 推送记录 URL"""
    if not site_base:
        site_base = "/me/inbox"
    return site_base.rstrip("/") + "/me/inbox"
