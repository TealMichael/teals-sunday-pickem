from datetime import datetime, timedelta, timezone
from pathlib import Path

from automation_recovery import recovery_action_due

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


class FakeStore:
    def __init__(self, success=None, latest=None):
        self.success = success or {}
        self.latest = latest or {}

    def last_successful_run(self, run_type, *, week_id=None):
        return self.success.get(run_type)

    def latest_data_run(self, run_type, *, week_id=None):
        return self.latest.get(run_type)


def stamp(dt):
    return dt.astimezone(UTC).isoformat()


def base_week(lock):
    return {
        "id": "week-1",
        "is_demo": False,
        "published_at": stamp(lock - timedelta(days=5)),
        "opens_at": stamp(lock - timedelta(days=5, hours=1)),
        "locks_at": stamp(lock),
        "data_status": "POOL_READY",
    }


def test_sunday_prelock_recovery_only_after_scheduler_grace():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)  # 1 PM ET
    now = lock - timedelta(minutes=60)
    fresh = {"injury_refresh": {"completed_at": stamp(now - timedelta(minutes=16)), "success": True}}
    stale = {"injury_refresh": {"completed_at": stamp(now - timedelta(minutes=18)), "success": True}}
    fresh_week = base_week(lock)
    fresh_week["last_data_refresh_at"] = stamp(now - timedelta(minutes=16))
    stale_week = base_week(lock)
    stale_week["last_data_refresh_at"] = stamp(now - timedelta(minutes=18))
    assert recovery_action_due(FakeStore(success=fresh), fresh_week, now=now) is None
    assert recovery_action_due(FakeStore(success=stale), stale_week, now=now) == "injury"


def test_live_recovery_arms_after_17_minutes_and_not_before_lock():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    now = lock + timedelta(hours=2)
    week = base_week(lock)
    week["data_status"] = "LIVE"
    week["last_data_refresh_at"] = stamp(now - timedelta(minutes=18))
    stale = {"live_scores": {"completed_at": stamp(now - timedelta(minutes=18)), "success": True}}
    assert recovery_action_due(FakeStore(success=stale), week, now=now) == "live"
    assert recovery_action_due(FakeStore(success=stale), week, now=lock - timedelta(seconds=1)) != "live"



class NoQueryStore:
    def last_successful_run(self, *args, **kwargs):
        raise AssertionError("fresh fast path should not query run history")

    def latest_data_run(self, *args, **kwargs):
        raise AssertionError("fresh fast path should not query run history")


def test_fresh_live_week_uses_loaded_week_stamp_without_extra_run_history_query():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    now = lock + timedelta(hours=1)
    week = base_week(lock)
    week["data_status"] = "LIVE"
    week["last_data_refresh_at"] = stamp(now - timedelta(minutes=4))
    assert recovery_action_due(NoQueryStore(), week, now=now) is None

def test_recent_failed_attempt_is_cooled_down():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    now = lock + timedelta(hours=1)
    week = base_week(lock)
    latest = {"live_scores": {"started_at": stamp(now - timedelta(minutes=2)), "success": False}}
    assert recovery_action_due(FakeStore(latest=latest), week, now=now) is None


def test_delayed_tuesday_publication_can_be_recovered_after_ten_minutes():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    opens = datetime(2026, 9, 8, 16, 0, tzinfo=UTC)  # Tuesday noon ET
    week = base_week(lock)
    week["published_at"] = None
    week["opens_at"] = stamp(opens)
    assert recovery_action_due(FakeStore(), week, now=opens + timedelta(minutes=9)) is None
    assert recovery_action_due(FakeStore(), week, now=opens + timedelta(minutes=10)) == "publish"


def test_lease_schema_is_server_only_and_runtime_has_recovery_hooks():
    sql = (ROOT / "db/005_automation_hardening.sql").read_text("utf-8")
    assert "create table if not exists pickem.refresh_leases" in sql
    assert "primary key" in sql
    assert "revoke all on table pickem.refresh_leases from anon, authenticated" in sql
    assert "grant all on table pickem.refresh_leases to service_role" in sql

    store = (ROOT / "store.py").read_text("utf-8")
    assert "def claim_refresh_lease" in store
    assert "def release_refresh_lease" in store
    assert "def latest_data_run" in store

    ui = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert "maybe_recover_critical_automation(store, week)" in ui
    assert "Sunday tab only" in ui

    recovery = (ROOT / "automation_recovery.py").read_text("utf-8")
    assert "ensure_week_shell_from_scoreboard" in recovery
    assert "next_week_num" in recovery


def test_v106_version_and_github_remains_primary_scheduler():
    assert 'APP_VERSION = "1.0.6"' in (ROOT / "config.py").read_text("utf-8")
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert 'cron: "7,22,37,52 11-23 * * 0"' in workflow
    assert 'cron: "7,17,27,37,47,57 12 * * 2"' in workflow
