from __future__ import annotations

from pathlib import Path

import pytest

import nfl_sync
from gate4 import _effective_pick
from nfl_sources import ESPNProvider
from weekly import unavailable_starter_positions, first_incomplete_position

ROOT = Path(__file__).resolve().parents[1]


class LiveStore:
    def __init__(self, pool):
        self.pool = [dict(row) for row in pool]
        self.applied = []
        self.stat_rows = []
        self.game_upserts = []
        self.week_updates = []
        self.finished = []

    def start_data_run(self, *args, **kwargs):
        return "run"

    def finish_data_run(self, run_id, **kwargs):
        self.finished.append(kwargs)

    def reconcile_pool_schedule(self, week, games):
        return []

    def get_full_week_pool(self, week_id):
        return [dict(row) for row in self.pool]

    def upsert_nfl_games(self, week_id, games):
        self.game_upserts.extend([dict(row) for row in games])
        return games

    def upsert_player_week_stats(self, week_id, rows):
        self.stat_rows.extend([dict(row) for row in rows])
        return rows

    def apply_pool_scores(self, week, rows, *, score_status):
        self.applied.extend([dict(row) for row in rows])
        return rows

    def update_week_data_state(self, week_id, **kwargs):
        self.week_updates.append(dict(kwargs))
        return kwargs


class FakeESPN:
    def __init__(self, summaries):
        self.summaries = summaries
        self.calls = []

    def summary(self, event_id):
        self.calls.append(event_id)
        value = self.summaries[event_id]
        if isinstance(value, Exception):
            raise value
        return value

    def player_stats(self, payload):
        return ESPNProvider.player_stats(payload)


def _game(event, home, away, status="LIVE", completed=False):
    return {
        "week_id": "w1",
        "provider_event_id": event,
        "home_team": home,
        "away_team": away,
        "kickoff_at": "2026-09-13T17:00:00+00:00",
        "is_eligible": True,
        "game_status": status,
        "completed": completed,
        "period": None,
        "game_clock": None,
        "home_score": 0,
        "away_score": 0,
    }


def _summary(home, away, *, state="in", completed=False, period=2, clock="8:41", home_score=7, away_score=10, players=()):
    by_team = {home: [], away: []}
    for team, player_name, position, yds in players:
        by_team[team].append({
            "athlete": {
                "id": f"id-{player_name}",
                "displayName": player_name,
                "position": {"abbreviation": position},
            },
            "stats": [str(yds), "0", "0"],
        })
    return {
        "header": {
            "competitions": [{
                "status": {
                    "period": period,
                    "displayClock": clock,
                    "type": {"state": state, "completed": completed},
                },
                "competitors": [
                    {"homeAway": "away", "score": str(away_score), "team": {"abbreviation": away}},
                    {"homeAway": "home", "score": str(home_score), "team": {"abbreviation": home}},
                ],
            }]
        },
        "boxscore": {
            "players": [
                {
                    "team": {"abbreviation": team},
                    "statistics": [{
                        "name": "passing",
                        "labels": ["YDS", "TD", "INT"],
                        "athletes": athletes,
                    }],
                }
                for team, athletes in by_team.items()
                if athletes
            ]
        },
    }


def _week():
    return {
        "id": "w1",
        "season": 2026,
        "nfl_week": 1,
        # Past lock avoids the pre-lock schedule reconciliation branch in unit tests.
        "locks_at": "2026-09-01T17:00:00+00:00",
        "published_at": "2026-09-08T16:00:00+00:00",
    }


