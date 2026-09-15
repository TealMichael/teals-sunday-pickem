from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import automation_recovery
import clock_broadcast
import gate4

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def _week(now: datetime, *, refresh_age_minutes: float = 1.0) -> dict:
    return {
        "id": "w1",
        "season": 2026,
        "nfl_week": 1,
        "published_at": (now - timedelta(days=5)).isoformat(),
        "locks_at": (now - timedelta(hours=1)).isoformat(),
        "data_status": "LIVE",
        "last_data_refresh_at": (now - timedelta(minutes=refresh_age_minutes)).isoformat(),
        "is_demo": False,
    }


class LaneStore:
    def __init__(self, now: datetime, *, game_age: float = 1.0):
        self.now = now
        self.game_age = game_age
        self.claimed: list[str] = []
        self.released: list[str] = []
        self.cache_clears: list[str] = []

    def get_nfl_games(self, week_id: str):
        return [{"provider_updated_at": (self.now - timedelta(minutes=self.game_age)).isoformat()}]

    def latest_data_run(self, run_type: str, *, week_id: str | None = None):
        return None

    def claim_refresh_lease(self, lease_key: str, *, owner: str, ttl_seconds: int = 180):
        self.claimed.append(lease_key)
        return True

    def release_refresh_lease(self, lease_key: str, *, owner: str):
        self.released.append(lease_key)

    def clear_week_cache(self, week_id: str):
        self.cache_clears.append(week_id)

    def get_week(self, week_id: str):
        return None


def test_hotfix710_config_and_display_cadence_are_locked():
    config = (ROOT / "config.py").read_text("utf-8")
    gate4_ui = (ROOT / "gate4_ui.py").read_text("utf-8")
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.10"' in config
    assert "ACTIVE_GAME_STATE_REFRESH_MINUTES = 2" in config
    assert "ACTIVE_PLAYER_STAT_REFRESH_MINUTES = 3" in config
    assert "LIVE_APP_DISPLAY_REFRESH_SECONDS = 15" in config
    assert "LIVE_GAME_STALE_MINUTES = 7" in config
    assert '@st.fragment(run_every=f"{LIVE_APP_DISPLAY_REFRESH_SECONDS}s")' in gate4_ui
    # Durable unattended GitHub fallback stays at five minutes.
    assert '2,7,12,17,22,27,32,37,42,47,52,57 11-23 * * 0' in workflow


def test_active_lane_prefers_due_player_stats_and_uses_one_lease(monkeypatch):
    now = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)
    store = LaneStore(now, game_age=10)
    week = _week(now, refresh_age_minutes=3.2)
    calls = []

    monkeypatch.setattr(automation_recovery, "refresh_live_player_stats", lambda s, w: calls.append("stats") or {"players": 25})
    monkeypatch.setattr(automation_recovery, "refresh_live_game_state", lambda s, w: calls.append("state") or {"games": []})
    monkeypatch.setattr(automation_recovery, "_refresh_clock_snapshot_best_effort", lambda s, w: None)

    _, info = automation_recovery.maybe_refresh_active_live_lane(store, week, now=now)
    assert calls == ["stats"]
    assert info and info["action"] == "player_stats" and info["success"] is True
    assert store.claimed == ["week:w1:active-player-stats"]
    assert store.released == ["week:w1:active-player-stats"]


def test_active_lane_uses_light_game_state_between_stat_cycles(monkeypatch):
    now = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)
    store = LaneStore(now, game_age=2.2)
    week = _week(now, refresh_age_minutes=1.0)
    calls = []

    monkeypatch.setattr(automation_recovery, "refresh_live_player_stats", lambda s, w: calls.append("stats") or {})
    monkeypatch.setattr(automation_recovery, "refresh_live_game_state", lambda s, w: calls.append("state") or {"games": 8})
    monkeypatch.setattr(automation_recovery, "_refresh_clock_snapshot_best_effort", lambda s, w: None)

    _, info = automation_recovery.maybe_refresh_active_live_lane(store, week, now=now)
    assert calls == ["state"]
    assert info and info["action"] == "game_state" and info["success"] is True
    assert store.claimed == ["week:w1:active-game-state"]


def test_stale_game_clock_is_hidden_but_last_score_remains(monkeypatch):
    now = datetime.now(UTC)
    old = (now - timedelta(minutes=8)).isoformat()
    game = {
        "game_status": "LIVE",
        "period": 2,
        "game_clock": "0:00",
        "provider_updated_at": old,
        "away_team": "GB",
        "home_team": "MIN",
        "away_score": 19,
        "home_score": 10,
        "kickoff_at": now.isoformat(),
    }
    pool = {"team_abbr": "GB", "game_status": "LIVE"}
    text = gate4.game_status_text(pool, {"GB": game})
    assert text == "LIVE"
    ticker = "".join(part["text"] for part in clock_broadcast._live_games_rich([game]))
    assert "GB 19" in ticker and "MIN 10" in ticker
    assert "Q2" not in ticker and "0:00" not in ticker and ticker.endswith("LIVE")


def test_fresh_game_clock_still_shows_quarter_and_clock():
    now = datetime.now(UTC)
    game = {
        "game_status": "LIVE",
        "period": 3,
        "game_clock": "10:51",
        "provider_updated_at": (now - timedelta(minutes=1)).isoformat(),
        "away_team": "GB",
        "home_team": "MIN",
        "away_score": 19,
        "home_score": 10,
        "kickoff_at": now.isoformat(),
    }
    pool = {"team_abbr": "GB", "game_status": "LIVE"}
    assert gate4.game_status_text(pool, {"GB": game}) == "LIVE • Q3 • 10:51"
    ticker = "".join(part["text"] for part in clock_broadcast._live_games_rich([game]))
    assert ticker.endswith("Q3 10:51")
