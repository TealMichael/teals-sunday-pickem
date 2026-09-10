from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from clock_broadcast import build_clock_snapshot, new_clock_token

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def test_v107_version_and_commissioner_navigation_cleanup():
    assert 'APP_VERSION = "1.0.7"' in (ROOT / "config.py").read_text("utf-8")
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")
    assert 'commissioner_tools = ["Week", "Players", "Corrections", "Clock", "Diagnostics"]' in ui
    assert '["Launch", "Week", "Players", "Corrections", "Diagnostics"]' not in ui
    assert 'Commissioner • Gate 6' not in ui
    assert 'Launch readiness & full-week checks' in ui
    assert 'Database & recent activity' in ui
    assert 'Legacy build diagnostics & demos' in ui
    assert 'Wednesday Live Game Dress Rehearsal", expanded=False' in ui
    assert 'def _render_clock' in ui
    app = (ROOT / "app.py").read_text("utf-8")
    assert 'GATE5_UI_SCHEMA_VERSION", 0) < 4' in app


def test_clock_migration_is_scoped_hashed_and_prelock_private():
    sql = (ROOT / "db/006_sunday_clock.sql").read_text("utf-8")
    assert "clock_tokens" in sql
    assert "token_hash" in sql
    assert "digest(p_token, 'sha256')" in sql
    assert "Plaintext token is never stored" in sql
    assert "enable row level security" in sql
    assert "revoke all on table pickem.clock_tokens from anon, authenticated" in sql
    assert "revoke all on table pickem.clock_snapshots from anon, authenticated" in sql
    assert "grant execute on function pickem.clock_feed(text) to anon, authenticated" in sql
    assert "grant execute on function pickem.clock_ack(text, text) to anon, authenticated" in sql
    # The pre-lock branch must stay on readiness/manual content, never weekly/pulse content.
    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("-- Post-lock broadcast rhythm", 1)[0]
    assert "readiness" in prelock
    assert "weekly" not in prelock
    assert "pulse" not in prelock
    assert "lineup_picks" not in sql
    assert "pin_hash" not in sql


def test_awtrix_script_is_separate_headless_scoped_client():
    text = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert "# @headless true" in text
    assert "/rest/v1/rpc/clock_feed" in text
    assert "/rest/v1/rpc/clock_ack" in text
    assert '"Accept-Profile": "pickem"' in text
    assert '"Content-Profile": "pickem"' in text
    assert "sb_key" in text
    assert "token" in text
    assert "SUPABASE_SECRET_KEY" not in text
    assert "SERVICE_ROLE" not in text.upper()
    assert "ClassSchedule" not in text
    assert "FactTop10" not in text
    assert "self.ticks = 900" in text
    assert "elif dow >= 4" in text


def test_clock_token_generation_only_returns_hash_for_storage():
    token, digest, hint = new_clock_token()
    assert len(token) >= 32
    assert len(digest) == 64
    assert token not in digest
    assert token.endswith(hint)


