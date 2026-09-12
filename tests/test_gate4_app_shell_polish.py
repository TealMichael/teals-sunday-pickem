from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gate4_nav_uses_consistent_material_icons_and_four_top_level_destinations():
    text = (ROOT / "gate4_ui.py").read_text("utf-8")
    assert 'options = ["🏈 Sunday", "🏆 Season", "🕘 History", "👤 Profile"]' in text
    for icon in ("sports_football", "emoji_events", "history", "person"):
        assert f":material/{icon}:" in text


def test_gate4_nav_is_required_stretched_and_non_wrapping():
    text = (ROOT / "gate4_ui.py").read_text("utf-8")
    assert 'required=True' in text
    assert 'width="stretch"' in text
    assert 'wrap=False' in text


def test_gate4_nav_has_mobile_safe_area_and_vertical_icon_label_layout():
    css = (ROOT / "ui.py").read_text("utf-8")
    assert 'env(safe-area-inset-bottom' in css
    assert 'flex-direction:column !important' in css
    assert 'width:min(520px' in css
    assert 'min-height:58px !important' in css
