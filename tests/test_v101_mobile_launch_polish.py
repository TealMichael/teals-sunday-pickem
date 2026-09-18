from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_nav_docks_above_owner_manage_app_controls():
    css = (ROOT / "ui.py").read_text("utf-8")
    assert 'bottom:calc(4.1rem + env(safe-area-inset-bottom, 0px)) !important' in css
    assert 'padding:.3rem .4rem !important' in css
    assert 'font-size:.75rem !important' in css
    assert 'content:"🏈"' not in css


def test_streamlit_portal_surfaces_are_forced_light():
    css = (ROOT / "ui.py").read_text("utf-8")
    for selector in ('[data-testid="stPopoverBody"]', '[data-baseweb="popover"]', '[data-baseweb="menu"]', '[role="dialog"]'):
        assert selector in css
    assert 'color-scheme:light !important' in css


def test_season_points_help_uses_inline_expander_not_popover():
    text = (ROOT / "gate4_ui.py").read_text("utf-8")
    block = text.split('def render_leaderboards', 1)[1].split('def render_history', 1)[0]
    assert 'with st.expander("ⓘ How season points work"):' in block
    assert 'getattr(st, "popover"' not in block
