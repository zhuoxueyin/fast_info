"""回填历史 item 的 title_zh / title (中文翻译)

用法: python scripts/backfill_title_zh.py [--dry-run] [--source x:sama]

逻辑:
- 找出 title 是英文的 item(英文是主体,不只是含英文产品名)
- 调用 LLM 输出中文 title
- 写回 items.title / title_original / title_translated
"""
from __future__ import annotations
import asyncio
import re
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import argparse
import json as _json
from pymongo import MongoClient, UpdateOne
from llm.model_registry import build_default_registry

# 一个 token 由"连续 ASCII 字母"组成,且 token 占比 > 50% 时,判定为英文标题
def is_english_title(text: str) -> bool:
    if not text or len(text) < 8:
        return False
    # 拆 token
    en_tokens = re.findall(r'[A-Za-z]+', text)
    en_chars = sum(len(t) for t in en_tokens)
    # 中文字符数
    zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if en_chars < 8:
        return False
    # 英文是主体 (英文 token 字符数 > 中文字符数 * 1.2 + 5)
    return en_chars >= zh_chars * 1.2 + 5


async def translate_one(registry, title: str, summary_hint: str = "") -> str:
    """LLM 把英文 title 翻译成简洁中文"""
    system_prompt = (
        "你是新闻标题翻译。请把下面的英文新闻标题翻译成简洁中文(≤30字)。"
        "球队名/人名/专有名词可保留英文(如 Cristiano Ronaldo / Lakers / World Cup)。"
        "只输出翻译后的中文标题本身,不要任何前后解释、引号、标点包裹。"
    )
    user = f"标题: {title}"
    if summary_hint:
        user += f"\n背景: {summary_hint[:200]}"
    try:
        result = await registry.get("short_summary").chat(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": user}],
            max_tokens=600, temperature=0.2,
        )
        content = result["choices"][0]["message"]["content"]
        # 1) 切掉 <thinking>...</thinking> 块(K2.6)
        content = re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>", "", content, flags=re.DOTALL)
        content = content.strip()
        # 3) 去掉包裹引号/反引号
        content = content.strip('`').strip('"').strip("'").strip()
        # 4) 截掉首尾的中文标点(如"你好世界。")
        content = content.rstrip('。.!?！？,;:：;')
        return content[:80]
    except Exception as e:
        print(f"  [llm-fail] {title[:40]}: {type(e).__name__}: {e}")
        return ""


async def main(dry_run: bool = False, source_filter: str | None = None):
    c = MongoClient('mongodb://127.0.0.1:27017')['fastinfo']

    q = {
        "$or": [
            {"title_translated": {"$exists": False}},
            {"title_translated": False},
        ],
    }
    if source_filter:
        q['source'] = source_filter

    candidates = []
    for it in c['items'].find(q, {'title': 1, 'title_original': 1, 'summary': 1, 'source': 1}):
        title = it.get('title') or ''
        original = it.get('title_original') or title
        if is_english_title(title) or is_english_title(original):
            candidates.append({
                '_id': it['_id'],
                'title': title,
                'title_original': original,
                'summary': it.get('summary', ''),
                'source': it.get('source'),
            })

    print(f"待回填: {len(candidates)} 条")
    if not candidates:
        return

    if dry_run:
        for it in candidates[:30]:
            print(f"  - [{it['source']}] {it['title'][:80]}")
        return

    registry = build_default_registry()

    sem = asyncio.Semaphore(4)

    async def proc(item):
        async with sem:
            new_title = await translate_one(registry, item['title_original'], item['summary'])
            # 必须以中文为主
            if not new_title:
                return None
            zh_chars = len(re.findall(r'[\u4e00-\u9fff]', new_title))
            if zh_chars < 4:
                return None
            print(f"  ✓ {item['title_original'][:50]}  ->  {new_title[:50]}")
            return UpdateOne(
                {'_id': item['_id']},
                {'$set': {
                    'title': new_title,
                    'title_original': item['title_original'],
                    'title_translated': True,
                    'title_translated_at': datetime.now(timezone.utc).isoformat(),
                }},
            )

    updates = await asyncio.gather(*[proc(it) for it in candidates])
    updates = [u for u in updates if u is not None]
    print(f"实际翻译: {len(updates)} 条")

    if updates:
        result = c['items'].bulk_write(updates)
        print(f"bulk_write: matched={result.matched_count}, modified={result.modified_count}")

    await registry.aclose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--source", default=None, help="只处理指定 source")
    args = p.parse_args()
    asyncio.run(main(dry_run=args.dry_run, source_filter=args.source))
