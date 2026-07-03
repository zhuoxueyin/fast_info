"""Day 5 · 源管理 CLI (调试 + 不开 admin 后台时的 fallback)

用法:
    python scripts/admin_sources.py list
    python scripts/admin_sources.py show <source_id>
    python scripts/admin_sources.py toggle <source_id>
    python scripts/admin_sources.py add <source_id> <kind> <name> <url>
    python scripts/admin_sources.py health
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storage.source_config import (
    list_sources, get_source, toggle_source, upsert_source,
)
from storage.source_runs import get_overall_health, get_recent_runs


def cmd_list(args):
    sources = list_sources()
    print(f"\n  · {len(sources)} 条 source_config:\n")
    for s in sources:
        print(f"  [{s.get('kind','?'):<12}] {s['source_id']:<25} "
              f"l1={s.get('l1','-'):<4} active={'✓' if s.get('is_active') else '✗'} "
              f"name={s.get('display_name','-')}")
        if s.get("consecutive_fails", 0) > 0:
            print(f"    ⚠ 连续失败 {s.get('consecutive_fails')} 次 / 阈值 {s.get('auto_disable_threshold')}")
        if s.get("disabled_reason"):
            print(f"    🚫 {s['disabled_reason']}")


def cmd_show(args):
    s = get_source(args.source_id)
    if not s:
        print(f"  ✗ {args.source_id} 不存在")
        return
    print(f"\n  source_id : {s['source_id']}")
    print(f"  kind      : {s.get('kind')}")
    print(f"  name      : {s.get('display_name')}")
    print(f"  url       : {s.get('url')}")
    print(f"  l1        : {s.get('l1')}")
    print(f"  tags      : {s.get('tags')}")
    print(f"  is_active : {s.get('is_active')}")
    print(f"  cron(s)   : {s.get('cron_interval_seconds')}")
    print(f"  limit     : {s.get('limit_per_run')}")
    print(f"  threshold : {s.get('auto_disable_threshold')}")
    print(f"  consecutive_fails : {s.get('consecutive_fails', 0)}")
    print(f"  last_success_at   : {s.get('last_success_at')}")
    print(f"  last_fail_at      : {s.get('last_fail_at')}")
    if s.get("disabled_reason"):
        print(f"  disabled_reason   : {s['disabled_reason']}")
    print()


def cmd_toggle(args):
    state = toggle_source(args.source_id)
    if state is None:
        print(f"  ✗ {args.source_id} 不存在")
    else:
        print(f"  {'✓ 启用' if state else '✗ 禁用'} {args.source_id}")


def cmd_add(args):
    doc = {
        "source_id": args.source_id,
        "kind": args.kind,
        "display_name": args.name,
        "url": args.url,
        "urls": [args.url],
        "is_active": True,
        "limit_per_run": args.limit,
        "auto_disable_threshold": 5,
    }
    upsert_source(doc)
    print(f"  ✓ 新增 {args.source_id}")


def cmd_health(args):
    rows = get_overall_health(window_days=args.window)
    print(f"\n  · 全平台健康度(过去 {args.window} 天):\n")
    for r in rows:
        ok = r["ok_runs"]
        fail = r["fail_runs"]
        sr = r["success_rate"]
        sr_str = f"{sr:.0%}" if sr is not None else "—"
        print(f"  [{r.get('kind','?'):<11}] {r['source_id']:<22} "
              f"✓{ok} ✗{fail} sr={sr_str} "
              f"avg={r.get('avg_duration_ms') or '—'}ms "
              f"new={r.get('total_new',0)} "
              f"fail={r.get('consecutive_fails',0)}/thr={r.get('auto_disable_threshold')}")


def cmd_runs(args):
    runs = get_recent_runs(source_id=args.source_id, limit=args.limit)
    print(f"\n  · 最近 {len(runs)} 条 source_runs"
          + (f" for {args.source_id}" if args.source_id else "") + ":\n")
    for r in runs:
        print(f"  {r.get('created_at','-')[:19]} "
              f"{r.get('source_id','?'):<20} "
              f"{r.get('status','?'):<8} "
              f"({r.get('duration_ms',0)}ms) "
              f"fetched={r.get('fetched_count',0)} "
              f"err={r.get('error_code') or '-'} "
              f"msg={(r.get('error_msg') or '')[:40]}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show")
    p.add_argument("source_id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("toggle")
    p.add_argument("source_id")
    p.set_defaults(func=cmd_toggle)

    p = sub.add_parser("add")
    p.add_argument("source_id")
    p.add_argument("kind")
    p.add_argument("name")
    p.add_argument("url")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("health")
    p.add_argument("--window", type=int, default=1)
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("runs")
    p.add_argument("--source-id")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_runs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