def test_final_game_skip_never_zeroes_existing_score(monkeypatch):
    games = [_game("g1", "DET", "NO", status="FINAL", completed=True)]
    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda store, week, espn=None, **kwargs: games)
    pool = [{
        "id": "p1", "team_abbr": "DET", "player_name": "Final Player", "position": "WR",
        "game_status": "FINAL", "score_updated_at": "2026-09-13T20:00:00Z", "score_total": 20.0,
    }]
    store = LiveStore(pool)
    espn = FakeESPN({})

    result = nfl_sync.refresh_live_scores(store, _week(), espn=espn)

    assert result["status"] == "PROVISIONAL"
    assert espn.calls == []
    assert store.applied == []  # the 20-point FINAL score was never rewritten as 0
    assert store.week_updates[-1]["data_status"] == "PROVISIONAL"


def test_one_bad_game_does_not_block_other_live_game(monkeypatch):
    games = [_game("bad", "AAA", "BBB"), _game("good", "DET", "NO")]
    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda store, week, espn=None, **kwargs: games)
    pool = [
        {"id": "a", "team_abbr": "AAA", "player_name": "Keep Me", "position": "QB", "score_total": 12.0, "score_updated_at": "old"},
        {"id": "d", "team_abbr": "DET", "player_name": "Good QB", "position": "QB", "score_total": 0.0, "score_updated_at": None},
    ]
    espn = FakeESPN({
        "bad": RuntimeError("temporary feed error"),
        "good": _summary("DET", "NO", players=[("DET", "Good QB", "QB", 250)]),
    })
    store = LiveStore(pool)

    result = nfl_sync.refresh_live_scores(store, _week(), espn=espn)

    assert len(result["summary_errors"]) == 1
    assert result["summary_errors"][0]["event_id"] == "bad"
    assert [row["pool_player_id"] for row in store.applied] == ["d"]
    assert abs(store.applied[0]["points"] - 10.0) < 1e-9


def test_missing_player_in_successful_summary_preserves_previous_score(monkeypatch):
    games = [_game("g1", "DET", "NO")]
    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda store, week, espn=None, **kwargs: games)
    pool = [{
        "id": "p1", "team_abbr": "DET", "player_name": "Missing Temporarily", "position": "WR",
        "score_total": 17.4, "score_updated_at": "2026-09-13T18:00:00Z", "game_status": "LIVE",
    }]
    store = LiveStore(pool)
    espn = FakeESPN({"g1": _summary("DET", "NO", players=[])})

    result = nfl_sync.refresh_live_scores(store, _week(), espn=espn)

    assert result["preserved_missing_players"] == 1
    assert store.applied == []
    assert store.week_updates[-1]["data_status"] == "LIVE"


def test_live_summary_updates_game_clock_and_final_state(monkeypatch):
    games = [_game("g1", "SEA", "NE")]
    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda store, week, espn=None, **kwargs: games)
    pool = [{"id": "p1", "team_abbr": "SEA", "player_name": "QB One", "position": "QB", "score_updated_at": None}]
    store = LiveStore(pool)
    espn = FakeESPN({
        "g1": _summary("SEA", "NE", state="post", completed=True, period=4, clock="0:00", home_score=13, away_score=10,
                       players=[("SEA", "QB One", "QB", 200)])
    })

    result = nfl_sync.refresh_live_scores(store, _week(), espn=espn)

    assert result["status"] == "PROVISIONAL"
    merged = store.game_upserts[-1]
    assert merged["game_status"] == "FINAL"
    assert merged["completed"] is True
    assert merged["period"] == 4
    assert merged["game_clock"] == "0:00"
    assert merged["home_score"] == 13
    assert merged["away_score"] == 10
    assert store.applied[0]["game_status"] == "FINAL"


def test_all_started_summary_failures_fail_refresh_without_touching_scores(monkeypatch):
    games = [_game("g1", "DET", "NO")]
    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda store, week, espn=None, **kwargs: games)
    store = LiveStore([{"id": "p1", "team_abbr": "DET", "player_name": "Safe", "position": "WR", "score_total": 9.9, "score_updated_at": "old"}])
    espn = FakeESPN({"g1": RuntimeError("down")})

    with pytest.raises(nfl_sync.Gate3Error):
        nfl_sync.refresh_live_scores(store, _week(), espn=espn)

    assert store.applied == []
    assert store.week_updates == []
    assert store.finished[-1]["success"] is False


