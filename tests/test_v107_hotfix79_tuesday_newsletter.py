from pathlib import Path

from newsletter import build_tuesday_newsletter, compact_final_standings, perfect_lineup, sms_segment_estimate

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def _pool_row(position, name, score, rank=1, visible=True):
    return {
        "id": f"{position}-{name}",
        "position": position,
        "player_name": name,
        "score_total": score,
        "slot_rank": rank,
        "is_visible": visible,
    }


def test_hotfix79_build_and_commissioner_newsletter_contract():
    config = (ROOT / "config.py").read_text("utf-8")
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    store = (ROOT / "store.py").read_text("utf-8")

    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.9"' in config
    assert 'commissioner_tools = ["Week", "Newsletter", "Players", "Corrections", "Clock", "Diagnostics"]' in ui
    assert 'GATE5_UI_SCHEMA_VERSION = 5' in ui
    assert 'elif tool == "Newsletter":' in ui
    assert '_render_newsletter(store, week)' in ui
    assert 'getattr(_gate5_ui, "GATE5_UI_SCHEMA_VERSION", 0) < 5' in app
    assert 'STORE_SCHEMA_VERSION = 3' in store
    assert 'def get_app_meta(' in store
    assert 'def set_app_meta(' in store
    assert 'getattr(_store, "STORE_SCHEMA_VERSION", 0) < 3' in app


def test_perfect_lineup_uses_only_visible_25_and_manual_override():
    rows = []
    for pos in POSITIONS:
        rows.append(_pool_row(pos, f"Best {pos}", 20, 1, True))
        rows.append(_pool_row(pos, f"Second {pos}", 10, 2, True))
        rows.append(_pool_row(pos, f"Hidden {pos}", 999, 6, False))
    rows[0]["manual_score_override"] = 25

    result = perfect_lineup(rows)
    assert result["complete"] is True
    assert [row["position"] for row in result["players"]] == list(POSITIONS)
    assert all(not str(row["player_name"]).startswith("Hidden") for row in result["players"])
    assert result["score"] == 105.0


def test_compact_final_standings_keeps_competition_ranks_and_every_participant():
    results = [
        {"finish_rank": 1, "nickname_snapshot": "Mike", "weekly_score": 100.0},
        {"finish_rank": 1, "nickname_snapshot": "Tim", "weekly_score": 100.0},
        {"finish_rank": 3, "nickname_snapshot": "Jenny", "weekly_score": 95.5},
    ]
    assert compact_final_standings(results) == "1 Mike 100.0 | 1 Tim 100.0 | 3 Jenny 95.5"


def test_tuesday_newsletter_has_required_short_text_sections():
    final_results = [
        {"player_id": "p1", "finish_rank": 1, "nickname_snapshot": "Mike", "weekly_score": 110.4, "season_points": 12, "nfl_week": 1},
        {"player_id": "p2", "finish_rank": 2, "nickname_snapshot": "Jenny", "weekly_score": 104.2, "season_points": 9, "nfl_week": 1},
    ]
    perfect = {
        "complete": True,
        "score": 145.6,
        "players": [
            {"position": "QB", "short_name": "Allen"},
            {"position": "RB", "short_name": "Barkley"},
            {"position": "WR", "short_name": "Jefferson"},
            {"position": "TE", "short_name": "Kelce"},
            {"position": "K", "short_name": "Aubrey"},
        ],
    }
    text = build_tuesday_newsletter(
        final_week={"nfl_week": 1},
        final_results=final_results,
        perfect=perfect,
        season_results=final_results,
        next_week={"nfl_week": 2},
        lineup_url="https://pickem.example",
    )
    assert "Week 1 Final" in text
    assert "Final: 1 Mike 110.4 | 2 Jenny 104.2" in text
    assert "Perfect 5: QB Allen • RB Barkley • WR Jefferson • TE Kelce • K Aubrey = 145.6" in text
    assert "Season leader: Mike — 12 pts" in text
    assert "Set Week 2: https://pickem.example" in text
    assert len(text) < 400


def test_sms_segment_estimate_handles_unicode_newsletter():
    text = "🏈 " + ("x" * 140)
    assert sms_segment_estimate(text) == 3
