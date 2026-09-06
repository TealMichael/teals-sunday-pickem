from datetime import datetime, timezone

from nfl_sources import ESPNProvider, availability_from_injury, is_eligible_sunday_kickoff, normalize_name, normalize_team

UTC = timezone.utc


def test_sunday_eligibility_rule_is_exact():
    # Sep 13 2026 17:00 UTC = 1 PM ET
    assert is_eligible_sunday_kickoff(datetime(2026, 9, 13, 17, 0, tzinfo=UTC))
    assert is_eligible_sunday_kickoff(datetime(2026, 9, 13, 20, 25, tzinfo=UTC))
    assert not is_eligible_sunday_kickoff(datetime(2026, 9, 13, 16, 59, tzinfo=UTC))
    assert not is_eligible_sunday_kickoff(datetime(2026, 9, 10, 20, 0, tzinfo=UTC))
    assert not is_eligible_sunday_kickoff(datetime(2026, 9, 14, 20, 0, tzinfo=UTC))


def test_team_and_name_normalization_handles_provider_differences():
    assert normalize_team("JAC") == "JAX"
    assert normalize_team("WSH") == "WAS"
    assert normalize_name("Harold Fannin Jr.") == normalize_name("Harold Fannin")


def test_injury_mapping_keeps_doubtful_in_backup_warning_bucket():
    assert availability_from_injury(None) == "HEALTHY"
    assert availability_from_injury("Questionable") == "QUESTIONABLE"
    assert availability_from_injury("Doubtful") == "QUESTIONABLE"
    assert availability_from_injury("Out") == "OUT"
    assert availability_from_injury("IR") == "OUT"


def test_espn_game_normalization_marks_only_sunday_1pm_plus_eligible():
    payload = {"events": [
        {"id": "sun", "date": "2026-09-13T17:00:00Z", "competitions": [{
            "competitors": [
                {"homeAway": "home", "team": {"abbreviation": "CAR"}, "score": "0"},
                {"homeAway": "away", "team": {"abbreviation": "CHI"}, "score": "0"},
            ],
            "status": {"type": {"state": "pre", "completed": False}},
            "odds": [{"overUnder": 47.5, "spread": -3.5, "details": "CHI -3.5"}],
        }]},
        {"id": "thu", "date": "2026-09-10T20:00:00Z", "competitions": [{
            "competitors": [
                {"homeAway": "home", "team": {"abbreviation": "LAR"}},
                {"homeAway": "away", "team": {"abbreviation": "SF"}},
            ],
            "status": {"type": {"state": "pre", "completed": False}},
        }]},
    ]}
    games = ESPNProvider.normalize_games(payload)
    assert {g["provider_event_id"]: g["is_eligible"] for g in games} == {"sun": True, "thu": False}
    sunday = next(g for g in games if g["provider_event_id"] == "sun")
    assert sunday["favored_team"] == "CHI"
    assert sunday["over_under"] == 47.5


def test_espn_boxscore_parser_combines_categories_for_same_player():
    payload = {"boxscore": {"players": [{
        "team": {"abbreviation": "BUF"},
        "statistics": [
            {"name": "passing", "labels": ["C/ATT", "YDS", "TD", "INT"], "athletes": [
                {"athlete": {"id": "1", "displayName": "Josh Allen"}, "stats": ["20/30", "250", "2", "1"]}
            ]},
            {"name": "rushing", "labels": ["CAR", "YDS", "TD"], "athletes": [
                {"athlete": {"id": "1", "displayName": "Josh Allen"}, "stats": ["8", "40", "1"]}
            ]},
        ],
    }]}}
    rows = ESPNProvider.player_stats(payload)
    assert len(rows) == 1
    assert rows[0]["stats"]["passing_yards"] == 250
    assert rows[0]["stats"]["rushing_yards"] == 40
    assert rows[0]["espn_player_id"] == "1"
