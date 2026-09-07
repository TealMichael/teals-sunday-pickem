from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_gate5_files_present_and_versioned():
    assert (ROOT / "gate5.py").exists()
    assert (ROOT / "gate5_ui.py").exists()
    assert "APP_VERSION = \"1.0.1\"" in (ROOT / "config.py").read_text()


def test_app_routes_commissioner_to_gate5_dashboard():
    text = (ROOT / "app.py").read_text()
    assert "render_commissioner_dashboard" in text
    assert "pin_pepper=secret(\"PIN_PEPPER\")" in text
    assert "Gate 4 demo remains an isolated Commissioner diagnostic" in text


def test_gate5_ui_contains_required_admin_controls():
    text = (ROOT / "gate5_ui.py").read_text()
    for needle in [
        "Refresh NFL Data Now",
        "Generate Again",
        "Reconcile / Finalize Now",
        "Players & PINs",
        "Reset Player PIN",
        "Emergency Player Pool Override",
        "Manual Score Override",
        "Preview Gate 4 Live Sunday Demo",
    ]:
        assert needle in text


def test_gate5_business_preserves_lock_and_manual_override_rules():
    text = (ROOT / "gate5.py").read_text()
    assert "Player-pool overrides are disabled after the universal 1:00 PM ET lock" in text
    assert "Manual score corrections are only available after the 1:00 PM ET lock" in text
    assert "archive_week_results" in text


def test_gate5_refresh_avoids_layout_spinner_ghosting():
    text = (ROOT / "gate5_ui.py").read_text()
    assert 'st.toast("Refreshing NFL data…")' in text
    assert 'with st.spinner("Refreshing NFL data…")' not in text


def test_gate5_score_override_copy_mentions_sunday_lock():
    text = (ROOT / "gate5_ui.py").read_text()
    assert "applying a correction remains locked until Sunday at 1:00 PM ET" in text
