from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_weekly_leaderboard_is_not_duplicated_in_season_destination():
    text = (ROOT / "gate4_ui.py").read_text()
    assert 'def _leaderboard_view_switcher()' not in text
    block = text.split('def render_leaderboards', 1)[1].split('def render_history', 1)[0]
    assert 'st.markdown("### Season")' in block
    assert '_render_season_rows' in block
    assert '_leaderboard_rows' not in block
    assert 'This Week' not in block


def test_roster_detail_renders_inline_beneath_selected_row():
    text = (ROOT / "gate4_ui.py").read_text()
    block = text.split('def _leaderboard_rows', 1)[1].split('def render_live_sunday', 1)[0]
    assert 'if detail and selected_id == row_player_id:' in block
    assert '_render_roster_detail(row, current_player_id)' in block
    assert 'st.rerun()' in block


def test_gate4_visual_polish_css_present():
    css = (ROOT / "ui.py").read_text()
    for needle in [
        '.story-grid',
        '.profile-grid',
        '.history-card',
        'st-key-gate4_nav',
        'button[aria-pressed="true"]',
    ]:
        assert needle in css


def test_demo_separates_current_week_and_season_destinations():
    text = (ROOT / "gate4_ui.py").read_text()
    demo = text.split('def render_gate4_demo', 1)[1]
    assert 'if tab == "🏈 Sunday":' in demo
    assert 'elif tab == "🏆 Season":' in demo
    assert '_leaderboard_rows(leaderboard, demo_player_id, detail=True)' in demo
    assert '_render_season_rows' in demo
    assert '_leaderboard_view_switcher()' not in demo
