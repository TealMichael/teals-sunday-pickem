from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hotfix7101_lineup_pool_disclaimer_and_warm_deploy_guard():
    config = (ROOT / "config.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    weekly = (ROOT / "weekly_ui.py").read_text("utf-8")

    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.10.1"' in config
    assert "WEEKLY_UI_SCHEMA_VERSION = 10" in weekly
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 10' in app

    assert "Saturday at 11:59 PM ET" in weekly
    assert "Your saved picks will never change automatically." in weekly
    assert "Check back before Sunday’s" in weekly
    assert "1:00 PM ET lock" in weekly

    # The note belongs directly beneath saved-pick displays in both the
    # normal ready-home view and Review My Five, but not demo-only surfaces.
    assert weekly.count("_render_pool_change_disclaimer()") == 3  # definition + two calls