def test_schedule_ineligible_starter_requires_replacement_even_with_backup():
    picks = [
        {"position": "QB", "pool_player_id": "qb"},
        {"position": "RB", "pool_player_id": "rb"},
        {"position": "WR", "pool_player_id": "s", "emergency_pool_player_id": "b"},
        {"position": "TE", "pool_player_id": "te"},
        {"position": "K", "pool_player_id": "k"},
    ]
    pool = {
        "qb": {"id": "qb", "availability_status": "HEALTHY", "schedule_eligible": True},
        "rb": {"id": "rb", "availability_status": "HEALTHY", "schedule_eligible": True},
        "s": {"id": "s", "availability_status": "HEALTHY", "schedule_eligible": False},
        "b": {"id": "b", "availability_status": "HEALTHY", "schedule_eligible": True},
        "te": {"id": "te", "availability_status": "HEALTHY", "schedule_eligible": True},
        "k": {"id": "k", "availability_status": "HEALTHY", "schedule_eligible": True},
    }
    assert unavailable_starter_positions(picks, pool) == ["WR"]
    assert first_incomplete_position(picks, pool) == "WR"


def test_emergency_backup_must_itself_be_eligible_and_not_out():
    pick = {"pool_player_id": "s", "emergency_pool_player_id": "b"}
    starter = {"id": "s", "availability_status": "OUT", "schedule_eligible": True}
    out_backup = {"id": "b", "availability_status": "OUT", "schedule_eligible": True}
    active, activated = _effective_pick(pick, {"s": starter, "b": out_backup})
    assert active is starter
    assert activated is False

    healthy_backup = {"id": "b", "availability_status": "HEALTHY", "schedule_eligible": True}
    active, activated = _effective_pick(pick, {"s": starter, "b": healthy_backup})
    assert active is healthy_backup
    assert activated is True


def test_hotfix6_deployment_and_autorefresh_contracts():
    config = (ROOT / "config.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    weekly_ui = (ROOT / "weekly_ui.py").read_text("utf-8")
    gate4_ui = (ROOT / "gate4_ui.py").read_text("utf-8")

    assert 'APP_BUILD_VERSION = "1.0.7-hotfix6"' in config
    assert 'get_store(secret("SUPABASE_URL"), supabase_server_key(), APP_BUILD_VERSION)' in app
    assert 'WEEKLY_UI_SCHEMA_VERSION = 9' in weekly_ui
    assert 'GATE4_UI_SCHEMA_VERSION = 4' in gate4_ui
    assert '@st.fragment(run_every="60s")' in gate4_ui
    assert 'def render_live_sunday' in gate4_ui
    assert 'def _render_live_prelock_status' in weekly_ui
    assert '@st.fragment(run_every="15s")' in weekly_ui
    assert 'def _lock_transition_guard' in weekly_ui


def test_injury_status_freezes_at_each_players_kickoff():
    from datetime import datetime, timezone
    from store import injury_status_mutable_for_pool_row

    now = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)  # 2 PM ET
    early = {"kickoff_at": "2026-09-13T17:00:00+00:00"}  # 1 PM ET already kicked
    late = {"kickoff_at": "2026-09-13T20:25:00+00:00"}   # 4:25 PM ET not kicked
    assert injury_status_mutable_for_pool_row(early, now) is False
    assert injury_status_mutable_for_pool_row(late, now) is True


