from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.subs_scheduler import should_run_now
from subscription import compute_next_run_at


def test_should_not_run_before_next_run_at_for_cron_sub():
    sub = {
        "title": "AI daily",
        "is_active": True,
        "cron_expr": "0 9 * * *",
        "interval_min": 0,
        "created_at": "2026-07-05T00:00:00+00:00",
        "next_run_at": "2026-07-05T09:00:00+00:00",
        "last_run_at": None,
    }
    now = datetime(2026, 7, 5, 4, 30, tzinfo=timezone.utc)
    assert should_run_now(sub, now) is False


def test_should_run_when_next_run_at_is_due():
    sub = {
        "title": "AI daily",
        "is_active": True,
        "cron_expr": "0 9 * * *",
        "interval_min": 0,
        "created_at": "2026-07-05T00:00:00+00:00",
        "next_run_at": "2026-07-05T09:00:00+00:00",
        "last_run_at": None,
    }
    now = datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc)
    assert should_run_now(sub, now) is True


def test_should_fallback_to_last_run_and_cron_when_next_run_missing():
    sub = {
        "title": "AI daily",
        "is_active": True,
        "cron_expr": "0 9 * * *",
        "interval_min": 0,
        "created_at": "2026-07-05T00:00:00+00:00",
        "last_run_at": "2026-07-05T03:30:00+00:00",
    }
    before_due = datetime(2026, 7, 5, 8, 59, tzinfo=timezone.utc)
    on_due = datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc)
    assert should_run_now(sub, before_due) is False
    assert should_run_now(sub, on_due) is True


def test_compute_next_run_at_respects_interval_min():
    sub = {
        "interval_min": 45,
        "cron_expr": "0 9 * * *",
    }
    base = datetime(2026, 7, 5, 4, 0, tzinfo=timezone.utc)
    assert compute_next_run_at(sub, base) == datetime(2026, 7, 5, 4, 45, tzinfo=timezone.utc)
