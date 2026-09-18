"""Regression: keep iPhone Profile tappable while docking nav closer to Streamlit host chrome."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_nav_docks_snugly_above_owner_chrome():
    ui = (ROOT / "ui.py").read_text("utf-8")
    mobile = ui.split("@media (max-width: 480px)", 1)[1].split("</style>", 1)[0]
    nav = mobile.split('div[class*="st-key-gate4_nav"] {', 1)[1].split("}", 1)[0]
    match = re.search(r'bottom:calc\(([\d.]+)rem \+ env\(safe-area-inset-bottom, 0px\)\)', nav)
    assert match, "mobile nav must still clear owner chrome and device safe area"
    bottom_rem = float(match.group(1))
    assert 3.8 <= bottom_rem <= 4.4, bottom_rem
    assert 'width:calc(100vw - 1rem) !important' in nav
    assert 'padding:.3rem .4rem !important' in nav
    assert '5.5rem' not in nav
    assert 'padding-bottom:12.75rem' in mobile
    assert 'flex-wrap:nowrap !important' in ui


def test_hotfix_loads_new_css_in_warm_streamlit_worker():
    app = (ROOT / "app.py").read_text("utf-8")
    config = (ROOT / "config.py").read_text("utf-8")
    css = (ROOT / "ui.py").read_text("utf-8")
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.15.2"' in config
    assert 'getattr(_config, "APP_BUILD_VERSION", "") != "1.0.7-hotfix7.15.2"' in app
    assert 'UI_THEME_SCHEMA_VERSION = 4' in css
    assert 'getattr(_ui, "UI_THEME_SCHEMA_VERSION", 0) < 4' in app
