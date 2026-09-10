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


def test_live_rehearsal_does_not_drop_scoring_rows_when_espn_position_is_missing_and_identity_is_unmatched():
    class ESPNWithPositionlessReceiving(FakeESPN):
        def summary(self, event_id):
            payload = super().summary(event_id)
            payload["boxscore"]["players"][0]["statistics"].append({
                "name": "receiving",
                "labels": ["REC", "YDS", "TD"],
                "athletes": [{
                    "athlete": {"id": "3", "displayName": "Live Receiver"},
                    "stats": ["2", "21", "0"],
                }],
            })
            return payload

    result = run_live_game_rehearsal(
        ReadOnlyStore(),
        season=2026,
        nfl_week=1,
        provider_event_id="401999999",
        nflverse=FakeNFLverse(),
        espn=ESPNWithPositionlessReceiving(),
    )

    receiver = next(row for row in result["rows"] if row["player_name"] == "Live Receiver")
    assert receiver["position"] == "REC"
    assert receiver["matched_cached_player"] is False
    assert receiver["points"] == 3.1
    assert "2 receptions" in receiver["stat_formula"]
    assert "21 receiving yds" in receiver["stat_formula"]
    assert result["category_samples"]["Receiving"]["player_name"] == "Live Receiver"


def test_live_rehearsal_prefers_cached_position_over_missing_espn_position_for_exact_production_match():
    class ESPNPositionlessQB(FakeESPN):
        def summary(self, event_id):
            payload = super().summary(event_id)
            for category in payload["boxscore"]["players"][0]["statistics"]:
                for athlete_row in category.get("athletes") or []:
                    if (athlete_row.get("athlete") or {}).get("displayName") == "Test Quarterback":
                        athlete_row["athlete"].pop("position", None)
            return payload

    result = run_live_game_rehearsal(
        ReadOnlyStore(),
        season=2026,
        nfl_week=1,
        provider_event_id="401999999",
        nflverse=FakeNFLverse(),
        espn=ESPNPositionlessQB(),
    )
    qb = next(row for row in result["rows"] if row["player_name"] == "Test Quarterback")
    assert qb["position"] == "QB"
    assert qb["matched_cached_player"] is True
    assert "247 passing yds" in qb["stat_formula"]


def test_live_rehearsal_explains_exact_key_miss_when_cached_team_differs():
    class StoreWithStaleTeam(ReadOnlyStore):
        def get_nfl_players(self):
            rows = super().get_nfl_players()
            rows.append({
                "full_name": "Live Receiver",
                "canonical_key": "livereceiver",
                "position": "WR",
                "team_abbr": "OLD",
                "sleeper_player_id": "stale-1",
                "last_synced_at": "2026-09-09T12:00:00+00:00",
            })
            return rows

    class ESPNWithReceiver(FakeESPN):
        def summary(self, event_id):
            payload = super().summary(event_id)
            payload["boxscore"]["players"][0]["statistics"].append({
                "name": "receiving",
                "labels": ["REC", "YDS", "TD"],
                "athletes": [{
                    "athlete": {"id": "3", "displayName": "Live Receiver"},
                    "stats": ["2", "21", "0"],
                }],
            })
            return payload

    result = run_live_game_rehearsal(
        StoreWithStaleTeam(),
        season=2026,
        nfl_week=1,
        provider_event_id="401999999",
        nflverse=FakeNFLverse(),
        espn=ESPNWithReceiver(),
    )
    diag = next(row for row in result["unmatched_diagnostics"] if row["player_name"] == "Live Receiver")
    assert "team OLD" in diag["reason"]
    assert diag["top_candidate"]["full_name"] == "Live Receiver"
    assert diag["top_candidate"]["similarity"] == 1.0
    assert result["cached_player_count"] == 3
    assert result["cache_latest_synced_at"] == "2026-09-09T12:00:00+00:00"


def test_live_rehearsal_surfaces_close_same_team_name_candidate_without_mutating_match_rule():
    class StoreWithNameVariant(ReadOnlyStore):
        def get_nfl_players(self):
            rows = super().get_nfl_players()
            rows.append({
                "full_name": "Jaxon Smith Njigba",
                "canonical_key": "jaxonsmithnjigba",
                "position": "WR",
                "team_abbr": "SEA",
                "sleeper_player_id": "variant-1",
            })
            return rows

    class ESPNWithVariant(FakeESPN):
        def summary(self, event_id):
            payload = super().summary(event_id)
            payload["boxscore"]["players"].append({
                "team": {"abbreviation": "SEA"},
                "statistics": [{
                    "name": "receiving",
                    "labels": ["REC", "YDS", "TD"],
                    "athletes": [{
                        "athlete": {"id": "9", "displayName": "Jaxon Smith-Njigba Jr"},
                        "stats": ["3", "31", "0"],
                    }],
                }],
            })
            return payload

    result = run_live_game_rehearsal(
        StoreWithNameVariant(),
        season=2026,
        nfl_week=1,
        provider_event_id="401999999",
        nflverse=FakeNFLverse(),
        espn=ESPNWithVariant(),
    )
    # normalize_name already removes Jr and punctuation, so this should become
    # an exact production key rather than a fuzzy fallback.
    row = next(row for row in result["rows"] if row["player_name"] == "Jaxon Smith-Njigba Jr")
    assert row["matched_cached_player"] is True


def test_commissioner_ui_has_read_only_why_unmatched_identity_diagnostic():
    text = open("gate5_ui.py", encoding="utf-8").read()
    assert "Why unmatched?" in text
    assert "Read-only identity diagnosis" in text
    assert "it does not change production matching or any Week 1 data" in text
    assert "Why exact key missed" in text
    assert "Best cached candidate" in text
