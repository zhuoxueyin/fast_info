"""
fastInfo · 后台抓取守护进程
================================

设计:独立进程,跟 CLI / 订阅 / API 解耦。
- 默认每 30 分钟跑一次 `ingest`
- 日志输出到 data/ingest-daemon.log
- 用 Windows Task Scheduler / Linux systemd timer 触发

跑法:
    python scripts/ingest_daemon.py           # 默认每 30 分钟
    python scripts/ingest_daemon.py --interval 600 --once   # 单次跑(测试)
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env(本地开发 + Docker volume 挂 /app/.env 都覆盖)
from _env import load_env
load_env()


async def run_once(args) -> dict:
    """执行一次完整 ingest 流程。

    返回 dict 便于 API 携带 warning 字段:
        {
            "fetched": int,        # 抓回原始条数
            "new": int,            # 去重后待处理条数
            "summarized": int,     # 成功摘要条数
            "failed": int,         # 摘要失败条数
            "warning": str,        # 警告原因(如 MMX_API_KEY 未设、源全失败等), 空 = 无
        }
    """
    import uuid
    from crawler.collectors import fetch_all
    from storage.mongo_writer import (
        upsert_item_async, get_done_urls, get_recent_title_hashes,
        ensure_indexes, create_task_run_pending, update_task_run_finished,
    )
    from llm.model_registry import build_default_registry
    import re as _re, json as _json

    # Day 5: 允许外部传入 run_id(给 API 异步触发用,保证返回的 run_id
    # 跟写入 task_runs 的是同一个 uuid)
    run_id = getattr(args, "run_id", None) or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    trigger = getattr(args, "trigger", "scheduled")
    operator = getattr(args, "operator", None)
    print(f"[{started_at.isoformat()}] ingest start (limit={args.limit}) run_id={run_id} trigger={trigger}")

    empty_result = lambda w="": {"fetched": 0, "new": 0, "summarized": 0, "failed": 0, "warning": w}

    # Day 5: 立刻写一条 status=running 占位记录,让前端轮询能看到
    try:
        create_task_run_pending({
            "run_id": run_id,
            "started_at": started_at,
            "trigger": trigger,
            "operator": operator,
            "limit": getattr(args, "limit", 8),
        })
    except Exception as e:
        print(f"  ⚠ create_task_run_pending failed(忽略): {e}")

    try:
        ensure_indexes()
    except Exception as e:
        print(f"  ✗ ensure_indexes failed: {e}")
        return empty_result(f"ensure_indexes failed: {e}")

    done = get_done_urls()
    recent_titles = get_recent_title_hashes(days=7)

    items = await fetch_all(limit_per_source=args.limit)
    new_items = [it for it in items if it.id not in done]
    # 跨源标题去重:7 天内已有相同规范化标题的,跳过(保留最早来源)
    before_dedup = len(new_items)
    new_items = [it for it in new_items if not it.title_hash or it.title_hash not in recent_titles]
    print(f"  fetched {len(items)}, new {before_dedup}, after title-dedup {len(new_items)}")

    if not new_items:
        # Day 5: 即便没新内容也要 update task_runs(否则状态卡 running)
        try:
            update_task_run_finished(run_id, {
                "finished_at": datetime.now(timezone.utc),
                "status": "done",
                "items_fetched": len(items),
                "items_summarized": 0,
                "items_failed": 0,
                "warning": "没有新内容(可能全部已抓过,或所有源都返回空)",
            })
        except Exception:
            pass
        return empty_result("没有新内容(可能全部已抓过,或所有源都返回空)")

    if not os.environ.get("MMX_API_KEY") and not os.environ.get("KIMI_API_KEY"):
        print("  ✗ MMX_API_KEY / KIMI_API_KEY 都没设")
        return empty_result("MMX_API_KEY 和 KIMI_API_KEY 都未配置 — 无法生成摘要")

    registry = build_default_registry()
    sem = asyncio.Semaphore(3)
    completed = 0
    failed = 0

    async def one(item):
        nonlocal completed, failed
        async with sem:
            system_prompt = (
                "你是中文资讯编辑。对给定文章标题和摘要进行处理，输出严格JSON（无markdown包裹，无多余文字）：\n"
                '{"title_zh": "中文标题(若原标题已是中文则与原标题一致;若为英文必须翻译成简洁中文,实体名/队名/球员名可保留英文,≤30字)", '
                '"summary": "120-180字中文摘要，信息完整，不空洞", "key_points": ["要点1","要点2","要点3"], '
                '"category": "二级分类(如大模型/AI芯片/新能源/自动驾驶/A股/影视等)", '
                '"category_l1": "一级分类，必须是：科技/AI/体育/娱乐/财经/汽车/其他 之一", '
                '"relevance": 0.0-10.0热度分}\n'
                "规则：category_l1必须从给定列表中选最贴切的一个；summary必须有实质内容不要空；title_zh必须输出。"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"标题: {item.title}\n来源: {item.source}\n原文摘要: {item.summary_html[:500]}"},
            ]
            fallback_summary = (item.summary_html or item.title)[:200].strip()
            parsed = None
            try:
                result = await registry.get("short_summary").chat(messages, max_tokens=800, temperature=0.3)
                content = result["choices"][0]["message"]["content"].strip()
                cleaned = _re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>", "", content, flags=_re.DOTALL).strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
                try:
                    parsed = _json.loads(cleaned) if cleaned.startswith("{") else None
                except Exception:
                    parsed = None
                if parsed is None:
                    m = _re.search(r"\{[\s\S]*\}", cleaned)
                    if m:
                        try:
                            parsed = _json.loads(m.group(0))
                        except Exception:
                            parsed = None
            except Exception as e:
                print(f"  [llm] {item.source}:{item.title[:30]}... {type(e).__name__}: {str(e)[:60]}")

            if not parsed:
                parsed = {
                    "summary": fallback_summary,
                    "key_points": [],
                    "category": "其他",
                    "category_l1": "其他",
                    "relevance": 0.5,
                }

            summary_text = (parsed.get("summary") or "").strip()
            if not summary_text or len(summary_text) < 10:
                summary_text = fallback_summary

            # title_zh: 优先使用 LLM 翻译的中文标题
            title_zh = (parsed.get("title_zh") or "").strip()
            original_title = item.title
            title_translated = False
            if title_zh and len(title_zh) >= 2:
                # LLM 给了中文翻译，用它作为主标题
                final_title = title_zh
                title_translated = (title_zh != original_title)
            else:
                final_title = original_title

            from taxonomy import normalize_l1
            cat_l1 = parsed.get("category_l1") or normalize_l1(parsed.get("category"))
            if cat_l1 not in ("科技","AI","体育","娱乐","财经","汽车","其他"):
                cat_l1 = normalize_l1(parsed.get("category")) or "其他"

            doc = {
                "url_hash": item.id, "id": item.id,
                "source": item.source, "source_url": item.source_url, "url": item.url,
                "title": final_title, "title_original": original_title, "title_hash": item.title_hash,
                "title_translated": title_translated,
                "published_at": item.published_at, "fetched_at": item.fetched_at,
                "author": item.author, "tags": item.tags, "language": item.language,
                "summary": summary_text,
                "key_points": parsed.get("key_points", []) or [],
                "category": parsed.get("category", "其他") or "其他",
                "category_l1": cat_l1,
                "relevance": float(parsed.get("relevance", 0.5) or 0.5),
                "summary_model": "fallback" if not parsed.get("summary_model") else parsed.get("summary_model"),
                "summary_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await upsert_item_async(doc)
                completed += 1
            except Exception:
                failed += 1

    await asyncio.gather(*[one(it) for it in new_items])
    await registry.aclose()
    print(f"  done: {completed} ok, {failed} failed")

    # 写 task_runs(管理员页面用)
    finished_at = datetime.now(timezone.utc)
    per_source: dict = {}
    for it in items:
        per_source.setdefault(it.source, {
            "fetched": 0, "summarized": 0, "errors": 0, "latency_ms": 0,
        })
        per_source[it.source]["fetched"] += 1
    # 统计每个源的摘要成功/失败数
    new_items_set = {it.id: it.source for it in new_items}
    done_set = set(done)
    # 从 completed/failed 反推各源(简化:按 new_items 中各源的比例分配,近似)
    per_source_success: dict = {}
    per_source_fail: dict = {}
    for it in new_items:
        per_source_success.setdefault(it.source, 0)
        per_source_fail.setdefault(it.source, 0)
    # 用 completed 和 failed 按比例分配(简化版,后续可精细化)
    total_new = len(new_items)
    if total_new > 0:
        for src in per_source_success:
            src_new = sum(1 for it in new_items if it.source == src)
            ratio = src_new / total_new
            per_source[src]["summarized"] = int(completed * ratio)
            per_source[src]["errors"] = int(failed * ratio)
    warning = ""
    if completed == 0 and failed > 0:
        warning = f"全部 {failed} 条 LLM 摘要失败(查 daemon 日志)"
    try:
        update_task_run_finished(run_id, {
            "finished_at": finished_at,
            "status": "done",
            "items_fetched": len(items),
            "items_summarized": completed,
            "items_failed": failed,
            "per_source": per_source,
            "warning": warning,
        })
    except Exception as e:
        print(f"  ⚠ update_task_run_finished 失败(忽略): {e}")
    return {
        "fetched": len(items),
        "new": len(new_items),
        "summarized": completed,
        "failed": failed,
        "warning": warning,
    }


def log_line(msg: str, log_file: Path):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n"
    print(line, end="")
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=1800, help="轮询间隔(秒)")
    parser.add_argument("--limit", type=int, default=8, help="每源抓多少条")
    parser.add_argument("--once", action="store_true", help="只跑一次退出")
    parser.add_argument("--log", default="data/ingest-daemon.log", help="日志文件")
    args = parser.parse_args()

    log_file = Path(args.log)

    if args.once:
        try:
            r = await run_once(args)
            print(f"\n✓ ingest 一次完成,新增 {r['summarized']} 条")
            if r.get("warning"):
                print(f"  ⚠ warning: {r['warning']}")
        except Exception as e:
            log_line(f"✗ ingest error: {e}\n{traceback.format_exc()}", log_file)
            sys.exit(1)
        return

    log_line(f"daemon started, interval={args.interval}s, limit={args.limit}", log_file)
    while True:
        try:
            await run_once(args)
        except Exception as e:
            log_line(f"✗ ingest error: {e}", log_file)
            log_line(traceback.format_exc(), log_file)
        log_line(f"sleeping {args.interval}s", log_file)
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())