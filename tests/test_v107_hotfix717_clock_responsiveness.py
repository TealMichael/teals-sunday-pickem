from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import automation_recovery
import clock_broadcast
import nfl_sync

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]


def test_saturday_preview_is_schedule_only_and_includes_sunday_games():
    games = [
        {
            "kickoff_at": "2026-09-27T17:00:00+00:00",
            "away_team": "KC",
            "home_team": "MIA",
            "game_status": "SCHEDULED",
        },
        {
            "kickoff_at": "2026-09-27T20:25:00+00:00",
            "away_team": "BAL",
            "home_team": "DAL",
            "game_status": "SCHEDULED",
        },
        # Monday game must not leak into the Saturday Sunday-preview ticker.
        {
            "kickoff_at": "2026-09-29T00:15:00+00:00",
            "away_team": "PHI",
            "home_team": "CHI",
            "game_status": "SCHEDULED",
        },
    ]
    text = clock_broadcast._sunday_preview_text(games, "2026-09-27T17:00:00+00:00")
    assert text.startswith("NFL SUNDAY PREVIEW")
    assert "KC @ MIA" in text
    assert "BAL @ DAL" in text
    assert "PHI" not in text
    assert "PTS" not in text
    assert "PICK'EM" not in text


def test_active_full_scoreboard_freshness_uses_own_success_run_not_freshest_game_row():
    class Store:
        def last_successful_run(self, run_type, week_id=None):
            assert run_type == "live_game_state"
            assert week_id == "w1"
            return {"completed_at": "2026-09-20T17:00:00+00:00"}

        def get_nfl_games(self, week_id):
            raise AssertionError("individual game timestamps must not drive whole-slate freshness")

    age = automation_recovery._latest_game_state_age(
        Store(), "w1", datetime(2026, 9, 20, 17, 3, tzinfo=UTC)
    )
    assert age == 3.0


def test_shared_live_refresh_gets_full_scoreboard_before_pool_stats(monkeypatch):
    calls = []
    games = [{"provider_event_id": "g1", "is_eligible": True, "game_status": "LIVE"}]

    def fake_game_state(store, week, espn):
        calls.append("scoreboard")
        return {"games": games, "live": 1, "final": 0}

    def fake_player_stats(store, week, received_games, espn, **kwargs):
        calls.append("player_stats")
        assert received_games == games
        assert kwargs["run_type"] == "live_scores"
        return {"status": "LIVE"}

    monkeypatch.setattr(nfl_sync, "refresh_live_game_state", fake_game_state)
    monkeypatch.setattr(nfl_sync, "_refresh_live_player_stats_from_games", fake_player_stats)
    result = nfl_sync.refresh_live_scores(object(), {"id": "w1", "locks_at": "2026-09-20T17:00:00+00:00"}, espn=object())
    assert result == {"status": "LIVE"}
    assert calls == ["scoreboard", "player_stats"]


def test_live_refresh_preserves_scoring_path_if_scoreboard_call_fails(monkeypatch):
    fallback_games = [{"provider_event_id": "g1", "is_eligible": True, "game_status": "LIVE"}]

    def broken_scoreboard(*args, **kwargs):
        raise RuntimeError("temporary scoreboard outage")

    monkeypatch.setattr(nfl_sync, "refresh_live_game_state", broken_scoreboard)
    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda *args, **kwargs: fallback_games)
    monkeypatch.setattr(
        nfl_sync,
        "_refresh_live_player_stats_from_games",
        lambda store, week, games, espn, **kwargs: {"games_seen": games},
    )
    result = nfl_sync.refresh_live_scores(object(), {"id": "w1", "locks_at": "2026-09-20T17:00:00+00:00"}, espn=object())
    assert result["games_seen"] == fallback_games


def test_sql_parks_caleb_adds_all_day_saturday_preview_and_preserves_live_score_slots():
    sql = (ROOT / "db" / "012_clock_responsiveness_saturday_preview.sql").read_text("utf-8")
    assert "extract(dow from v_local)::integer = 6" in sql
    assert "/ 900" in sql
    assert "'category', 'preview'" in sql
    assert "v_payload->>'sunday_preview'" in sql
    assert "when 1 then v_category := 'live_games'" in sql
    assert "when 4 then v_category := 'live_games'" in sql
    assert "when 7 then v_category := 'live_games'" in sql
    assert "when 10 then v_category := 'live_games'" in sql
    assert "when 2 then v_category := 'player'" in sql
    assert "when 8 then v_category := 'player'" in sql
    assert "v_category := 'caleb'" not in sql
    assert "v_caleb_live" not in sql


def test_awtrix_dynamic_sports_replace_stale_display_but_manual_can_stack():
    script = (ROOT / "awtrix" / "PickemSunday.ax").read_text("utf-8")
    assert '# @version 1.0.7-hotfix7.17' in script
    assert 'category == "live_games"' in script
    assert 'category == "preview"' in script
    assert 'stack_it = false' in script
    assert '"stack": stack_it' in script
    assert 'if category == "manual"' in script
    assert 'self.ticks = 10' in script
    assert 'dow == 6' in script and 'self.ticks = 30' in script


def test_build_and_warm_reload_markers_are_bumped():
    config = (ROOT / "config.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.17"' in config
    assert 'NFL_SYNC_SCHEMA_VERSION", 0) < 6' in app
    assert 'AUTOMATION_RECOVERY_SCHEMA_VERSION", 0) < 6' in app
    assert 'GATE5_UI_SCHEMA_VERSION", 0) < 8' in app
    assert clock_broadcast.CLOCK_SNAPSHOT_VERSION == 5
    assert nfl_sync.NFL_SYNC_SCHEMA_VERSION == 6
    assert automation_recovery.AUTOMATION_RECOVERY_SCHEMA_VERSION == 6


def test_worker_keeps_caleb_code_parked_without_refreshing_special_provider():
    worker = (ROOT / "scripts" / "nfl_refresh.py").read_text("utf-8")
    assert "refresh_specials=False" in worker
    assert "Caleb Watch is parked" in worker
