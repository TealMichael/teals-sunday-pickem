from live_dress_rehearsal import (
    compare_rehearsal_snapshots,
    discover_rehearsal_games,
    run_live_game_rehearsal,
)


class FakeNFLverse:
    def schedule_games(self, season, week, week_id=None, *, game_type="REG"):
        assert season == 2026
        assert week == 1
        assert game_type == "REG"
        return [
            {
                "provider_event_id": "401999999",
                "away_team": "NE",
                "home_team": "SEA",
                "kickoff_at": "2026-09-10T00:20:00+00:00",
                "game_status": "LIVE",
                "is_eligible": False,
            }
        ]


class FakeESPN:
    def summary(self, event_id):
        assert event_id == "401999999"
        return {
            "header": {
                "competitions": [
                    {
                        "status": {
                            "period": 2,
                            "displayClock": "08:41",
                            "type": {"state": "in", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "away", "score": "10", "team": {"abbreviation": "NE"}},
                            {"homeAway": "home", "score": "7", "team": {"abbreviation": "SEA"}},
                        ],
                    }
                ]
            },
            "boxscore": {
                "players": [
                    {
                        "team": {"abbreviation": "NE"},
                        "statistics": [
                            {
                                "name": "passing",
                                "labels": ["YDS", "TD", "INT"],
                                "athletes": [
                                    {
                                        "athlete": {
                                            "id": "1",
                                            "displayName": "Test Quarterback",
                                            "position": {"abbreviation": "QB"},
                                        },
                                        "stats": ["247", "2", "1"],
                                    }
                                ],
                            },
                            {
                                "name": "rushing",
                                "labels": ["YDS", "TD"],
                                "athletes": [
                                    {
                                        "athlete": {
                                            "id": "1",
                                            "displayName": "Test Quarterback",
                                            "position": {"abbreviation": "QB"},
                                        },
                                        "stats": ["18", "0"],
                                    }
                                ],
                            },
                            {
                                "name": "kicking",
                                "labels": ["FG", "XP"],
                                "athletes": [
                                    {
                                        "athlete": {
                                            "id": "2",
                                            "displayName": "Test Kicker",
                                            "position": {"abbreviation": "PK"},
                                        },
                                        "stats": ["2/2", "3/3"],
                                    }
                                ],
                            },
                        ],
                    }
                ]
            },
        }

    def player_stats(self, payload):
        from nfl_sources import ESPNProvider

        return ESPNProvider.player_stats(payload)


class ReadOnlyStore:
    def __init__(self):
        self.reads = 0

    def get_nfl_players(self):
        self.reads += 1
        return [
            {
                "full_name": "Test Quarterback",
                "canonical_key": "testquarterback",
                "position": "QB",
                "team_abbr": "NE",
            },
            {
                "full_name": "Test Kicker",
                "canonical_key": "testkicker",
                "position": "K",
                "team_abbr": "NE",
            },
        ]


def test_discover_live_rehearsal_game_is_read_only_schedule_discovery():
    games = discover_rehearsal_games(season=2026, nfl_week=1, nflverse=FakeNFLverse())
    assert len(games) == 1
    assert games[0]["provider_event_id"] == "401999999"
    assert "NE @ SEA" in games[0]["label"]


def test_live_rehearsal_uses_real_parser_scoring_and_cached_identity_matching_without_writes():
    store = ReadOnlyStore()
    result = run_live_game_rehearsal(
        store,
        season=2026,
        nfl_week=1,
        provider_event_id="401999999",
        nflverse=FakeNFLverse(),
        espn=FakeESPN(),
    )

    assert result["read_only"] is True
    assert result["espn_status"] == "LIVE"
    assert result["away_score"] == 10
    assert result["home_score"] == 7
    assert result["fantasy_rows"] == 2
    assert result["matched_rows"] == 2
    assert result["match_rate"] == 1.0
    assert store.reads == 1

    qb = result["samples"]["QB"]
    assert qb["points"] == 17.68
    assert qb["points_formula"] == "9.9 + 8.0 − 2.0 + 1.8 = 17.7 pts"
    assert "247 passing yds" in qb["stat_formula"]

    kicker = result["samples"]["K"]
    assert kicker["points"] == 9.0
    assert "2 FG made" in kicker["stat_formula"]
    assert "3 XP made" in kicker["stat_formula"]


def test_live_rehearsal_snapshot_comparison_detects_moving_stats():
    previous = {
        "espn_status": "LIVE",
        "rows": [
            {
                "key": "NE:testquarterback",
                "player_name": "Test Quarterback",
                "position": "QB",
                "team_abbr": "NE",
                "points": 10.0,
                "raw_stats": {"passing_yards": 150},
            }
        ],
    }
    current = {
        "espn_status": "LIVE",
        "rows": [
            {
                "key": "NE:testquarterback",
                "player_name": "Test Quarterback",
                "position": "QB",
                "team_abbr": "NE",
                "points": 14.0,
                "raw_stats": {"passing_yards": 250},
            }
        ],
    }
    comparison = compare_rehearsal_snapshots(previous, current)
    assert comparison["changed_players"] == 1
    assert comparison["score_changes"][0]["delta"] == 4.0
    assert comparison["status_changed"] is False


def test_commissioner_ui_labels_live_test_as_read_only_and_passes_real_week_context():
    text = open("gate5_ui.py", encoding="utf-8").read()
    assert "Wednesday Live Game Dress Rehearsal" in text
    assert "Commissioner-only and read-only" in text
    assert "It does not write Week 1 scores, lineups, standings, or NFL data." in text
    assert "_render_diagnostics(store, week)" in text
