from datetime import datetime, timezone

from weekly import (
    POSITIONS,
    first_incomplete_position,
    lineup_progress,
    pool_is_ready,
    required_backup_positions,
    week_phase,
)

UTC = timezone.utc


def test_week_phase_uses_open_and_universal_lock():
    week = {"opens_at": "2026-09-08T16:00:00+00:00", "locks_at": "2026-09-13T17:00:00+00:00"}
    assert week_phase(week, datetime(2026, 9, 8, 15, 59, tzinfo=UTC)) == "upcoming"
    assert week_phase(week, datetime(2026, 9, 8, 16, 0, tzinfo=UTC)) == "open"
    assert week_phase(week, datetime(2026, 9, 13, 17, 0, tzinfo=UTC)) == "locked"


def test_pool_ready_requires_exactly_five_visible_per_position():
    pool = []
    for pos in POSITIONS:
        for rank in range(1, 11):
            pool.append({"position": pos, "slot_rank": rank, "is_visible": rank <= 5})
    assert pool_is_ready(pool)
    pool.pop()
    assert pool_is_ready(pool)  # hidden #10 is not required for user-facing readiness
    pool = [p for p in pool if not (p["position"] == "QB" and p["slot_rank"] == 5)]
    assert not pool_is_ready(pool)


def test_questionable_starter_requires_backup():
    pool = {
        "a": {"id": "a", "position": "RB", "availability_status": "QUESTIONABLE"},
        "b": {"id": "b", "position": "QB", "availability_status": "HEALTHY"},
    }
    picks = [
        {"position": "QB", "pool_player_id": "b", "emergency_pool_player_id": None},
        {"position": "RB", "pool_player_id": "a", "emergency_pool_player_id": None},
    ]
    assert required_backup_positions(picks, pool) == ["RB"]
    assert first_incomplete_position(picks, pool) == "RB"
    assert lineup_progress(picks) == (2, 5)
