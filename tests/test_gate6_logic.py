from datetime import datetime, timedelta, timezone

from gate6 import launch_readiness, run_full_week_rehearsal

UTC = timezone.utc


class FakeLaunchStore:
    def __init__(self, now: datetime, *, heartbeat=True, bad_schedule=False):
        self.now = now
        self.heartbeat = heartbeat
        self.bad_schedule = bad_schedule

    def healthcheck(self):
        return True

    def get_nfl_games(self, week_id, eligible_only=False):
        if self.bad_schedule:
            return []
        return [
            {"id": f"g{i}", "is_eligible": True, "home_team": "DET", "away_team": "GB"}
            for i in range(13)
        ]

    def get_full_week_pool(self, week_id):
        return []

    def last_successful_run(self, run_type, week_id=None):
        if run_type == "preseason_replay":
            return {"metadata": {"anchor_pass": True, "database_pass": True, "week1_isolation_pass": True, "cleanup_pass": True}}
        if run_type == "scoring_diagnostic":
            return {"metadata": {"math_pass": True, "database_pass": True, "week1_isolation_pass": True, "cleanup_pass": True}}
        if run_type == "auto_cycle" and self.heartbeat:
            return {"completed_at": (self.now - timedelta(minutes=10)).isoformat(), "metadata": {"actions": []}}
        return None

    def get_recent_data_runs(self, week_id=None, limit=20):
        return []

    def get_registered_players(self):
        return [{"id": "p1", "nickname": "Mike T.", "emoji": "🤘"}]


def _week(*, bad_lock=False):
    return {
        "id": "w1",
        "season": 2026,
        "nfl_week": 1,
        "label": "Week 1",
        "opens_at": "2026-09-08T16:00:00+00:00",  # Tue noon ET
        "locks_at": "2026-09-13T18:00:00+00:00" if bad_lock else "2026-09-13T17:00:00+00:00",  # Sun 1 ET
        "published_at": None,
        "data_status": "WAITING",
    }


def test_launch_readiness_can_be_fully_ready_before_tuesday():
    now = datetime(2026, 9, 6, 21, 0, tzinfo=UTC)
    report = launch_readiness(FakeLaunchStore(now), _week(), now=now)
    assert report["overall"] == "READY"
    statuses = {row["key"]: row["status"] for row in report["checks"]}
    assert statuses["database"] == "PASS"
    assert statuses["week_timing"] == "PASS"
    assert statuses["real_boxscore"] == "PASS"
    assert statuses["scoring"] == "PASS"
    assert statuses["automation"] == "PASS"


def test_launch_readiness_warns_until_first_gate6_heartbeat():
    now = datetime(2026, 9, 6, 21, 0, tzinfo=UTC)
    report = launch_readiness(FakeLaunchStore(now, heartbeat=False), _week(), now=now)
    assert report["overall"] == "WARN"
    automation = next(row for row in report["checks"] if row["key"] == "automation")
    assert automation["status"] == "WARN"


def test_launch_readiness_fails_bad_lock_contract():
    now = datetime(2026, 9, 6, 21, 0, tzinfo=UTC)
    report = launch_readiness(FakeLaunchStore(now), _week(bad_lock=True), now=now)
    assert report["overall"] == "FAIL"
    timing = next(row for row in report["checks"] if row["key"] == "week_timing")
    assert timing["status"] == "FAIL"


def test_full_week_rehearsal_passes_all_core_contracts():
    report = run_full_week_rehearsal()
    assert report["success"] is True
    assert report["passed"] == report["total"]
    names = {row["name"] for row in report["steps"]}
    assert "Universal lock" in names
    assert "Emergency backup" in names
    assert "Incomplete lineup" in names
    assert "Weekly tie" in names
    assert "Season co-champion tie" in names
