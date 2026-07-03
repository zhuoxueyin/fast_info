"""Day 5 · 一次性迁移 + 种子脚本

把代码里 RSS_SOURCES / KOL_SOURCES 注入 MongoDB source_config collection,
老 global 文档不动(保留作 fallback)。

用法:
    python scripts/migrate_source_config.py            # 新建缺失条目
    python scripts/migrate_source_config.py --reset    # 清空重建
    python scripts/migrate_source_config.py --list     # 仅展示当前状态
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storage.mongo_writer import ensure_indexes, get_db
from storage.source_runs import ensure_indexes as ensure_runs_indexes
from storage.source_config import (
    seed_from_registry, ensure_indexes as ensure_sc_indexes,
    list_sources, load_enabled_sources,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="清空并重建 source_config")
    parser.add_argument("--list", action="store_true", help="列出当前 source_config")
    args = parser.parse_args()

    if args.list:
        sources = list_sources()
        print(f"\n  · source_config 当前 {len(sources)} 条")
        for s in sources:
            print(f"    [{s.get('kind','?'):<10}] {s['source_id']:<25} "
                  f"l1={s.get('l1','-'):<4} active={s.get('is_active')} "
                  f"name={s.get('display_name','-')}")
        enabled = load_enabled_sources()
        print(f"\n  · 启用集合: {sorted(enabled) if enabled else '(all)'}")
        return

    if args.reset:
        n = get_db()["source_config"].delete_many({}).deleted_count
        print(f"  ⚠️  删除了 {n} 条 source_config 文档")

    print("  · 确保索引 ...")
    ensure_indexes()
    ensure_runs_indexes()
    ensure_sc_indexes()

    print("  · 从代码注册表 seed ...")
    created = seed_from_registry()
    print(f"  ✓ 新建 {created} 条 source_config")

    if created == 0 and not args.reset:
        print("  (已存在的不会覆盖)")

    print()
    print("  验证:")
    sources = list_sources()
    print(f"    总计 {len(sources)} 条;启用 {len([s for s in sources if s.get('is_active')])} 条")


if __name__ == "__main__":
    main()
