from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_commissioner_demo_stays_in_admin_mode():
    ui = (ROOT / "gate5_ui.py").read_text()
    assert 'if st.button("Preview Gate 4 Live Sunday Demo"' in ui
    assert 'st.session_state.gate4_demo = True' in ui
    assert 'st.session_state.commish = False' not in ui.split('Preview Gate 4 Live Sunday Demo', 1)[1].split('Open Gate 3.5 Replay Runner', 1)[0]
    app = (ROOT / "app.py").read_text()
    assert "render_gate4_demo()" in app


def test_demo_accepts_synthetic_identity_and_clears_nav_state():
    text = (ROOT / "gate4_ui.py").read_text()
    assert "def render_gate4_demo(current_player: dict[str, Any] | None = None)" in text
    assert 'current_player = current_player if isinstance(current_player, dict) else {}' in text
    assert 'st.session_state.pop("gate4_nav", None)' in text


def test_weekly_ui_deploy_reload_guard_present():
    text = (ROOT / "app.py").read_text()
    assert '_weekly_params = inspect.signature(_weekly_ui.render_player_game).parameters' in text
    assert '"on_sign_out" not in _weekly_params' in text
    assert '"allow_demo_week" not in _weekly_params' in text
    assert "importlib.reload(_weekly_ui)" in text