class FakeClockStore:
    def __init__(self):
        self.snapshot = None

    def get_week_public_bundle(self, week_id, ttl_seconds=8.0):
        return {
            "players": [
                {"id": "p1", "nickname": "Alpha", "emoji": "🏈"},
                {"id": "p2", "nickname": "Bravo", "emoji": "🦆"},
                {"id": "p3", "nickname": "Charlie", "emoji": "⭐"},
            ],
            "lineups": [
                {"id": "l1", "player_id": "p1", "confirmed_at": "2026-09-13T12:00:00Z"},
                {"id": "l2", "player_id": "p2", "confirmed_at": "2026-09-13T12:00:00Z"},
            ],
            "picks": [
                {"lineup_id": "l1", "position": "QB", "pool_player_id": "q1"},
                {"lineup_id": "l2", "position": "QB", "pool_player_id": "q2"},
            ],
            "pool": [
                {"id": "q1", "position": "QB", "player_name": "Live Pool QB", "is_visible": True, "score_total": 12.3, "game_status": "LIVE", "availability_status": "HEALTHY"},
                {"id": "q2", "position": "QB", "player_name": "Final Pool QB", "is_visible": True, "score_total": 15.0, "game_status": "FINAL", "availability_status": "HEALTHY"},
                {"id": "hidden", "position": "WR", "player_name": "Hidden Player", "is_visible": False, "score_total": 30.0, "game_status": "LIVE", "availability_status": "HEALTHY"},
            ],
            "games": [
                {"away_team": "AAA", "home_team": "BBB", "away_score": 21, "home_score": 17, "game_status": "LIVE", "period": 3, "game_clock": "4:22", "kickoff_at": "2026-09-13T17:00:00Z"},
                {"away_team": "CCC", "home_team": "DDD", "away_score": 7, "home_score": 3, "game_status": "FINAL", "period": 4, "game_clock": "0:00", "kickoff_at": "2026-09-13T17:00:00Z"},
            ],
        }

    def get_weekly_results(self, season=None):
        return [
            {"player_id": "p1", "nickname_snapshot": "Alpha", "emoji_snapshot": "🏈", "season_points": 12, "weekly_score": 80.0, "finish_rank": 1},
            {"player_id": "p2", "nickname_snapshot": "Bravo", "emoji_snapshot": "🦆", "season_points": 9, "weekly_score": 75.0, "finish_rank": 2},
        ]

    def get_registered_players(self):
        return [
            {"id": "p1", "nickname": "Alpha", "emoji": "🏈"},
            {"id": "p2", "nickname": "Bravo", "emoji": "🦆"},
            {"id": "p3", "nickname": "Charlie", "emoji": "⭐"},
        ]

    def get_player_week_stats(self, week_id, pool_player_ids=None):
        return [
            {"pool_player_id": "q1", "raw_stats": {"passing_yards": 200, "passing_tds": 1}},
            {"pool_player_id": "hidden", "raw_stats": {"receiving_yards": 100}},
        ]


def test_clock_snapshot_full_weekly_all_live_games_pool_only_updates_and_week2_season():
    store = FakeClockStore()
    week = {"id": "w2", "season": 2026, "nfl_week": 2, "label": "Week 2", "data_status": "LIVE"}
    payload = build_clock_snapshot(store, week, now=datetime(2026, 9, 20, 18, 0, tzinfo=UTC))

    # All registered players appear in weekly standings, including a 0-point/no-lineup player.
    assert "Alpha" in payload["weekly"]
    assert "Bravo" in payload["weekly"]
    assert "Charlie" in payload["weekly"]
    # Only games that are currently live make the NFL ticker.
    assert "AAA 21 BBB 17" in payload["live_games"]
    assert "CCC" not in payload["live_games"]
    # Player Update is limited to visible pool players whose game is LIVE.
    assert any("Live Pool QB" in row for row in payload["player_updates"])
    assert not any("Final Pool QB" in row for row in payload["player_updates"])
    assert not any("Hidden Player" in row for row in payload["player_updates"])
    # Season ticker begins in Week 2 and includes the full registered group.
    assert payload["season_text"].startswith("SEASON STANDINGS")
    assert "Charlie 0 PTS" in payload["season_text"]


def test_week1_omits_season_standings():
    store = FakeClockStore()
    week = {"id": "w1", "season": 2026, "nfl_week": 1, "label": "Week 1", "data_status": "LIVE"}
    payload = build_clock_snapshot(store, week)
    assert payload["season_text"] == ""


def test_clock_snapshot_refresh_hooks_do_not_modify_scoring_engine():
    gate5 = (ROOT / "gate5.py").read_text("utf-8")
    worker = (ROOT / "scripts/nfl_refresh.py").read_text("utf-8")
    recovery = (ROOT / "automation_recovery.py").read_text("utf-8")
    assert "_refresh_clock_best_effort" in gate5
    assert "_refresh_clock_best_effort" in worker
    assert "refresh_clock_snapshot(store, refreshed)" in recovery
    scoring = (ROOT / "nfl_scoring.py").read_text("utf-8")
    assert "clock_broadcast" not in scoring
    sync = (ROOT / "nfl_sync.py").read_text("utf-8")
    assert "clock_broadcast" not in sync
