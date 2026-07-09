"""
fastInfo · 后台抓取守护进程
================================

设计:独立进程,跟 CLI / 订阅 / API 解耦。

Day 1-Day 9:固定 interval,默认 30 分钟全量跑一次
Day 10.5:升级为按 source_config.cron_interval_seconds 调度
    - 每源独立的 cron 节奏
    - daemon tick = 60s,到期才跑(支持 0 = 手动)
    - 读 ingest_schedule.py 的 compute_due_sources

跑法:
    python scripts/ingest_daemon.py                    # 默认调度器模式,tick 60s
    python scripts/ingest_daemon.py --legacy           # 老模式:每 30 min 全量
    python scripts/ingest_daemon.py --once             # 单次跑全量(测试)
    python scripts/ingest_daemon.py --once --sources huxiu,weibo_hot  # 单次跑指定源
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

# === Windows GBK 兜底 ===
for _stream in (sys.stdout, sys.stderr):
    try:
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 加载 .env
from _env import load_env
load_env()


# ============================================================
# 单源抓取 + LLM 摘要 + 入库(独立任务)
# ============================================================

async def run_source(source_id: str, limit: int, task_run_id: str, trigger: str) -> dict:
    """跑单个源 — 抓 + LLM 摘要 + 入库。

    返回 {fetched, summarized, failed, warning}
    source_runs 由 fetch_one 内的 record_source_run 自动写。
    """
    from crawler.collectors import fetch_one_source
    from storage.mongo_writer import (
        get_done_urls, get_recent_title_hashes,
    )
    from llm.model_registry import build_default_registry
    import re as _re, json as _json

    started_at = datetime.now(timezone.utc)
    empty = lambda w="": {"fetched": 0, "summarized": 0, "failed": 0, "warning": w}

    items = await fetch_one_source(source_id, limit=limit, task_run_id=task_run_id)
    if not items:
        return empty("没有新内容(可能全部已抓过或源返回空)")

    done = get_done_urls()
    recent_titles = get_recent_title_hashes(days=7)
    new_items = [it for it in items if it.id not in done]
    new_items = [it for it in new_items if not it.title_hash or it.title_hash not in recent_titles]

    if not new_items:
        return empty("没有新内容(全部已抓过)")

    if not os.environ.get("MMX_API_KEY") and not os.environ.get("KIMI_API_KEY"):
        return empty("MMX_API_KEY / KIMI_API_KEY 都未配置")

    from storage.mongo_writer import upsert_item_async
    from taxonomy import normalize_l1

    registry = build_default_registry()
    sem = asyncio.Semaphore(3)
    completed = 0
    failed = 0

    system_prompt = (
        "你是 fastInfo 的中文资讯分类编辑。请根据文章标题和摘要，输出严格 JSON（无 markdown 包裹，无多余文字）：\n"
        '{"title_zh": "中文标题(若原标题已是中文则与原标题一致;若为英文必须翻译成简洁中文,实体名/队名/球员名可保留英文,≤30字)", '
        '"summary": "120-180字中文摘要，信息完整，不空洞", "key_points": ["要点1","要点2","要点3"], '
        '"category": "二级分类(如大模型/AI芯片/新能源/自动驾驶/A股/影视/游戏等)", '
        '"category_l1": "一级分类，必须是：科技/AI/体育/娱乐/财经/汽车/其他 之一", '
        '"relevance": 0.0-10.0热度分}\n\n'
        "一级分类定义（按主题内容选最贴切的一个，不要只看是否提到融资/股价）：\n"
        "- 科技：互联网、软件、硬件、芯片/半导体/CPU/GPU、通信/5G、消费电子、物联网、云计算/SaaS、开源、网络安全、量子计算、航空/航天、无人机、VR/AR、元宇宙、生物科技、工业互联网等产业动态\n"
        "- AI：人工智能、大模型、AIGC、Agent/智能体、AI芯片、AI应用、具身智能、多模态、NLP、计算机视觉、ChatGPT/GPT/LLM/Claude/Gemini/DeepSeek等\n"
        "- 体育：足球、篮球、电竞(LOL/DOTA/王者/CSGO)、NBA/CBA、世界杯、欧冠、奥运会、F1、马拉松、网球、乒乓球、羽毛球等\n"
        "- 娱乐：影视、音乐、明星、综艺、动漫/动画/漫画/二次元、游戏、直播、短视频、美食、旅游、时尚、艺术、文化等\n"
        "- 财经：股市/IPO/上市、融资（仅当文章核心是投资/交易而非科技产品）、A股/港股/美股/中概股、基金/债券、宏观/央行/GDP/CPI/降息/加息、银行/保险/房地产、比特币/以太坊/区块链/加密货币/币圈、创业/VC/PE/财报/并购等\n"
        "- 汽车：汽车、新能源车/电动车、自动驾驶/智能驾驶、新势力(小米SU7/比亚迪/特斯拉/蔚来/小鹏/理想等)、传统车企、电池/充电/充电桩等\n"
        "- 其他：社会、教育、健康、生活等不属于以上 6 类的内容\n\n"
        "规则：category_l1 必须从给定列表中选；若文章是科技/AI 产品或产业新闻，即使提到融资也应优先归为科技/AI；summary 必须有实质内容；title_zh 必须输出。"
    )

    async def one(item):
        nonlocal completed, failed
        async with sem:
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

            title_zh = (parsed.get("title_zh") or "").strip()
            original_title = item.title
            title_translated = False
            if title_zh and len(title_zh) >= 2:
                final_title = title_zh
                title_translated = (title_zh != original_title)
            else:
                final_title = original_title

            raw_l1 = parsed.get("category_l1")
            raw_cat = parsed.get("category")
            text_hint = f"{final_title} {summary_text}"
            cat_l1 = raw_l1 if raw_l1 in ("科技","AI","体育","娱乐","财经","汽车","其他") else ""
            # LLM 给的"其他"可能只是不会分；用 category + 标题/摘要再兜一次底
            if not cat_l1 or cat_l1 == "其他":
                inferred = normalize_l1(raw_cat, text=text_hint)
                if inferred != "其他":
                    cat_l1 = inferred
            if cat_l1 not in ("科技","AI","体育","娱乐","财经","汽车","其他"):
                cat_l1 = "其他"

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
                "summary_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await upsert_item_async(doc)
                completed += 1
            except Exception:
                failed += 1

    await asyncio.gather(*[one(it) for it in new_items])
    await registry.aclose()

    warning = ""
    if completed == 0 and failed > 0:
        warning = f"全部 {failed} 条 LLM 摘要失败"
    elif completed > 0 and failed > 0:
        warning = f"部分失败:成功 {completed} / 失败 {failed}"

    return {
        "fetched": len(items),
        "summarized": completed,
        "failed": failed,
        "warning": warning,
    }


async def run_due_sources(due_sources: list[str], args) -> dict:
    """按 due 源列表逐源跑,共用一条 task_run。"""
    import uuid
    from storage.mongo_writer import (
        create_task_run_pending, update_task_run_finished,
    )

    run_id = getattr(args, "run_id", None) or str(uuid.uuid4())
    trigger = getattr(args, "trigger", "scheduled")
    operator = getattr(args, "operator", None)

    started_at = datetime.now(timezone.utc)
    print(f"[{started_at.isoformat()}] ingest start (scheduler, due={len(due_sources)}) run_id={run_id} trigger={trigger}")

    try:
        create_task_run_pending({
            "run_id": run_id,
            "started_at": started_at,
            "trigger": trigger,
            "operator": operator,
            "limit": args.limit,
            "mode": "scheduler",
            "due_sources": due_sources,
        })
    except Exception as e:
        print(f"  [warn] create_task_run_pending failed: {e}")

    total_fetched = 0
    total_summarized = 0
    total_failed = 0
    per_source: dict = {}
    warnings: list[str] = []

    for sid in due_sources:
        try:
            r = await run_source(sid, limit=args.limit, task_run_id=run_id, trigger=trigger)
            total_fetched += r.get("fetched", 0)
            total_summarized += r.get("summarized", 0)
            total_failed += r.get("failed", 0)
            per_source[sid] = {
                "fetched": r.get("fetched", 0),
                "summarized": r.get("summarized", 0),
                "errors": r.get("failed", 0),
            }
            w = r.get("warning")
            if w:
                warnings.append(f"{sid}: {w}")
        except Exception as e:
            total_failed += 1
            per_source[sid] = {"fetched": 0, "summarized": 0, "errors": 1}
            warnings.append(f"{sid}: {type(e).__name__}: {str(e)[:100]}")

    finished_at = datetime.now(timezone.utc)
    final_status = "done"
    if total_summarized == 0 and total_failed > 0:
        final_status = "failed"
    elif total_summarized > 0 and total_failed > 0:
        final_status = "partial"

    try:
        update_task_run_finished(run_id, {
            "finished_at": finished_at,
            "status": final_status,
            "items_fetched": total_fetched,
            "items_summarized": total_summarized,
            "items_failed": total_failed,
            "per_source": per_source,
            "warning": "; ".join(warnings) if warnings else "",
        })
    except Exception as e:
        print(f"  [warn] update_task_run_finished failed: {e}")

    return {
        "run_id": run_id,
        "status": final_status,
        "fetched": total_fetched,
        "summarized": total_summarized,
        "failed": total_failed,
        "sources_ran": len(due_sources),
    }


async def run_legacy(args) -> dict:
    """Day 1-Day 9 老模式:全量 fetch_all,保留兼容(给 --legacy 用)"""
    import uuid
    from crawler.collectors import fetch_all
    from storage.mongo_writer import (
        upsert_item_async, get_done_urls, get_recent_title_hashes,
        ensure_indexes, create_task_run_pending, update_task_run_finished,
    )
    from llm.model_registry import build_default_registry
    import re as _re, json as _json

    run_id = getattr(args, "run_id", None) or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    trigger = getattr(args, "trigger", "scheduled")

    empty = lambda w="": {"fetched": 0, "summarized": 0, "failed": 0, "warning": w}
    print(f"[{started_at.isoformat()}] ingest start (legacy full, limit={args.limit}) run_id={run_id}")

    try:
        ensure_indexes()
        create_task_run_pending({
            "run_id": run_id, "started_at": started_at,
            "trigger": trigger, "operator": getattr(args, "operator", None),
            "limit": args.limit, "mode": "legacy_full",
        })
    except Exception:
        pass

    done = get_done_urls()
    recent_titles = get_recent_title_hashes(days=7)

    items = await fetch_all(limit_per_source=args.limit, task_run_id=run_id)
    new_items = [it for it in items if it.id not in done]
    new_items = [it for it in new_items if not it.title_hash or it.title_hash not in recent_titles]

    if not new_items:
        update_task_run_finished(run_id, {
            "finished_at": datetime.now(timezone.utc), "status": "done",
            "items_fetched": len(items), "items_summarized": 0, "items_failed": 0,
            "warning": "没有新内容",
        })
        return empty("没有新内容")

    if not os.environ.get("MMX_API_KEY") and not os.environ.get("KIMI_API_KEY"):
        update_task_run_finished(run_id, {
            "finished_at": datetime.now(timezone.utc), "status": "failed",
            "items_fetched": len(items), "items_failed": len(new_items),
            "warning": "API keys 都未配置",
        })
        return empty("API keys 未配置")

    from taxonomy import normalize_l1
    registry = build_default_registry()
    sem = asyncio.Semaphore(3)
    completed = 0
    failed = 0

    system_prompt = (
        "你是 fastInfo 的中文资讯分类编辑。请根据文章标题和摘要，输出严格 JSON（无 markdown 包裹，无多余文字）：\n"
        '{"title_zh": "中文标题(若原标题已是中文则与原标题一致;若为英文必须翻译成简洁中文,实体名/队名/球员名可保留英文,≤30字)", '
        '"summary": "120-180字中文摘要，信息完整，不空洞", "key_points": ["要点1","要点2","要点3"], '
        '"category": "二级分类(如大模型/AI芯片/新能源/自动驾驶/A股/影视/游戏等)", '
        '"category_l1": "一级分类，必须是：科技/AI/体育/娱乐/财经/汽车/其他 之一", '
        '"relevance": 0.0-10.0热度分}\n\n'
        "一级分类定义（按主题内容选最贴切的一个，不要只看是否提到融资/股价）：\n"
        "- 科技：互联网、软件、硬件、芯片/半导体/CPU/GPU、通信/5G、消费电子、物联网、云计算/SaaS、开源、网络安全、量子计算、航空/航天、无人机、VR/AR、元宇宙、生物科技、工业互联网等产业动态\n"
        "- AI：人工智能、大模型、AIGC、Agent/智能体、AI芯片、AI应用、具身智能、多模态、NLP、计算机视觉、ChatGPT/GPT/LLM/Claude/Gemini/DeepSeek等\n"
        "- 体育：足球、篮球、电竞(LOL/DOTA/王者/CSGO)、NBA/CBA、世界杯、欧冠、奥运会、F1、马拉松、网球、乒乓球、羽毛球等\n"
        "- 娱乐：影视、音乐、明星、综艺、动漫/动画/漫画/二次元、游戏、直播、短视频、美食、旅游、时尚、艺术、文化等\n"
        "- 财经：股市/IPO/上市、融资（仅当文章核心是投资/交易而非科技产品）、A股/港股/美股/中概股、基金/债券、宏观/央行/GDP/CPI/降息/加息、银行/保险/房地产、比特币/以太坊/区块链/加密货币/币圈、创业/VC/PE/财报/并购等\n"
        "- 汽车：汽车、新能源车/电动车、自动驾驶/智能驾驶、新势力(小米SU7/比亚迪/特斯拉/蔚来/小鹏/理想等)、传统车企、电池/充电/充电桩等\n"
        "- 其他：社会、教育、健康、生活等不属于以上 6 类的内容\n\n"
        "规则：category_l1 必须从给定列表中选；若文章是科技/AI 产品或产业新闻，即使提到融资也应优先归为科技/AI；summary 必须有实质内容；title_zh 必须输出。"
    )

    async def one(item):
        nonlocal completed, failed
        async with sem:
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
            except Exception:
                parsed = None
            if not parsed:
                parsed = {"summary": fallback_summary, "key_points": [], "category": "其他", "category_l1": "其他", "relevance": 0.5}
            summary_text = (parsed.get("summary") or "").strip() or fallback_summary
            title_zh = (parsed.get("title_zh") or "").strip()
            final_title = title_zh if (title_zh and len(title_zh) >= 2) else item.title
            raw_l1 = parsed.get("category_l1")
            raw_cat = parsed.get("category")
            text_hint = f"{final_title} {summary_text}"
            cat_l1 = raw_l1 if raw_l1 in ("科技","AI","体育","娱乐","财经","汽车","其他") else ""
            # LLM 给的"其他"可能只是不会分；用 category + 标题/摘要再兜一次底
            if not cat_l1 or cat_l1 == "其他":
                inferred = normalize_l1(raw_cat, text=text_hint)
                if inferred != "其他":
                    cat_l1 = inferred
            if cat_l1 not in ("科技","AI","体育","娱乐","财经","汽车","其他"):
                cat_l1 = "其他"
            doc = {
                "url_hash": item.id, "id": item.id,
                "source": item.source, "source_url": item.source_url, "url": item.url,
                "title": final_title, "title_original": item.title, "title_hash": item.title_hash,
                "title_translated": (final_title != item.title),
                "published_at": item.published_at, "fetched_at": item.fetched_at,
                "author": item.author, "tags": item.tags, "language": item.language,
                "summary": summary_text,
                "key_points": parsed.get("key_points", []) or [],
                "category": parsed.get("category", "其他") or "其他",
                "category_l1": cat_l1,
                "relevance": float(parsed.get("relevance", 0.5) or 0.5),
                "summary_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await upsert_item_async(doc)
                completed += 1
            except Exception:
                failed += 1

    await asyncio.gather(*[one(it) for it in new_items])
    await registry.aclose()

    per_source: dict = {}
    for it in items:
        per_source.setdefault(it.source, {"fetched": 0, "summarized": 0, "errors": 0})
        per_source[it.source]["fetched"] += 1

    final_status = "partial" if (completed > 0 and failed > 0) else ("done" if completed > 0 else "failed")
    update_task_run_finished(run_id, {
        "finished_at": datetime.now(timezone.utc),
        "status": final_status,
        "items_fetched": len(items),
        "items_summarized": completed,
        "items_failed": failed,
        "per_source": per_source,
        "warning": "; ".join(warnings) if 'warnings' in dir() else "",
    })

    return {
        "run_id": run_id, "status": final_status,
        "fetched": len(items), "summarized": completed, "failed": failed,
    }


def log_line(msg: str, log_file: Path):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n"
    try:
        print(line, end="")
    except (UnicodeEncodeError, OSError):
        try:
            sys.stdout.write(line.encode("utf-8", "replace").decode("ascii", "replace"))
        except Exception:
            pass
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


async def scheduler_loop(args, log_file: Path):
    """调度器主循环(Day 10.5 默认)。

    - tick_interval(默认 60s)检查一次
    - 读 source_config + source_runs,算出 due 源
    - 到期的跑(走 run_due_sources),共用一条 task_run
    - 没源 due,啥都不写
    """
    from storage.ingest_schedule import compute_due_sources, pick_due_sources

    log_line(f"scheduler started, tick={args.tick_interval}s, limit={args.limit}", log_file)

    while True:
        try:
            now = datetime.now(timezone.utc)
            schedule = compute_due_sources(now=now)
            due = pick_due_sources(schedule, now=now)
            if due:
                log_line(f"due {len(due)} sources: {','.join(due)}", log_file)
                r = await run_due_sources(due, args)
                log_line(f"  -> status={r['status']} fetched={r['fetched']} summarized={r['summarized']} failed={r['failed']}", log_file)
        except Exception as e:
            log_line(f"tick err: {e}", log_file)
            log_line(traceback.format_exc(), log_file)
        await asyncio.sleep(args.tick_interval)


async def legacy_loop(args, log_file: Path):
    """老模式:每 interval 全量跑一次(给不想用调度器的用户保留)"""
    log_line(f"legacy daemon started, interval={args.interval}s, limit={args.limit}", log_file)
    while True:
        try:
            r = await run_legacy(args)
            log_line(f"  -> status={r.get('status')} fetched={r.get('fetched')} summarized={r.get('summarized')}", log_file)
        except Exception as e:
            log_line(f"ingest error: {e}", log_file)
            log_line(traceback.format_exc(), log_file)
        await asyncio.sleep(args.interval)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=1800, help="[legacy] 全量跑间隔秒")
    parser.add_argument("--tick-interval", type=int, default=60, help="[scheduler] 检查间隔秒(默认 60s)")
    parser.add_argument("--limit", type=int, default=8, help="每源抓多少条")
    parser.add_argument("--once", action="store_true", help="只跑一次退出")
    parser.add_argument("--sources", type=str, default=None, help="[--once 时用] 指定 source_ids,逗号分隔")
    parser.add_argument("--legacy", action="store_true", help="用老模式(全量每 interval 跑)")
    parser.add_argument("--log", default="data/ingest-daemon.log", help="日志文件")
    args = parser.parse_args()

    log_file = Path(args.log)

    if args.once:
        if args.sources:
            due = [s.strip() for s in args.sources.split(",") if s.strip()]
            print(f"[once] running specified sources: {due}")
            r = await run_due_sources(due, args)
            print(f"\n  status={r['status']} fetched={r['fetched']} summarized={r['summarized']}")
        elif args.legacy:
            r = await run_legacy(args)
            print(f"\n  [legacy] status={r.get('status')} fetched={r.get('fetched')} summarized={r.get('summarized')}")
        else:
            # 默认 --once 走调度器:列出所有 due 源并跑
            from storage.ingest_schedule import compute_due_sources, pick_due_sources
            schedule = compute_due_sources()
            due = pick_due_sources(schedule)
            print(f"[once-scheduler] due sources: {due}")
            if not due:
                print("[once-scheduler] no due sources, nothing to do")
                return
            r = await run_due_sources(due, args)
            print(f"\n  status={r['status']} fetched={r['fetched']} summarized={r['summarized']}")
        return

    if args.legacy:
        await legacy_loop(args, log_file)
    else:
        await scheduler_loop(args, log_file)


if __name__ == "__main__":
    asyncio.run(main())