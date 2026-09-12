from pathlib import Path

ROOT = Path(__file__).parents[1]


def _signup_block() -> str:
    app = (ROOT / "app.py").read_text("utf-8")
    return app.split('with st.form("signup_form"):', 1)[1].split('if st.session_state.get("signup_error"):', 1)[0]


def test_signup_emoji_has_no_fake_football_default():
    block = _signup_block()
    assert 'placeholder="🏈"' not in block
    assert 'placeholder="Tap here, then choose an emoji"' in block
    assert 'key="signup_emoji"' in block


def test_signup_pin_avoids_password_manager_and_requests_phone_keypad():
    block = _signup_block()
    assert block.count('type="phone"') == 2
    assert block.count('autocomplete="off"') >= 3
    assert 'type="password"' not in block
    assert 'key="signup_pin"' in block
    assert 'key="signup_pin_confirm"' in block


def test_signup_pin_is_still_visually_masked():
    ui = (ROOT / "ui.py").read_text("utf-8")
    assert 'st-key-signup_pin' in ui
    assert '-webkit-text-security:disc' in ui
