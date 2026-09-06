from datetime import datetime
from zoneinfo import ZoneInfo

from nfl_sync import injury_interval_minutes

ET = ZoneInfo("America/New_York")


def test_injury_refresh_cadence_ramps_up_toward_lock():
    assert injury_interval_minutes(datetime(2026,9,8,12,tzinfo=ET)) == 360  # Tue
    assert injury_interval_minutes(datetime(2026,9,11,12,tzinfo=ET)) == 240  # Fri
    assert injury_interval_minutes(datetime(2026,9,12,12,tzinfo=ET)) == 180  # Sat
    assert injury_interval_minutes(datetime(2026,9,13,9,tzinfo=ET)) == 60
    assert injury_interval_minutes(datetime(2026,9,13,11,30,tzinfo=ET)) == 30
    assert injury_interval_minutes(datetime(2026,9,13,14,tzinfo=ET)) == 60
