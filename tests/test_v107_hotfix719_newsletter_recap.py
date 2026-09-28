from pathlib import Path

from newsletter import (
    build_tuesday_newsletter,
    commissioner_story,
    compact_season_top_five,
)

ROOT = Path(__file__).resolve().parents[1]


def _result(player_id, name, week, rank, score, season_points):
    return {
        "player_id": player_id,
        "nickname_snapshot": name,
        "nfl_week": week,
        "finish_rank": rank,
        "weekly_score": score,
        "season_points": season_points,
    }


def test_week3_tie_becomes_one_commissioner_style_sentence():
    final_results = [
        _result("crane", "Crane", 3, 1, 117.5, 12),
        _result("jenny", "Jenny", 3, 1, 117.5, 12),
        _result("jackson", "Jackson", 3, 3, 103.2, 7),
        _result("neiljo", "Neiljo", 3, 3, 103.2, 7),
    ]
    story = commissioner_story(
        final_week={"nfl_week": 3},
        final_results=final_results,
        perfect={"complete": True, "score": 124.5, "players": []},
        season_results=final_results,
    )
    assert story == (
        "Crane and Jenny shared the Week 3 crown at 117.5, "
        "finishing just 7.0 points shy of the perfect possible lineup."
    )


def test_newsletter_keeps_every_weekly_finisher_but_only_five_season_entries():
    final_results = [
        _result("p1", "Alpha", 3, 1, 120.0, 12),
        _result("p2", "Bravo", 3, 2, 110.0, 9),
        _result("p3", "Charlie", 3, 3, 100.0, 7),
        _result("p4", "Delta", 3, 4, 90.0, 6),
        _result("p5", "Echo", 3, 5, 80.0, 5),
        _result("p6", "Foxtrot", 3, 6, 70.0, 4),
    ]
    text = build_tuesday_newsletter(
        final_week={"nfl_week": 3},
        final_results=final_results,
        perfect={"complete": True, "score": 150.0, "players": []},
        season_results=final_results,
        next_week={"nfl_week": 4},
        lineup_url="https://pickem.example",
    )
    weekly = next(line for line in text.splitlines() if line.startswith("🏆 Week 3:"))
    season = next(line for line in text.splitlines() if line.startswith("📈 Season Top 5:"))
    assert "Foxtrot 70.0" in weekly
    assert "Alpha 12 pts" in season
    assert "Echo 5 pts" in season
    assert "Foxtrot" not in season
    assert "Perfect 5:" not in text
    assert "👉 Week 4 lineup: https://pickem.example" in text


def test_compact_season_top_five_uses_app_season_order():
    rows = [
        _result("p1", "Alpha", 1, 1, 100.0, 12),
        _result("p2", "Bravo", 1, 2, 99.0, 9),
        _result("p3", "Charlie", 1, 3, 98.0, 7),
        _result("p4", "Delta", 1, 4, 97.0, 6),
        _result("p5", "Echo", 1, 5, 96.0, 5),
        _result("p6", "Foxtrot", 1, 6, 95.0, 4),
    ]
    summary = compact_season_top_five(rows)
    assert summary == (
        "1 Alpha 12 pts • 2 Bravo 9 pts • 3 Charlie 7 pts • "
        "4 Delta 6 pts • 5 Echo 5 pts"
    )


def test_commissioner_story_can_be_omitted_when_nothing_is_notable():
    season_results = [
        _result("a", "Alpha", 1, 1, 110.0, 12),
        _result("b", "Bravo", 1, 2, 100.0, 9),
        _result("c", "Charlie", 1, 3, 90.0, 7),
        _result("d", "Delta", 1, 4, 80.0, 6),
        _result("e", "Echo", 1, 5, 70.0, 5),
        _result("a", "Alpha", 2, 2, 114.0, 9),
        _result("b", "Bravo", 2, 1, 115.0, 12),
        _result("c", "Charlie", 2, 3, 90.0, 7),
        _result("d", "Delta", 2, 4, 80.0, 6),
        _result("e", "Echo", 2, 5, 70.0, 5),
        _result("a", "Alpha", 3, 1, 100.0, 12),
        _result("b", "Bravo", 3, 2, 95.0, 9),
        _result("c", "Charlie", 3, 3, 90.0, 7),
        _result("d", "Delta", 3, 4, 85.0, 6),
        _result("e", "Echo", 3, 5, 80.0, 5),
    ]
    final_results = [row for row in season_results if row["nfl_week"] == 3]
    story = commissioner_story(
        final_week={"nfl_week": 3},
        final_results=final_results,
        perfect={"complete": True, "score": 130.0, "players": []},
        season_results=season_results,
    )
    assert story is None


def test_new_season_leader_is_an_interesting_story():
    season_results = [
        _result("a", "Alpha", 1, 1, 110.0, 12),
        _result("b", "Bravo", 1, 2, 100.0, 9),
        _result("b", "Bravo", 2, 1, 125.0, 12),
        _result("a", "Alpha", 2, 2, 101.0, 9),
    ]
    final_results = [row for row in season_results if row["nfl_week"] == 2]
    story = commissioner_story(
        final_week={"nfl_week": 2},
        final_results=final_results,
        perfect={"complete": True, "score": 150.0, "players": []},
        season_results=season_results,
    )
    assert story == "Bravo moved into the season lead with 21 points after Week 2."


def test_hotfix719_warm_reload_and_fingerprint_contract():
    config = (ROOT / "config.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")
    newsletter = (ROOT / "newsletter.py").read_text("utf-8")

    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.19"' in config
    assert 'GATE5_UI_SCHEMA_VERSION = 9' in ui
    assert 'NEWSLETTER_LOGIC_SCHEMA_VERSION = 2' in newsletter
    assert 'getattr(_gate5_ui, "GATE5_UI_SCHEMA_VERSION", 0) < 9' in app
    assert 'getattr(_newsletter, "NEWSLETTER_LOGIC_SCHEMA_VERSION", 0) < 2' in ui
    assert 'for row in data.get("season_results") or []' in ui
