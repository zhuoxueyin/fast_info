"""
fastInfo · 初始化 banner_config / task_runs 集合
================================================

跑法(只需要跑一次):
    python scripts/init_admin_collections.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from datetime import datetime, timezone
from storage.mongo_writer import (
    ensure_indexes, get_banner, DEFAULT_DB, get_db,
)


def init_banner():
    banner = get_banner()
    print(f"  ✓ banner_config: {banner}")


def init_task_runs_index():
    db = get_db()
    runs = db["task_runs"]
    print(f"  task_runs 当前条数: {runs.count_documents({})}")


def main():
    print("== fastInfo Day 3 集合初始化 ==")
    print("[1] ensure_indexes ...")
    ensure_indexes()
    print("[2] banner_config ...")
    init_banner()
    print("[3] task_runs ...")
    init_task_runs_index()
    print("\n✓ 完成")


if __name__ == "__main__":
    main()