def test_post_lock_injury_refresh_does_not_fake_live_score_freshness(monkeypatch):
    class InjuryStore:
        def __init__(self):
            self.week_updates = []
        def start_data_run(self, *args, **kwargs): return "run"
        def finish_data_run(self, *args, **kwargs): pass
        def reconcile_pool_schedule(self, week, games): return []
        def sync_pool_injury_status(self, week_id, players, *, now=None): return []
        def promote_replacements_for_out_players(self, week): return []
        def update_week_data_state(self, week_id, **kwargs):
            self.week_updates.append(kwargs)

    monkeypatch.setattr(nfl_sync, "sync_schedule", lambda store, week, **kwargs: [])
    monkeypatch.setattr(nfl_sync, "sync_players", lambda store: {pos: [] for pos in ("QB", "RB", "WR", "TE", "K")})
    store = InjuryStore()
    week = {
        "id": "w1",
        "published_at": "2026-09-08T16:00:00Z",
        "locks_at": "2020-09-13T17:00:00Z",
    }
    nfl_sync.refresh_injuries(store, week)
    assert store.week_updates == []


def test_sleeper_downloads_league_player_payload_only_once_per_refresh():
    from nfl_sources import SleeperProvider

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "qb1": {"full_name": "QB One", "position": "QB", "team": "DET", "active": True},
                "rb1": {"full_name": "RB One", "position": "RB", "team": "NO", "active": True},
                "wr1": {"full_name": "WR One", "position": "WR", "team": "DET", "active": True},
                "te1": {"full_name": "TE One", "position": "TE", "team": "NO", "active": True},
                "k1": {"full_name": "K One", "position": "K", "team": "DET", "active": True},
            }

    class Session:
        def __init__(self):
            self.calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            return Response()

    session = Session()
    provider = SleeperProvider(session=session)
    rows = {position: provider.active_players(position) for position in ("QB", "RB", "WR", "TE", "K")}

    assert session.calls == 1
    assert all(len(rows[position]) == 1 for position in rows)


def test_prefer_live_schedule_sync_preserves_precise_espn_state():
    class ScheduleStore:
        def __init__(self):
            self.saved = []
        def get_nfl_games(self, week_id):
            return [
                {
                    "provider_event_id": "live",
                    "game_status": "LIVE",
                    "period": 3,
                    "game_clock": "4:21",
                    "home_score": 21,
                    "away_score": 17,
                    "completed": False,
                },
                {
                    "provider_event_id": "final",
                    "game_status": "FINAL",
                    "period": 4,
                    "game_clock": "0:00",
                    "home_score": 31,
                    "away_score": 20,
                    "completed": True,
                },
            ]
        def upsert_nfl_games(self, week_id, games):
            self.saved = [dict(game) for game in games]
            return self.saved

    class ScheduleProvider:
        def schedule_games(self, season, nfl_week, week_id=None):
            return [
                {
                    "week_id": week_id,
                    "provider_event_id": "live",
                    "home_team": "DET",
                    "away_team": "NO",
                    "kickoff_at": "2026-09-13T17:00:00Z",
                    "is_eligible": True,
                    "game_status": "LIVE",
                    "period": None,
                    "game_clock": None,
                    "home_score": 0,
                    "away_score": 0,
                    "completed": False,
                },
                {
                    "week_id": week_id,
                    "provider_event_id": "final",
                    "home_team": "CIN",
                    "away_team": "TB",
                    "kickoff_at": "2026-09-13T17:00:00Z",
                    "is_eligible": True,
                    "game_status": "FINAL",
                    "period": None,
                    "game_clock": None,
                    "home_score": 0,
                    "away_score": 0,
                    "completed": True,
                },
            ]

    store = ScheduleStore()
    games = nfl_sync.sync_schedule(store, _week(), nflverse=ScheduleProvider(), prefer_live=True)
    by_id = {game["provider_event_id"]: game for game in games}

    assert by_id["live"]["period"] == 3
    assert by_id["live"]["game_clock"] == "4:21"
    assert by_id["live"]["home_score"] == 21
    assert by_id["final"]["game_status"] == "FINAL"
    assert by_id["final"]["home_score"] == 31
    assert by_id["final"]["away_score"] == 20
