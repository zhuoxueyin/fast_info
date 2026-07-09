"""
Backfill items.category_l1 based on the latest taxonomy mapping.

Usage:
    python scripts/backfill_category_l1.py [--dry-run]
"""
from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.mongo_writer import get_db
from taxonomy import normalize_l1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()

    db = get_db()
    coll = db["items"]
    total = 0
    updated = 0
    skipped = 0

    for doc in coll.find({}, {"category": 1, "category_l1": 1, "title": 1, "summary": 1}):
        total += 1
        category = doc.get("category") or ""
        text = f"{doc.get('title', '')} {doc.get('summary', '')}"
        new_l1 = normalize_l1(category, text)
        old_l1 = doc.get("category_l1") or "其他"
        if new_l1 == old_l1:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry] {doc['_id']} {old_l1} -> {new_l1} | category={category} | {doc.get('title', '')[:30]}")
            updated += 1
            continue
        coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"category_l1": new_l1, "category_l1_backfilled": True}},
        )
        updated += 1
        print(f"[upd] {doc['_id']} {old_l1} -> {new_l1} | {doc.get('title', '')[:30]}")

    print(f"\nDone. total={total} updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
