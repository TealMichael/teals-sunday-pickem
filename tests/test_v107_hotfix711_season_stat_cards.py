from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import player_season_stats as stats

ROOT = Path(__file__).resolve().parents[1]
WEEK = {"id": "week-2", "season": 2026, "nfl_week": 2, "published_at": "2026-09-15T16:00:00+00:00"}
POOL = [
    {"id": "qb1", "position": "QB", "team_abbr": "BUF", "player_name": "Josh Allen", "is_visible": True},
    {"id": "rb1", "position": "RB", "team_abbr": "IND", "player_name": "Jonathan Taylor", "is_visible": True},
    {"id": "wr1", "position": "WR", "team_abbr": "MIN", "player_name": "Justin Jefferson", "is_visible": True},
    {"id": "te1", "position": "TE", "team_abbr": "KC", "player_name": "Travis Kelce", "is_visible": False},
    {"id": "k1", "position": "K", "team_abbr": "DAL", "player_name": "Brandon Aubrey", "is_visible": True},
]
ROWS = [
    {"week": "1", "season_type": "REG", "team": "BUF", "position": "QB", "player_display_name": "Josh Allen", "player_id": "a", "passing_yards": "250", "passing_tds": "2", "rushing_yards": "40"},
    {"week": "1", "season_type": "REG", "team": "IND", "position": "RB", "player_display_name": "Jonathan Taylor", "player_id": "b", "rushing_yards": "101", "receiving_yards": "22", "rushing_tds": "1", "receiving_tds": "0"},
    {"week": "1", "season_type": "REG", "team": "MIN", "position": "WR", "player_display_name": "Justin Jefferson", "player_id": "c", "receiving_yards": "94", "receptions": "7", "receiving_tds": "1"},
    {"week": "1", "season_type": "REG", "team": "KC", "position": "TE", "player_display_name": "Travis Kelce", "player_id": "d", "receiving_yards": "62", "receptions": "5", "receiving_tds": "1"},
    {"week": "1", "season_type": "REG", "team": "DAL", "position": "K", "player_display_name": "Brandon Aubrey", "player_id": "e", "fg_made": "2", "fg_att": "3", "pat_made": "4"},
]


def test_position_specific_snapshot_is_read_only_includes_hidden_reserves_and_filters_current_week():
    pool = deepcopy(POOL)
    original = deepcopy(pool)
    data = stats.build_snapshot(WEEK, pool, ROWS + [
        {**ROWS[0], "week": "2", "passing_yards": "1000"},
        {**ROWS[0], "week": "1", "season_type": "POST", "passing_yards": "900"},
    ])
    assert data["through_week"] == 1
    assert data["players"]["qb1"] == {"gp": 1, "passing_yards_pg": 250, "passing_tds": 2, "rushing_yards_pg": 40}
    assert data["players"]["rb1"]["total_tds"] == 1
    assert data["players"]["wr1"]["receptions_pg"] == 7
    assert data["players"]["te1"]["receiving_yards_pg"] == 62  # hidden replacement ready
    assert data["players"]["k1"]["fg_pct"] == 66.7
    assert pool == original
    enriched = stats.attach_snapshot(pool, data)
    assert pool == original and enriched[0]["_season_stats"]["gp"] == 1
    assert "250.0 pass yds/g" in stats.stats_line(enriched[0])
    assert "FG 66.7%" in stats.stats_line(enriched[-1])


def test_averages_divide_by_recorded_games_not_team_weeks_and_do_not_double_count_week():
    week = {**WEEK, "nfl_week": 4}
    history = ROWS + [
        {**ROWS[2], "week": "2", "receiving_yards": "46", "receptions": "3", "receiving_tds": "0"},
        {**ROWS[2], "week": "2", "receiving_yards": "46", "receptions": "3", "receiving_tds": "0"},
        {**ROWS[2], "week": "4", "receiving_yards": "2000"},
    ]
    result = stats.build_snapshot(week, POOL, history)["players"]["wr1"]
    assert result == {"gp": 2, "receiving_yards_pg": 70, "receptions_pg": 5, "total_tds": 1}


