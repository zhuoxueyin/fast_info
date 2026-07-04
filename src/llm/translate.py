"""fastInfo · 英→中翻译 (Day 6 v0.3.0)

为英文源(item.title + summary)的英文内容自动翻译成中文,放在:
  item[\"title_zh\"]
  item[\"summary_zh\"]
并补充:
  item[\"lang_detected\"] = \"en\" / \"zh\" / \"mixed\"

使用 M2.7-highspeed 模型组(便宜快),独立 prompt,不污染 short_summary。
"""
from __future__ import annotations
import re
from typing import Optional

from llm.model_registry import build_default_registry


# 简易英文比例检测(粗,够用)
def detect_lang(text: str) -> str:
    if not text:
        return "unknown"
    text = text[:500]
    ascii_alpha = sum(1 for c in text if c.isascii() and c.isalpha())
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total = ascii_alpha + cn_chars
    if total == 0:
        return "unknown"
    return "en" if ascii_alpha / total > 0.6 else "zh" if cn_chars / total > 0.6 else "mixed"


_PROMPT_TRANSLATE = """你是 fastInfo 的英中翻译助手。

输入(英文或中英混合):
{text}

要求:
- 如果是英文 → 输出地道中文,标题 < 30 字,摘要 120-180 字 + 2-4 关键点
- 如果是中英混合 → 保持中文为主,英文术语保留(可在括号内补中文)
- 如果是中文 → 原样输出
- 严格按 JSON: {{"title\":..., \"summary\":..., \"key_points\": [\"...\", ...]}}
- 不要 markdown 包裹
"""


async def translate_to_zh(title: str, summary: str = "") -> Optional[dict]:
    """英→中翻译,返回 {title, summary, key_points} 或 None"""
    text = f"标题: {title}\n摘要: {summary[:400]}" if summary else f"标题: {title}"
    try:
        registry = build_default_registry()
        messages = [
            {"role": "system", "content": "输出必须是合法 JSON,不要 markdown。"},
            {"role": "user", "content": _PROMPT_TRANSLATE.format(text=text)},
        ]
        result = await registry.get("short_summary").chat(messages, max_tokens=500, temperature=0.3)
        content = result["choices"][0]["message"]["content"].strip()
        content = re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>", "", content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = content.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
        import json
        parsed = json.loads(content)
        return {
            "title_zh": parsed.get("title", "").strip(),
            "summary_zh": parsed.get("summary", "").strip(),
            "key_points_zh": parsed.get("key_points", []),
            "_model": result.get("model", "?"),
        }
    except Exception as e:
        print(f"[translate_to_zh] fail: {type(e).__name__}: {e}")
        return None


async def maybe_translate_item(doc: dict) -> dict:
    """对英文 item 跑翻译,加 title_zh/summary_zh 字段。不修改其他字段。"""
    title = doc.get("title", "")
    summary = doc.get("summary", "")
    lang = detect_lang(title + " " + summary)
    doc["lang_detected"] = lang
    if lang in ("en", "mixed"):  # mixed 也走一道,统一为中文优先
        zh = await translate_to_zh(title, summary)
        if zh:
            doc.update({
                "title_zh": zh["title_zh"],
                "summary_zh": zh["summary_zh"],
                "key_points_zh": zh["key_points_zh"],
                "translate_model": zh.get("_model", "?"),
            })
    return doc
