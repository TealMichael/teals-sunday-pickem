from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_browser_bridge_is_not_unconditionally_mounted():
    app = (ROOT / "app.py").read_text("utf-8")
    assert "_sync_pending_storage_command()" in app
    assert 'if not st.session_state.player and not st.session_state.remember_restore_checked:' in app
    assert 'command = st.session_state.get("remember_storage_command") or {}' in app
    assert 'render_pending_remember_cookie_command' not in app


def test_successful_login_uses_callback_before_rerender():
    app = (ROOT / "app.py").read_text("utf-8")
    assert "def _signin_submit()" in app
    assert "on_click=_signin_submit" in app
    assert "def _apply_player_auth_result" in app
    helper = app.split("def _apply_player_auth_result", 1)[1].split("def _signin_submit", 1)[0]
    assert "st.session_state.player = result.player" in helper
    assert "_queue_remember_cookie_set(result.cookie_value)" in helper
    # The old post-form explicit rerun/placeholder workaround caused the ghosted form.
    assert "auth_slot" not in app


def test_pending_login_storage_does_not_block_signed_in_home():
    app = (ROOT / "app.py").read_text("utf-8")
    block = app.split("# Remembered-login restore", 1)[1]
    assert '_storage_sync_pending, _storage_sync_action = _sync_pending_storage_command()' in block
    assert 'if _storage_sync_pending and _storage_sync_action == "delete":' in block
    assert 'if st.session_state.player:' in block
    # A pending login write must not block the signed-in player page.
    assert 'if _storage_sync_pending and _storage_sync_action == "set":' not in block


def test_fixed_light_theme_is_hardened_for_dark_system_devices():
    ui = (ROOT / "ui.py").read_text("utf-8")
    cfg = (ROOT / ".streamlit/config.toml").read_text("utf-8")
    assert "color-scheme: light" in ui
    assert '[data-testid="stAppViewContainer"]' in ui
    assert "background:var(--page) !important" in ui
    assert "background:#F3F5F7 !important" in ui
    assert 'data-testid="stBaseButton-secondary"' in ui
    assert 'background:#FFFFFF !important' in ui
    assert 'base = "light"' in cfg


def test_hero_has_safe_top_spacing_and_kicker_line_height():
    ui = (ROOT / "ui.py").read_text("utf-8")
    assert "padding-top: 2.25rem" in ui
    assert ".hero-kicker" in ui
    assert "line-height:1.35" in ui
    assert "padding-top:.12rem" in ui
