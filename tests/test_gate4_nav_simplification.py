from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_nav_has_four_non_overlapping_destinations():
    text = (ROOT / "gate4_ui.py").read_text()
    assert 'options = ["🏈 Sunday", "🏆 Season", "🕘 History", "👤 Profile"]' in text
    assert ':material/emoji_events: Season' in text
    assert ':material/leaderboard:' not in text


def test_old_leaderboard_session_migrates_to_season():
    text = (ROOT / "gate4_ui.py").read_text()
    assert 'if default == "🏆 Leaderboard":' in text
    assert 'default = "🏆 Season"' in text


def test_production_router_sends_season_to_season_view():
    text = (ROOT / "weekly_ui.py").read_text()
    assert 'if tab == "🏆 Season":' in text
    assert 'render_leaderboards(store, week, player, phase)' in text
