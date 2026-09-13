from datetime import datetime, timedelta, timezone

from automation_recovery import recovery_action_due

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


def test_sunday_morning_recovery_arms_at_8am_for_hourly_stale_data():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)  # 1 PM ET
    now = lock - timedelta(hours=5)  # 8 AM ET
    week = base_week(lock)
    week["last_data_refresh_at"] = stamp(now - timedelta(minutes=63))
    success = {"injury_refresh": {"completed_at": stamp(now - timedelta(minutes=63)), "success": True}}
    assert recovery_action_due(FakeStore(success=success), week, now=now) == "injury"


def test_sunday_morning_recovery_does_not_arm_before_8am():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    now = lock - timedelta(hours=5, minutes=1)  # 7:59 AM ET
    week = base_week(lock)
    week["last_data_refresh_at"] = stamp(now - timedelta(hours=4))
    success = {"injury_refresh": {"completed_at": stamp(now - timedelta(hours=4)), "success": True}}
    assert recovery_action_due(FakeStore(success=success), week, now=now) is None


def test_sunday_morning_hourly_grace_does_not_overpoll():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    now = lock - timedelta(hours=3)  # 10 AM ET
    week = base_week(lock)
    week["last_data_refresh_at"] = stamp(now - timedelta(minutes=61))
    success = {"injury_refresh": {"completed_at": stamp(now - timedelta(minutes=61)), "success": True}}
    assert recovery_action_due(FakeStore(success=success), week, now=now) is None


def test_final_two_hours_keep_existing_15_minute_recovery_threshold():
    lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    now = lock - timedelta(hours=1)
    week = base_week(lock)
    week["last_data_refresh_at"] = stamp(now - timedelta(minutes=18))
    success = {"injury_refresh": {"completed_at": stamp(now - timedelta(minutes=18)), "success": True}}
    assert recovery_action_due(FakeStore(success=success), week, now=now) == "injury"
