"""fastInfo · NL PATCH(Day 6 v0.3.0)

用自然语言修改已有订阅。例:
  "改成每天下午 5 点,只发飞书"  → {"cron_expr": "0 17 * * *", "channels": ["feishu"]}
  "暂停"                          → {"is_active": false}
  "每周三五 9 点发"               → {"cron_expr": "0 9 * * 3,5"}
  "只看大模型相关的"              → {"categories_l2": ["大模型"]}
  "改成 5 条"                     → {"max_items": 5}

复用 nl_parse 模型组(M2.7-highspeed → K2.6 四级 fallback)。prompt 专门为 patch 设计。
"""
from __future__ import annotations
import asyncio
import json
import re
from typing import Optional

from llm.model_registry import build_default_registry


_PROMPT = """你是 fastInfo 的订阅修改助手。

当前订阅配置(JSON):
{current}

用户修改指令: {nl_command}

返回一个 JSON 对象,**只包含要改动的字段**(没改的字段不要返回)。
可改字段:
  cron_expr:      cron 表达式,例如 '0 17 * * *'(每天 17 点)、'*/30 * * * *'(每 30 分钟)
  channels:       渠道列表,['inbox', 'email', 'feishu', 'wechat', 'webhook']
  max_items:      每次最多取 N 条,整数
  interval_min:   自定义间隔分钟数(0=用 cron)
  categories_l1:  一级类目(科技/AI/体育/娱乐/财经/汽车/其他)
  categories_l2:  二级类目(大模型/AI芯片/...)
  keywords:       关键词数组
  title:          标题字符串
  is_active:      true / false(暂停/启用)

⚠️ 严格按 JSON 输出,不要 markdown 包裹,不要解释。
"""


_VALID_FIELDS = {"cron_expr", "channels", "max_items", "interval_min",
                 "categories_l1", "categories_l2", "keywords", "title", "is_active"}


async def parse_nl_patch(nl_command: str, current_sub: dict) -> dict:
    """NL → 要改动的字段 delta(只含要改的字段)"""
    registry = build_default_registry()
    cur_view = {k: current_sub.get(k) for k in _VALID_FIELDS if current_sub.get(k) is not None}
    try:
        prompt = _PROMPT.format(
            current=json.dumps(cur_view, ensure_ascii=False, default=str)[:1000],
            nl_command=nl_command,
        )
        messages = [
            {"role": "system", "content": "输出必须是合法 JSON 对象,不包 markdown 包裹。"},
            {"role": "user", "content": prompt},
        ]
        result = await registry.get("nl_parse").chat(messages, max_tokens=400, temperature=0.2)
        content = result["choices"][0]["message"]["content"].strip()
        # 清理 <think> 标签 + markdown
        content = re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>", "", content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = content.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
        parsed = json.loads(content)
    except Exception as e:
        print(f"[parse_nl_patch] LLM failed: {type(e).__name__}: {str(e)[:100]}")
        parsed = {}
    finally:
        try:
            await registry.aclose()
        except Exception:
            pass
    if not isinstance(parsed, dict):
        return {}
    return {k: v for k, v in parsed.items() if k in _VALID_FIELDS and v is not None}


def apply_nl_patch_sync(nl_command: str, current_sub: dict) -> dict:
    """CLI / 测试 sync 包装"""
    return asyncio.run(parse_nl_patch(nl_command, current_sub))