def test_traded_player_uses_only_matching_stable_provider_id_across_teams():
    week = {**WEEK, "nfl_week": 4}
    traded = [
        {**ROWS[2], "week": "1", "team": "NYJ", "receiving_yards": "100"},
        {**ROWS[2], "week": "2", "team": "MIN", "receiving_yards": "60"},
        {**ROWS[2], "week": "3", "team": "NYJ", "player_id": "another-person", "receiving_yards": "1000"},
    ]
    result = stats.build_snapshot(week, POOL, traded)["players"]["wr1"]
    assert result["gp"] == 2 and result["receiving_yards_pg"] == 80


def test_missing_players_never_get_fabricated_zeros_and_no_divide_by_zero_kicker():
    result = stats.build_snapshot(WEEK, POOL, ROWS[:-1])
    assert "k1" not in result["players"]
    assert stats.stats_line({"position": "K"}) == "Season stats pending"
    single = stats.build_snapshot(WEEK, POOL, [dict(ROWS[-1], fg_made="0", fg_att="0", pat_made="0")])
    assert single["players"]["k1"]["fg_pct"] is None
    assert "FG —" in stats.stats_line({**POOL[-1], "_season_stats": single["players"]["k1"]})


def test_kicker_without_kicking_columns_is_unavailable_not_a_zero_season():
    unknown = {k: v for k, v in ROWS[-1].items() if k not in ("fg_made", "fg_att", "pat_made")}
    assert "k1" not in stats.build_snapshot(WEEK, POOL, [unknown])["players"]


class FakeStore:
    def __init__(self):
        self.meta = {}
        self.leases = set()
        self.pool_calls = 0
        self.writes = []

    def get_app_meta(self, key):
        return {"value": self.meta[key]} if key in self.meta else None

    def set_app_meta(self, key, value):
        self.meta[key] = value
        self.writes.append((key, deepcopy(value)))
        return {"value": value}

    def get_full_week_pool(self, week_id):
        self.pool_calls += 1
        assert week_id == WEEK["id"]
        return deepcopy(POOL)

    def claim_refresh_lease(self, key, *, owner, ttl_seconds):
        if key in self.leases:
            return False
        self.leases.add(key)
        return True

    def release_refresh_lease(self, key, *, owner):
        self.leases.discard(key)


class FakeProvider:
    def __init__(self, data=ROWS, error=False):
        self.data = data
        self.error = error
        self.calls = 0

    def weekly_player_stats(self, season):
        assert season == 2026
        self.calls += 1
        if self.error:
            raise OSError("offline")
        return deepcopy(self.data)


def test_one_shared_snapshot_and_no_repeat_provider_calls():
    store, provider = FakeStore(), FakeProvider()
    first = stats.load_or_prepare_snapshot(store, WEEK, provider=provider)
    second = stats.load_or_prepare_snapshot(store, WEEK, provider=provider)
    assert first == second and first["through_week"] == 1
    assert provider.calls == 1 and store.pool_calls == 1 and len(store.writes) == 1
    assert not store.leases
    assert stats.load_or_prepare_snapshot(store, {**WEEK, "is_demo": True}, provider=provider) is None
    assert stats.load_or_prepare_snapshot(store, {**WEEK, "published_at": None}, provider=provider) is None


def test_provider_failure_cools_down_and_does_not_break_picks():
    store, provider = FakeStore(), FakeProvider(error=True)
    assert stats.load_or_prepare_snapshot(store, WEEK, provider=provider) is None
    assert stats.load_or_prepare_snapshot(store, WEEK, provider=provider) is None
    assert provider.calls == 1 and not store.leases
    assert "retry_after" in store.meta[stats.snapshot_key(WEEK)]


def test_busy_lease_cannot_create_another_provider_request():
    store, provider = FakeStore(), FakeProvider()
    store.leases.add("season-card-stats:2026:2")
    assert stats.load_or_prepare_snapshot(store, WEEK, provider=provider) is None
    assert provider.calls == 0 and store.pool_calls == 0


def test_weekly_player_cards_keep_single_tap_target_and_warm_deploy():
    ui = (ROOT / "weekly_ui.py").read_text()
    app = (ROOT / "app.py").read_text()
    config = (ROOT / "config.py").read_text()
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.11"' in config
    assert 'WEEKLY_UI_SCHEMA_VERSION = 11' in ui
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 11' in app
    assert 'label = f"{check}**{name}**{badge}\\n{meta}{season_strip}{extra}"' in ui
    assert "st.button(" in ui and "pool = attach_snapshot(pool, load_or_prepare_snapshot(store, week))" in ui
    assert "_render_pool_change_disclaimer()" in ui
