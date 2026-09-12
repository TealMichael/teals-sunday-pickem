from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from clock_broadcast import (
    BEARS_BLUE,
    BEARS_ORANGE,
    GREEN,
    WHITE,
    _caleb_watch_rich,
    _live_games_rich,
    _player_updates_rich,
    _pulse_rich,
    _season_rich,
    _team_color,
    _weekly_rich,
    build_caleb_4k_watch,
)

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


class FakeSpecialStore:
    def __init__(self, status: str = "LIVE"):
        self.status = status

    def get_nfl_games(self, week_id: str):
        return [
            {
                "week_id": week_id,
                "provider_event_id": "401-test-bears",
                "home_team": "CHI",
                "away_team": "MIN",
                "kickoff_at": "2026-09-27T17:00:00+00:00",
                "game_status": self.status,
                "is_eligible": True,
            }
        ]


class FakeNFLverse:
    def __init__(self):
        self.calls = 0

    def weekly_player_stats(self, season: int, week=None):
        self.calls += 1
        return [
            {"season": str(season), "week": "1", "player_display_name": "Caleb Williams", "team": "CHI", "passing_yards": "250"},
            {"season": str(season), "week": "2", "player_display_name": "Caleb Williams", "team": "CHI", "passing_yards": "240"},
            {"season": str(season), "week": "2", "player_display_name": "Other QB", "team": "DET", "passing_yards": "999"},
        ]


class FakeESPN:
    def summary(self, event_id: str):
        assert event_id == "401-test-bears"
        return {"event": event_id}

    def player_stats(self, payload):
        return [
            {
                "team_abbr": "CHI",
                "player_name": "Caleb Williams",
                "position": "QB",
                "stats": {"passing_yards": 287},
            }
        ]


def _joined(fragments):
    return "".join(part["t"] for part in fragments)


def _colors(fragments):
    return [part["c"] for part in fragments]


def test_caleb_watch_live_includes_today_season_remaining_and_17_game_pace():
    nflverse = FakeNFLverse()
    watch = build_caleb_4k_watch(
        FakeSpecialStore("LIVE"),
        {"id": "w3", "season": 2026, "nfl_week": 3},
        now=datetime(2026, 9, 27, 19, 30, tzinfo=UTC),
        nflverse=nflverse,
        espn=FakeESPN(),
    )

    assert nflverse.calls == 1
    assert watch["is_live"] is True
    assert watch["today_yards"] == 287
    assert watch["baseline_yards"] == 490
    assert watch["season_yards"] == 777
    assert watch["remaining"] == 3223
    assert watch["games_played"] == 3
    assert watch["pace"] == 4403
    assert "🐻 CALEB 4K WATCH 🐻" in watch["text"]
    assert "TODAY: 287 YDS" in watch["text"]
    assert "SEASON: 777 YDS" in watch["text"]
    assert "3,223 TO 4K" in watch["text"]
    assert "PACE: 4,403" in watch["text"]
    assert "BEARS FANS, DON'T JINX IT" in watch["text"]
    assert watch["fragments"] == _caleb_watch_rich(
        today_yards=287,
        season_yards=777,
        remaining=3223,
        pace=4403,
        is_live=True,
    )


def test_caleb_watch_non_live_runs_once_per_hour_style_without_today():
    watch = build_caleb_4k_watch(
        FakeSpecialStore("SCHEDULED"),
        {"id": "w3", "season": 2026, "nfl_week": 3},
        now=datetime(2026, 9, 27, 16, 0, tzinfo=UTC),
        nflverse=FakeNFLverse(),
        espn=FakeESPN(),
    )
    assert watch["is_live"] is False
    assert watch["season_yards"] == 490
    assert watch["remaining"] == 3510
    assert watch["pace"] == 4165
    assert "TODAY:" not in watch["text"]
    assert "PACE: 4,165" in watch["text"]


def test_caleb_watch_reuses_week_baseline_instead_of_redownloading_nflverse():
    class ShouldNotCallNFLverse:
        def weekly_player_stats(self, season: int, week=None):
            raise AssertionError("cached weekly baseline should be reused")

    previous = {
        "baseline_week": 3,
        "baseline_yards": 490,
        "baseline_games": 2,
        "season_yards": 490,
        "today_yards": None,
    }
    watch = build_caleb_4k_watch(
        FakeSpecialStore("SCHEDULED"),
        {"id": "w3", "season": 2026, "nfl_week": 3},
        previous=previous,
        nflverse=ShouldNotCallNFLverse(),
        espn=FakeESPN(),
    )
    assert watch["baseline_yards"] == 490
    assert watch["pace"] == 4165


def test_nfl_live_ticker_colors_each_team_name_and_keeps_scores_white():
    rich = _live_games_rich([
        {
            "game_status": "LIVE",
            "kickoff_at": "2026-09-13T17:00:00+00:00",
            "away_team": "CHI",
            "home_team": "MIN",
            "away_score": 21,
            "home_score": 17,
            "period": 3,
            "game_clock": "4:22",
        }
    ])
    assert _joined(rich) == "NFL LIVE • CHI 21 • MIN 17 • Q3 4:22"
    chi = next(part for part in rich if part["t"] == "CHI")
    minny = next(part for part in rich if part["t"] == "MIN")
    assert chi["c"] == _team_color("CHI") == BEARS_ORANGE
    assert minny["c"] == _team_color("MIN")
    assert any(part["c"] == WHITE and "21" in part["t"] for part in rich)
    assert any(part["c"] == WHITE and "17" in part["t"] for part in rich)


