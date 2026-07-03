"""
fastInfo · W2 实战:抓 RSS → 走 M3 生成摘要 → 写入 MongoDB
===========================================================

数据流:
    RSS(7 个站点)
        ↓
    RSS Collector
        ↓
    LLM short_summary (M3 主力,K2.6 备用)
        ↓
    MongoDB(db=fastinfo, collection=items, key=url_hash)

跑法:
    cd D:\WORK\trae\fast_info
    $env:PYTHONPATH = "."
    $env:MMX_API_KEY = "sk-..."
    python examples/fetch_and_summarize.py
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# 让 src/ 下的模块可被 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from crawler.rss_collector import fetch_all, Item
from llm.model_registry import build_default_registry, ModelError
from storage.mongo_writer import (
    upsert_item_async,
    get_done_urls,
    ensure_indexes,
    count_items,
    stats,
)


_THINK_RE = re.compile(r"<(?:think|thinking)>.*?</(?:think|thinking)>", re.DOTALL)
_JSON_OBJ_RE = re.compile(r"\{[\s\S]*\}")


def banner(text: str):
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def strip_think(text: str) -> str:
    """去掉模型输出的 <think>...</think> 块"""
    return _THINK_RE.sub("", text).strip()


def parse_summary_json(content: str) -> dict:
    """M3/Kimi 输出可能含 thinking / markdown 装饰,要剥干净再 parse"""
    cleaned = strip_think(content)
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = _JSON_OBJ_RE.search(cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"summary": cleaned, "key_points": [], "category": "其他", "relevance": 0.5}


async def summarize_one(registry, item: Item) -> dict:
    """对单条 item 生成结构化摘要"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个中文资讯编辑。根据用户给的新闻,生成结构化 JSON 结果。\n"
                "字段:\n"
                "  summary: 120-180 字的中文摘要,核心事实清晰\n"
                "  key_points: 2-4 条关键要点,字符串数组\n"
                "  category: AI / 科技 / 财经 / 体育 / 娱乐 / 其他 中选一个\n"
                "  relevance: 0-1 之间的浮点数,代表对'科技/AI 行业人士'的相关度\n"
                "严格按 JSON 输出,不要加 markdown 包裹,不要解释。"
            ),
        },
        {
            "role": "user",
            "content": f"标题: {item.title}\n\n来源描述: {item.summary_html[:300]}",
        },
    ]

    t0 = time.time()
    result = await registry.get("short_summary").chat(messages, max_tokens=600, temperature=0.3)
    elapsed_ms = int((time.time() - t0) * 1000)
    content = result["choices"][0]["message"]["content"].strip()

    parsed = parse_summary_json(content)

    return {
        # MongoDB 唯一键
        "url_hash": item.id,           # id 已经是 sha256 前 24 位
        "id": item.id,
        "source": item.source,
        "source_url": item.source_url,
        "url": item.url,
        "title": item.title,
        "published_at": item.published_at,
        "fetched_at": item.fetched_at,
        "author": item.author,
        "tags": item.tags,
        "language": item.language,
        # LLM 生成
        "summary": parsed.get("summary", content),
        "key_points": parsed.get("key_points", []),
        "category": parsed.get("category", "其他"),
        "relevance": parsed.get("relevance", 0.5),
        "summary_model": result.get("model", "?"),
        "summary_latency_ms": elapsed_ms,
        "summary_at": datetime.now(timezone.utc).isoformat(),
    }


async def main():
    banner("[0/4] 准备:确保 MongoDB 索引")
    ensure_indexes()
    print(f"   MongoDB 当前共 {count_items()} 条")

    banner("[1/4] 加载已完成状态(从 MongoDB 读 url_hash,做增量)")
    done = get_done_urls()
    print(f"   已入库 {len(done)} 条 url_hash")

    banner("[2/4] 抓 RSS(7 个源)")
    items = await fetch_all(limit_per_source=8)
    new_items = [it for it in items if it.id not in done]
    print(f"\n   共抓 {len(items)} 条,新增 {len(new_items)} 条(已过滤历史)")

    if not new_items:
        print("\n   ⚠ 没有新内容,跳过摘要生成")
        banner("完成 ✓")
        s = stats()
        print(f"   MongoDB 总计: {s['total']} 条")
        for src in s["by_source"][:5]:
            print(f"     {src['_id']:<20} {src['count']:>5}")
        return

    if not os.environ.get("MMX_API_KEY"):
        print("\n   ✗ MMX_API_KEY 未设置,无法跑摘要")
        return

    banner(f"[3/4] 走 LLM 生成摘要(并发 3,共 {len(new_items)} 条)")
    registry = build_default_registry()
    sem = asyncio.Semaphore(3)

    async def bounded_summarize(item):
        async with sem:
            try:
                return await summarize_one(registry, item), None
            except Exception as e:
                return None, str(e)

    tasks = [bounded_summarize(it) for it in new_items]
    completed = 0
    failed = 0
    total_ms = 0
    success_model = {}
    inserted = 0
    async for coro in asyncio.as_completed(tasks):
        result, err = await coro
        if err or result is None:
            failed += 1
            print(f"   ✗ error: {err}")
            continue
        # 写 MongoDB
        try:
            is_new = await upsert_item_async(result)
            if is_new:
                inserted += 1
        except Exception as e:
            failed += 1
            print(f"   ✗ mongo write error: {e}")
            continue
        completed += 1
        total_ms += result.get("summary_latency_ms", 0)
        model = result.get("summary_model", "?")
        success_model[model] = success_model.get(model, 0) + 1
        title_short = result["title"][:30] + "..."
        print(f"   {model:<28} | {title_short:<32} | {result['summary_latency_ms']}ms")

    await registry.aclose()

    banner("完成 ✓")
    s = stats()
    print(f"   本次: 成功 {completed},失败 {failed},新增入库 {inserted}")
    if completed:
        print(f"   平均延迟: {total_ms // completed}ms")
    if success_model:
        print(f"   走过模型: {success_model}")
    print(f"   MongoDB 总计: {s['total']} 条")
    for src in s["by_source"][:5]:
        print(f"     {src['_id']:<20} {src['count']:>5}")


if __name__ == "__main__":
    asyncio.run(main())