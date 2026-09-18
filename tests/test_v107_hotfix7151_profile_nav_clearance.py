"""Regression: Streamlit Cloud owner avatar must not block Profile navigation."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_owner_avatar_cannot_overlap_mobile_profile_tab():
    ui = (ROOT / "ui.py").read_text("utf-8")
    mobile = ui.split("@media (max-width: 480px)", 1)[1].split("</style>", 1)[0]
    nav = mobile.split('div[class*="st-key-gate4_nav"] {', 1)[1].split("}", 1)[0]
    # Owner chrome occupies the bottom-right ~64 CSS px on iOS. The entire
    # nav sits ABOVE the host chrome, rather than reserving an unusable slice
    # INSIDE the fourth tab. Keep the safe-area inset additive.
    match = re.search(r'bottom:calc\(([\d.]+)rem \+ env\(safe-area-inset-bottom, 0px\)\)', nav)
    assert match, "mobile nav must clear owner chrome and device safe area"
    assert float(match.group(1)) >= 5.0
    assert "padding:.3rem .4rem !important" in nav
    assert "3.45rem" not in nav
    assert 'width:calc(100vw - 1rem) !important' in nav
    assert '::after' not in mobile  # no fake fifth slot pretending to be a nav item
    assert 'padding-bottom:12.75rem' in mobile
    assert 'flex-wrap:nowrap !important' in ui  # four tabs remain on one row


def test_hotfix_loads_new_css_in_warm_streamlit_worker():
    app = (ROOT / "app.py").read_text("utf-8")
    config = (ROOT / "config.py").read_text("utf-8")
    css = (ROOT / "ui.py").read_text("utf-8")
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.15.1"' in config
    assert 'getattr(_config, "APP_BUILD_VERSION", "") != "1.0.7-hotfix7.15.1"' in app
    assert 'UI_THEME_SCHEMA_VERSION = 3' in css
    assert 'getattr(_ui, "UI_THEME_SCHEMA_VERSION", 0) < 3' in app
