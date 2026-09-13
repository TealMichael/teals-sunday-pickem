from pathlib import Path

from weekly import lineup_readiness, required_backup_positions

ROOT = Path(__file__).resolve().parents[1]


def test_questionable_backup_must_still_have_eligible_sunday_game():
    pool = {
        "starter": {"id": "starter", "position": "TE", "availability_status": "QUESTIONABLE", "schedule_eligible": True},
        "backup": {"id": "backup", "position": "TE", "availability_status": "HEALTHY", "schedule_eligible": False},
    }
    picks = [{"position": "TE", "pool_player_id": "starter", "emergency_pool_player_id": "backup"}]
    assert required_backup_positions(picks, pool) == ["TE"]
    assert lineup_readiness(picks, pool)["ready"] is False


def test_visible_pool_and_save_guard_carry_schedule_eligibility():
    text = (ROOT / "store.py").read_text("utf-8")
    assert "availability_status,schedule_eligible,schedule_note" in text
    assert "That player's game is no longer eligible for Sunday Pick'em." in text
    assert "That emergency backup's game is no longer eligible for Sunday Pick'em." in text


def test_injury_replacement_cannot_promote_schedule_ineligible_hidden_player():
    text = (ROOT / "store.py").read_text("utf-8")
    start = text.index("def promote_replacements_for_out_players")
    end = text.index("def upsert_player_week_stats", start)
    section = text[start:end]
    assert 'and bool(r.get("schedule_eligible", True))' in section


def test_database_guard_allows_only_backup_clear_for_preserved_hidden_starter():
    sql = (ROOT / "db/011_preserved_lineup_selection_guard.sql").read_text("utf-8")
    assert "v_cleanup_only boolean := false" in sql
    assert "old.emergency_pool_player_id is not null" in sql
    assert "new.emergency_pool_player_id is null" in sql
    assert "if not v_cleanup_only then" in sql
    assert "not coalesce(v_starter.schedule_eligible, true)" in sql
    assert "not coalesce(v_backup.schedule_eligible, true)" in sql
    assert "if now() >= v_week.locks_at then" in sql
    assert "Picks are locked for this week." in sql


def test_final_freeze_does_not_touch_protected_sunday_surfaces():
    config = (ROOT / "config.py").read_text("utf-8")
    assert 'APP_VERSION = "1.0.7"' in config
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.3"' in config
    # Hotfix 7.2 deliberately leaves scoring, clock client, and workflows at
    # their already-tested contracts.
    scoring = (ROOT / "nfl_scoring.py").read_text("utf-8")
    assert "def score_stat_line" in scoring
    assert "fg_made * 3.0" in scoring
    awtrix = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert "# @version 1.0.7-hotfix7.1" in awtrix
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert '7,22,37,52 11-23 * * 0' in workflow


def test_save_pick_rejects_schedule_ineligible_starter_before_database_write():
    from store import StoreError, SupabaseStore

    store = SupabaseStore.__new__(SupabaseStore)
    store._public_cache = {}
    week = {
        "id": "week-1",
        "opens_at": "2026-09-01T00:00:00+00:00",
        "locks_at": "2099-09-13T17:00:00+00:00",
        "is_demo": False,
    }
    pool = [{
        "id": "qb-1",
        "position": "QB",
        "is_visible": True,
        "availability_status": "HEALTHY",
        "schedule_eligible": False,
    }]
    try:
        store.save_pick(
            week_id="week-1",
            player_id="player-1",
            position="QB",
            pool_player_id="qb-1",
            known_week=week,
            known_pool=pool,
        )
    except StoreError as exc:
        assert "no longer eligible" in str(exc)
    else:
        raise AssertionError("schedule-ineligible starter was accepted")


def test_save_pick_rejects_schedule_ineligible_emergency_backup_before_database_write():
    from store import StoreError, SupabaseStore

    store = SupabaseStore.__new__(SupabaseStore)
    store._public_cache = {}
    week = {
        "id": "week-1",
        "opens_at": "2026-09-01T00:00:00+00:00",
        "locks_at": "2099-09-13T17:00:00+00:00",
        "is_demo": False,
    }
    pool = [
        {
            "id": "te-1",
            "position": "TE",
            "is_visible": True,
            "availability_status": "QUESTIONABLE",
            "schedule_eligible": True,
        },
        {
            "id": "te-2",
            "position": "TE",
            "is_visible": True,
            "availability_status": "HEALTHY",
            "schedule_eligible": False,
        },
    ]
    try:
        store.save_pick(
            week_id="week-1",
            player_id="player-1",
            position="TE",
            pool_player_id="te-1",
            emergency_pool_player_id="te-2",
            known_week=week,
            known_pool=pool,
        )
    except StoreError as exc:
        assert "emergency backup's game is no longer eligible" in str(exc)
    else:
        raise AssertionError("schedule-ineligible emergency backup was accepted")
