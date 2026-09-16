"""Regression cases from the full pre-Sunday safety audit."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import nfl_sync
from gate4 import game_status_text
from store import StoreError, SupabaseStore


class StaleScoreboard:
    def __init__(self, status="SCHEDULED"):
        self.status = status

    def scoreboard(self, season, nfl_week):
        return {"events": ["stale"]}

    def normalize_games(self, payload, week_id):
        return [{
            "week_id": week_id, "provider_event_id": "event-1",
            "home_team": "BUF", "away_team": "NYJ", "game_status": self.status,
            "completed": False, "period": None, "game_clock": None,
            "home_score": 0, "away_score": 0,
            "kickoff_at": "2026-09-20T17:00:00+00:00", "is_eligible": True,
        }]


class ScoreboardStore:
    def __init__(self, status="FINAL"):
        self.previous = {
            "week_id": "w", "provider_event_id": "event-1", "home_team": "BUF",
            "away_team": "NYJ", "game_status": status, "completed": status == "FINAL",
            "period": 4 if status == "FINAL" else 2,
            "game_clock": "0:00", "home_score": 27, "away_score": 17,
            "kickoff_at": "2026-09-20T17:00:00+00:00", "is_eligible": True,
            "provider_updated_at": "2026-09-20T20:00:00+00:00",
        }
        self.written = []

    def start_data_run(self, *args, **kwargs):
        return "run"

    def finish_data_run(self, *args, **kwargs):
        pass

    def get_nfl_games(self, *args, **kwargs):
        return [self.previous]

    def upsert_nfl_games(self, week_id, rows):
        self.written.extend(rows)

    def clear_week_cache(self, *args):
        pass


def test_stale_espn_scoreboard_must_not_revert_a_final_game_to_scheduled_zero():
    store = ScoreboardStore(status="FINAL")
    nfl_sync.refresh_live_game_state(store, {"id": "w", "season": 2026, "nfl_week": 2}, espn=StaleScoreboard())
    assert len(store.written) == 1
    assert store.written[0]["game_status"] == "FINAL"
    assert store.written[0]["home_score"] == 27
    assert store.written[0]["away_score"] == 17


def test_stale_espn_scoreboard_must_not_revert_live_game_to_scheduled_zero():
    store = ScoreboardStore(status="LIVE")
    nfl_sync.refresh_live_game_state(store, {"id": "w", "season": 2026, "nfl_week": 2}, espn=StaleScoreboard())
    assert store.written[0]["game_status"] == "LIVE"
    assert store.written[0]["home_score"] == 27


def test_partial_schedule_fails_before_writing_any_pool_rows():
    store = SupabaseStore.__new__(SupabaseStore)
    store.get_full_week_pool = lambda week_id: [
        {"id": "qb", "position": "QB", "team_abbr": "BUF", "slot_rank": 1, "is_visible": True},
        {"id": "rb", "position": "RB", "team_abbr": "NYJ", "slot_rank": 1, "is_visible": True},
    ]
    writes = []
    store._table = lambda table: writes.append(table)  # never reached on partial feed
    try:
        store.reconcile_pool_schedule(
            {"id": "w", "published_at": "2026-09-15T16:00:00Z"},
            [{"home_team": "BUF", "away_team": "MIA", "is_eligible": True}],
        )
    except StoreError as exc:
        assert "incomplete" in str(exc).lower()
    else:
        raise AssertionError("An incomplete provider schedule must not mutate a published pool")
    assert writes == []


class StubUpsert:
    def __init__(self):
        self.payload = None

    def upsert(self, payload, *, on_conflict):
        self.payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=self.payload)


def test_repeated_unchanged_live_scoreboard_keeps_old_clock_freshness_timestamp():
    old = (datetime.now(timezone.utc) - timedelta(minutes=9)).isoformat()
    previous = {
        "provider_event_id": "event-1", "game_status": "LIVE", "period": 2,
        "game_clock": "0:00", "home_score": 19, "away_score": 10,
        "provider_updated_at": old,
    }
    store = SupabaseStore.__new__(SupabaseStore)
    store.get_nfl_games = lambda week_id: [previous]
    request = StubUpsert()
    store._table = lambda table: request
    result = store.upsert_nfl_games("w", [{
        "provider_event_id": "event-1", "game_status": "LIVE", "period": 2,
        "game_clock": "0:00", "home_score": 19, "away_score": 10,
    }])
    assert result[0]["provider_updated_at"] == old


def test_live_game_clock_change_advances_freshness_timestamp():
    old = (datetime.now(timezone.utc) - timedelta(minutes=9)).isoformat()
    previous = {
        "provider_event_id": "event-1", "game_status": "LIVE", "period": 2,
        "game_clock": "0:00", "home_score": 19, "away_score": 10,
        "provider_updated_at": old,
    }
    store = SupabaseStore.__new__(SupabaseStore)
    store.get_nfl_games = lambda week_id: [previous]
    request = StubUpsert()
    store._table = lambda table: request
    result = store.upsert_nfl_games("w", [{
        "provider_event_id": "event-1", "game_status": "LIVE", "period": 3,
        "game_clock": "15:00", "home_score": 19, "away_score": 10,
    }])
    assert result[0]["provider_updated_at"] != old


def test_unchanged_live_scoreboard_after_seven_minutes_hides_clock_not_score():
    old = (datetime.now(timezone.utc) - timedelta(minutes=9)).isoformat()
    prior = {
        "provider_event_id": "event-1", "game_status": "LIVE", "period": 2,
        "game_clock": "0:00", "home_score": 19, "away_score": 10,
        "provider_updated_at": old,
    }
    store = SupabaseStore.__new__(SupabaseStore)
    store.get_nfl_games = lambda week_id: [prior]
    request = StubUpsert()
    store._table = lambda table: request
    updated = store.upsert_nfl_games("w", [dict(prior)])[0]
    assert game_status_text({"team_abbr": "BUF"}, {"BUF": updated}) == "LIVE"
    assert updated["home_score"] == 19


class ScheduleStore:
    def __init__(self):
        self.original = {
            "week_id": "w", "provider_event_id": "event-1", "home_team": "BUF",
            "away_team": "NYJ", "game_status": "LIVE", "completed": False,
            "period": 3, "game_clock": "10:51", "home_score": 19,
            "away_score": 10, "kickoff_at": "2026-09-20T17:00:00+00:00",
            "is_eligible": True,
        }
        self.written = []

    def get_nfl_games(self, week_id):
        return [self.original]

    def upsert_nfl_games(self, week_id, rows):
        self.written.extend(rows)


class DelayedScheduleProvider:
    def schedule_games(self, season, nfl_week, week_id):
        return [{
            "week_id": week_id, "provider_event_id": "event-1",
            "home_team": "BUF", "away_team": "NYJ", "game_status": "SCHEDULED",
            "completed": False, "period": None, "game_clock": None,
            "home_score": 0, "away_score": 0,
            "kickoff_at": "2026-09-20T17:00:00+00:00", "is_eligible": True,
        }]


def test_lagging_schedule_does_not_reset_live_game_during_five_minute_worker():
    store = ScheduleStore()
    games = nfl_sync.sync_schedule(
        store, {"id": "w", "season": 2026, "nfl_week": 2},
        nflverse=DelayedScheduleProvider(), prefer_live=True,
    )
    assert games[0]["game_status"] == "LIVE"
    assert games[0]["home_score"] == 19
    assert games[0]["game_clock"] == "10:51"
    assert store.written[0]["game_status"] == "LIVE"
