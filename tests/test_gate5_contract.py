from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_gate5_files_present_and_versioned():
    assert (ROOT / "gate5.py").exists()
    assert (ROOT / "gate5_ui.py").exists()
    assert "APP_VERSION = \"0.5.1\"" in (ROOT / "config.py").read_text()


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
