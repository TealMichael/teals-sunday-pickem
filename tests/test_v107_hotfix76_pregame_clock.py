from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "db/011_clock_pregame_preview.sql"


def test_pregame_clock_starts_at_9_and_keeps_1pm_postlock_cadence_unchanged():
    sql = SQL.read_text("utf-8")
    assert "locks_at - interval '4 hours'" in sql
    assert "v_hour < 12" in sql
    assert "floor(extract(epoch from now()) / 600)" in sql
    assert "mod(floor(v_minute / 5)::integer, 2) = 0" in sql
    assert "Noon-lock: Welcome at :00/:10/:20/" in sql
    assert "v_category := 'welcome'" in sql

    # The 1 PM+ rotation stays exactly on the established Hotfix 7 cadence.
    for slot in (0, 3, 6, 9):
        assert f"when {slot} then v_category := 'weekly'" in sql
    for slot in (1, 4, 7, 10):
        assert f"when {slot} then v_category := 'live_games'" in sql
    assert "when 2 then v_category := case when v_caleb_live then 'caleb' else 'player' end" in sql
    assert "when 8 then v_category := 'caleb'" in sql
    assert "else v_category := 'manual';              -- :55" in sql


def test_pregame_preview_is_schedule_only_and_privacy_safe():
    sql = SQL.read_text("utf-8")
    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("-- Post-lock broadcast rhythm", 1)[0]

    assert "SUNDAY NFL PREVIEW" in prelock
    assert "from pickem.nfl_games" in prelock
    assert "game_status not in ('CANCELED', 'POSTPONED')" in prelock
    assert "timezone('America/New_York', kickoff_at)" in prelock
    assert "v_settings.welcome_text" in prelock

    # Pre-lock broadcast must never expose private Pick'em ownership/story data.
    assert "weekly_rich" not in prelock
    assert "pulses_rich" not in prelock
    assert "player_updates_rich" not in prelock
    assert "lineup_picks" not in prelock
    assert "confirmed_picks" not in prelock


def test_no_awtrix_client_reinstall_is_required():
    sql = SQL.read_text("utf-8")
    client = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert "create or replace function pickem.clock_feed(p_token text)" in sql
    assert "/rest/v1/rpc/pickem_clock_feed" in client
    assert 'default=15 min=10 max=60 unit=sec' in client
