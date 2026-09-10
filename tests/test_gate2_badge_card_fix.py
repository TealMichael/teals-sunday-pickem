from pathlib import Path


def _weekly_ui():
    return Path("weekly_ui.py").read_text()


def _ui():
    return Path("ui.py").read_text()


def test_player_card_is_the_real_streamlit_button_not_an_overlay():
    text = _weekly_ui()
    start = text.index("def _render_player_card_button")
    block = text[start:start+2600]
    assert 'width="stretch"' in block
    assert 'wrap=True' in block
    assert 'type="secondary"' in block
    assert 'with st.container(border=True' not in block
    assert 'type="tertiary"' not in block


def test_questionable_badge_is_inline_in_button_label():
    text = _weekly_ui()
    start = text.index("def _render_player_card_button")
    block = text[start:start+2600]
    assert ':yellow-badge[⚠ QUESTIONABLE]' in block
    assert 'label = f"{check}**{name}**{badge}\\n{meta}{extra}"' in block


def test_player_card_css_styles_native_button_as_full_card():
    text = _ui()
    assert 'st-key-pickbtn_' in text
    assert 'min-height:88px !important;' in text
    assert 'width:100% !important;' in text
    assert 'opacity:0 !important;' not in text
    assert 'inset:0 !important;' not in text
