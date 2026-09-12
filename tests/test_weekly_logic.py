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


def test_questionable_starter_with_out_backup_still_needs_attention():
    pool = {
        "q": {"id":"q","position":"TE","availability_status":"QUESTIONABLE"},
        "b": {"id":"b","position":"TE","availability_status":"OUT"},
    }
    picks = [{"position":"TE","pool_player_id":"q","emergency_pool_player_id":"b"}]
    assert required_backup_positions(picks, pool) == ["TE"]


def test_out_starter_is_treated_as_incomplete_for_editing():
    from weekly import unavailable_starter_positions
    pool = {
        "q": {"id":"q","position":"QB","availability_status":"HEALTHY"},
        "x": {"id":"x","position":"RB","availability_status":"OUT"},
    }
    picks = [
        {"position":"QB","pool_player_id":"q","emergency_pool_player_id":None},
        {"position":"RB","pool_player_id":"x","emergency_pool_player_id":None},
    ]
    assert unavailable_starter_positions(picks, pool) == ["RB"]
    assert first_incomplete_position(picks, pool) == "RB"


def test_out_starter_with_valid_emergency_backup_keeps_position_ready():
    from weekly import unavailable_starter_positions

    pool = {
        "qb": {"id": "qb", "position": "QB", "availability_status": "HEALTHY"},
        "rb": {"id": "rb", "position": "RB", "availability_status": "OUT", "is_visible": False},
        "rb_b": {"id": "rb_b", "position": "RB", "availability_status": "HEALTHY", "schedule_eligible": True},
        "wr": {"id": "wr", "position": "WR", "availability_status": "HEALTHY"},
        "te": {"id": "te", "position": "TE", "availability_status": "HEALTHY"},
        "k": {"id": "k", "position": "K", "availability_status": "HEALTHY"},
    }
    picks = [
        {"position": "QB", "pool_player_id": "qb", "emergency_pool_player_id": None},
        {"position": "RB", "pool_player_id": "rb", "emergency_pool_player_id": "rb_b"},
        {"position": "WR", "pool_player_id": "wr", "emergency_pool_player_id": None},
        {"position": "TE", "pool_player_id": "te", "emergency_pool_player_id": None},
        {"position": "K", "pool_player_id": "k", "emergency_pool_player_id": None},
    ]

    assert unavailable_starter_positions(picks, pool) == []
    assert first_incomplete_position(picks, pool) is None
