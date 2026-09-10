from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_player_ui_cannot_enter_gate2_demo():
    weekly = (ROOT / "weekly_ui.py").read_text()
    assert "Preview Gate 2 Test Week" not in weekly
    assert "if not allow_demo_week and st.session_state.get(\"use_demo_week\")" in weekly


def test_gate2_demo_is_commissioner_only():
    app = (ROOT / "app.py").read_text()
    gate5 = (ROOT / "gate5_ui.py").read_text()
    assert 'if st.session_state.get("gate2_demo")' in app
    assert "allow_demo_week=True" in app
    assert "Preview Gate 2 Lineup Builder" in gate5

def test_hotfix_version():
    config = (ROOT / "config.py").read_text()
    assert 'APP_VERSION = "1.0.5"' in config
