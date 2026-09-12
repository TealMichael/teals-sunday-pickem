from datetime import datetime
from zoneinfo import ZoneInfo

from nfl_sync import injury_interval_minutes

ET = ZoneInfo("America/New_York")


def test_injury_refresh_cadence_ramps_up_toward_lock():
    assert injury_interval_minutes(datetime(2026,9,8,12,tzinfo=ET)) == 360  # Tue
    assert injury_interval_minutes(datetime(2026,9,11,12,tzinfo=ET)) == 240  # Fri
    assert injury_interval_minutes(datetime(2026,9,12,12,tzinfo=ET)) == 180  # Sat
    assert injury_interval_minutes(datetime(2026,9,13,9,tzinfo=ET)) == 60
    assert injury_interval_minutes(datetime(2026,9,13,11,30,tzinfo=ET)) == 15
    assert injury_interval_minutes(datetime(2026,9,13,14,tzinfo=ET)) == 15


def test_run_due_uses_start_time_so_15_minute_cron_does_not_skip_every_other_run():
    from nfl_sync import _run_due
    from datetime import timezone

    last = {
        "started_at": "2026-09-13T17:07:00+00:00",
        "completed_at": "2026-09-13T17:08:30+00:00",
    }
    now = datetime(2026, 9, 13, 17, 22, 0, tzinfo=timezone.utc)
    assert _run_due(last, 15, now) is True


def test_run_due_tolerates_normal_github_start_time_jitter():
    from nfl_sync import _run_due
    from datetime import timezone

    last = {
        "started_at": "2026-09-13T17:07:45+00:00",
        "completed_at": "2026-09-13T17:08:30+00:00",
    }
    # The next nominal :22 cron began 35 seconds before a strict 15-minute
    # start-to-start interval. It should still run instead of slipping to :37.
    now = datetime(2026, 9, 13, 17, 22, 20, tzinfo=timezone.utc)
    assert _run_due(last, 15, now) is True