def test_caleb_rich_message_mixes_bears_white_blue_and_pace_color():
    rich = _caleb_watch_rich(
        today_yards=287,
        season_yards=2941,
        remaining=1059,
        pace=4165,
        is_live=True,
    )
    assert _joined(rich) == (
        "🐻 CALEB 4K WATCH 🐻 • TODAY: 287 YDS • SEASON: 2,941 YDS • "
        "1,059 TO 4K • PACE: 4,165 👀 • BEARS FANS, DON'T JINX IT"
    )
    colors = _colors(rich)
    assert BEARS_ORANGE in colors
    assert BEARS_BLUE in colors
    assert WHITE in colors
    assert GREEN in colors


def test_pickem_messages_use_color_as_accents_not_full_line_paint():
    weekly = _weekly_rich(
        [
            {"rank": 1, "nickname": "Jenny", "score": 48.7},
            {"rank": 2, "nickname": "Mike", "score": 44.2},
        ],
        final=False,
    )
    season = _season_rich(
        [
            {"rank": 1, "nickname": "Jenny", "season_points": 24},
            {"rank": 2, "nickname": "Mike", "season_points": 19},
        ],
        2,
    )
    assert WHITE in _colors(weekly)
    assert WHITE in _colors(season)
    assert len(set(_colors(weekly))) >= 3
    assert len(set(_colors(season))) >= 3


def test_player_and_pulse_use_player_team_color_while_copy_stays_readable():
    pool = [
        {
            "id": "p1",
            "is_visible": True,
            "game_status": "LIVE",
            "score_total": 18.6,
            "player_name": "Jahmyr Gibbs",
            "team_abbr": "DET",
        }
    ]
    stats = [{"pool_player_id": "p1", "raw_stats": {"rushing_yards": 92, "rushing_tds": 1}}]
    player = _player_updates_rich(pool, stats)[0]
    assert any(part["t"] == "Jahmyr Gibbs" and part["c"] == _team_color("DET") for part in player)
    assert WHITE in _colors(player)

    pulse = _pulse_rich(
        {"most_popular": {"player_name": "Jahmyr Gibbs", "count": 8, "total": 10}, "went_alone": [], "same_brain": []},
        pool,
    )[0]
    assert any(part["t"] == "Jahmyr Gibbs" and part["c"] == _team_color("DET") for part in pulse)
    assert WHITE in _colors(pulse)


def test_hotfix7_clock_rotation_keeps_core_cadence_and_adds_caleb_slots():
    sql = (ROOT / "db/009_clock_colors_caleb_4k.sql").read_text("utf-8")

    for slot in (0, 3, 6, 9):
        assert f"when {slot} then v_category := 'weekly'" in sql
    for slot in (1, 4, 7, 10):
        assert f"when {slot} then v_category := 'live_games'" in sql

    assert "when 2 then v_category := case when v_caleb_live then 'caleb' else 'player' end" in sql
    assert "when 8 then v_category := 'caleb'" in sql
    assert "when v_caleb_live then 'player'" in sql
    assert "else v_category := 'manual';              -- :55" in sql


def test_sql_prefers_rich_fragments_and_keeps_pregame_privacy():
    sql = (ROOT / "db/009_clock_colors_caleb_4k.sql").read_text("utf-8")

    for key in (
        "readiness_rich",
        "weekly_rich",
        "live_games_rich",
        "player_updates_rich",
        "pulses_rich",
        "season_rich",
        "champion_rich",
    ):
        assert key in sql
    assert "'fragments', v_fragments" in sql
    assert "'c', 'F56600'" in sql
    assert "'c', 'FFFFFF'" in sql
    assert "FROM THE COMMISH • " in sql

    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("-- Post-lock broadcast rhythm", 1)[0]
    assert "weekly_rich" not in prelock
    assert "pulses_rich" not in prelock
    assert "v_caleb->'fragments'" not in prelock


def test_awtrix_passes_fragment_array_without_changing_poll_or_security_contract():
    text = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert "# @version 1.0.7-hotfix7" in text
    assert 'var fragments = data.find("fragments")' in text
    assert 'notify({"text": fragments' in text
    assert 'default=15 min=10 max=60 unit=sec' in text
    assert "self.ticks = 15" in text
    assert "/rest/v1/rpc/pickem_clock_feed" in text
    assert "SERVICE_ROLE" not in text.upper()


def test_test_clock_demonstrates_team_fragments_caleb_theme_and_worker_refreshes_specials():
    sql = (ROOT / "db/009_clock_colors_caleb_4k.sql").read_text("utf-8")
    worker = (ROOT / "scripts/nfl_refresh.py").read_text("utf-8")
    assert "NFL LIVE TEST • CHI 21 • MIN 17" in sql
    assert "🐻 CALEB 4K WATCH 🐻" in sql
    assert "'c', 'F56600'" in sql
    assert "'c', '5B7CFA'" in sql
    assert "refresh_clock_snapshot(store, target, refresh_specials=True)" in worker


def test_hotfix7_has_distinct_warm_deploy_generation():
    config = (ROOT / "config.py").read_text("utf-8")
    assert 'APP_VERSION = "1.0.7"' in config
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7"' in config


def test_hotfix7_does_not_enter_scoring_or_lineup_engines():
    scoring = (ROOT / "nfl_scoring.py").read_text("utf-8").lower()
    weekly = (ROOT / "weekly.py").read_text("utf-8").lower()
    assert "caleb 4k" not in scoring
    assert "caleb_4k" not in scoring
    assert "caleb 4k" not in weekly
    assert "caleb_4k" not in weekly
