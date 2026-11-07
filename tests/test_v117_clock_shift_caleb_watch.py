"""v1.0.17 clock-only timetable and special-statistics regression checks."""

from datetime import datetime, timezone
from pathlib import Path

from clock_broadcast import build_caleb_4k_watch


ROOT = Path(__file__).resolve().parents[1]


def test_new_clock_migration_preserves_privacy_safe_pregame_rotation():
    previous = (ROOT / "db/013_pregame_four_way_double_scroll.sql").read_text("utf-8")
    current = (ROOT / "db/016_clock_standings_shift_caleb_watch.sql").read_text("utf-8")
    before_lock = lambda sql: sql.split("if now() < v_week.locks_at then", 1)[1].split(
        "else\n    -- Post-lock broadcast rhythm", 1
    )[0]
    assert before_lock(current) == before_lock(previous)
    assert "v_slot := floor(extract(epoch from now()) / 900)" in current
    assert "where is_demo = false" in current
    assert "-- Sunday broadcast: begin 10:30 AM ET and stop at midnight." in current


def test_weekly_standings_move_five_minutes_without_losing_nfl_slots():
    sql = (ROOT / "db/016_clock_standings_shift_caleb_watch.sql").read_text("utf-8")
    live = sql.split("-- Post-lock broadcast rhythm", 1)[1].split(
        "if v_category = 'weekly' then", 1
    )[0]
    for slot, category in enumerate((
        "live_games", "weekly", "player", "live_games", "weekly", "season",
        "live_games", "weekly", "caleb", "live_games", "weekly", "manual",
    )):
        if slot == 5:
            assert "when 5 then v_category := case" in live
            assert "when v_week.nfl_week >= 2 then 'season'" in live
        elif slot == 11:
            assert "else v_category := 'manual'" in live
        else:
            assert f"when {slot} then v_category := '{category}'" in live
    assert live.count("v_category := 'weekly'") == 4
    assert live.count("v_category := 'live_games'") == 4
    assert "when 8 then v_category := 'caleb';" in live


def test_caleb_missing_data_falls_back_to_pool_update():
    sql = (ROOT / "db/016_clock_standings_shift_caleb_watch.sql").read_text("utf-8")
    fallback = sql.split("elsif v_category = 'caleb' then", 1)[1].split(
        "elsif v_category = 'pulse' then", 1
    )[0]
    assert "v_caleb->>'text'" in fallback
    assert "v_caleb->'fragments'" in fallback
    assert "v_payload->'player_updates'" in fallback
    assert "v_category := 'player'" in fallback


def test_only_scheduled_automation_requests_extra_caleb_provider_work():
    worker = (ROOT / "scripts/nfl_refresh.py").read_text("utf-8")
    coordinated = (ROOT / "refresh_protocol.py").read_text("utf-8")
    clock = (ROOT / "clock_broadcast.py").read_text("utf-8")
    assert "refresh_clock_snapshot(store, target, refresh_specials=True)" in worker
    assert "refresh_clock_snapshot(owned,owned.get_week(str(current['id'])) or current)" in coordinated
    assert "refresh_specials: bool = False" in clock


def test_existing_caleb_builder_handles_live_yards_and_season_pace():
    class Store:
        def get_nfl_games(self, week_id):
            return [{"home_team": "CHI", "away_team": "DET", "game_status": "LIVE",
                     "provider_event_id": "bears-game", "kickoff_at": "2026-09-27T17:00:00+00:00"}]

    class SeasonStats:
        def weekly_player_stats(self, season):
            return [{"week": "1", "player_display_name": "Caleb Williams", "passing_yards": "200"},
                    {"week": "2", "player_display_name": "Caleb Williams", "passing_yards": "300"}]

    class BoxScore:
        def summary(self, event_id):
            assert event_id == "bears-game"
            return {"event": event_id}

        def player_stats(self, payload):
            return [{"team_abbr": "CHI", "player_name": "Caleb Williams",
                     "stats": {"passing_yards": 125}}]

    watch = build_caleb_4k_watch(
        Store(), {"id": "w3", "season": 2026, "nfl_week": 3},
        now=datetime(2026, 9, 27, 19, tzinfo=timezone.utc),
        nflverse=SeasonStats(), espn=BoxScore(),
    )
    assert watch["is_live"] is True
    assert watch["season_yards"] == 625
    assert watch["remaining"] == 3375
    assert watch["pace"] == round(625 / 3 * 17)
    assert "TODAY: 125 YDS" in watch["text"]
    assert "CALEB 4K WATCH" in watch["text"]


def test_release_is_distinct_and_preserves_physical_awtrix_script():
    config = (ROOT / "config.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    script = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert 'APP_VERSION = "1.0.17"' in config
    assert 'APP_BUILD_VERSION = "1.0.17-clock"' in config
    assert '"1.0.17-clock"' in app
    assert '"/rest/v1/rpc/pickem_clock_feed"' in script
    assert 'if category == "preview" || category == "live_games" || category == "weekly" || category == "manual"' in script
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")
    assert "GATE5_UI_SCHEMA_VERSION = 13" in ui
    assert '("Caleb 4K Watch", (payload.get("caleb_watch") or {}).get("text"))' in ui
