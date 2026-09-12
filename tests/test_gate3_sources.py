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


def test_nflverse_schedule_parser_handles_2026_week_and_eligibility():
    from nfl_sources import NFLverseProvider

    csv_text = """game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,espn,away_moneyline,home_moneyline,spread_line,total_line\n2026_01_CHI_CAR,2026,REG,1,2026-09-13,Sunday,13:00,CHI,,CAR,,401000001,-110,-110,1.5,44.5\n2026_01_SF_LAR,2026,REG,1,2026-09-10,Thursday,20:35,SF,,LAR,,401000002,-110,-110,1.5,47.5\n2026_02_X_Y,2026,REG,2,2026-09-20,Sunday,13:00,X,,Y,,401000003,-110,-110,1.5,41.5\n"""

    class Response:
        text = csv_text
        def raise_for_status(self):
            return None

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    games = NFLverseProvider(Session()).schedule_games(2026, 1, "week-id")
    assert len(games) == 2
    by_id = {g["provider_event_id"]: g for g in games}
    assert by_id["401000001"]["is_eligible"] is True
    assert by_id["401000002"]["is_eligible"] is False
    assert by_id["401000001"]["kickoff_at"].startswith("2026-09-13T17:00:00")


def test_espn_scoreboard_tries_dates_year_then_season_shape():
    calls = []

    class Response:
        def __init__(self, ok): self.ok = ok
        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError("bad")
        def json(self): return {"events": []}

    class Session:
        def get(self, url, params=None, timeout=None):
            calls.append(dict(params or {}))
            return Response(ok=len(calls) > 1)

    ESPNProvider(Session()).scoreboard(2026, 1)
    assert calls[0]["dates"] == "2026"
    assert calls[1]["season"] == 2026


def test_espn_summary_prefers_cdn_and_unwraps_gamepackage():
    calls = []

    class Response:
        def raise_for_status(self): return None
        def json(self):
            return {"gamepackageJSON": {"boxscore": {"players": []}, "header": {"id": "401-test"}}}

    class Session:
        def get(self, url, params=None, timeout=None):
            calls.append((url, dict(params or {})))
            return Response()

    payload = ESPNProvider(Session()).summary("401-test")
    assert payload["header"]["id"] == "401-test"
    assert calls[0][0].endswith("/core/nfl/boxscore")
    assert calls[0][1] == {"xhr": 1, "gameId": "401-test"}


def test_nflverse_schedule_parser_can_load_preseason_rows():
    from nfl_sources import NFLverseProvider

    csv_text = """game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,espn,away_moneyline,home_moneyline,spread_line,total_line
2026_03_CHI_TEN,2026,PRE,3,2026-08-29,Saturday,18:00,CHI,24,TEN,15,401999999,-110,-110,1.0,36.5
"""

    class Response:
        text = csv_text
        def raise_for_status(self): return None

    class Session:
        def get(self, *args, **kwargs): return Response()

    games = NFLverseProvider(Session()).schedule_games(2026, 3, game_type="PRE")
    assert len(games) == 1
    assert games[0]["provider_event_id"] == "401999999"
    assert games[0]["home_score"] == 15
    assert games[0]["away_score"] == 24
