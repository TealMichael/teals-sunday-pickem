from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_picker_cards_are_compact_but_keep_full_card_tap_target():
    css = (ROOT / "ui.py").read_text("utf-8")
    assert "min-height:68px !important;" in css
    assert "padding:.5rem .8rem !important;" in css
    assert "margin:.25rem 0 !important;" in css
    assert "line-height:1.3 !important;" in css
    assert "width:100% !important;" in css


def test_sunday_status_keeps_out_starter_warning_when_backup_is_valid():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert "covered_out = [pos for pos in out_starters if pos not in unavailable]" in text
    assert 'title = "Lineup ready — backup set"' in text
    assert "OUT • emergency backup" in text
    assert "QUESTIONABLE" in text


def test_weekly_ui_reload_guard_bumped_for_hot_deploy():
    weekly = (ROOT / "weekly_ui.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    assert "WEEKLY_UI_SCHEMA_VERSION = 8" in weekly
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 8' in app


def test_hotfix_does_not_touch_scoring_or_refresh_schedule():
    scoring = (ROOT / "nfl_scoring.py").read_text("utf-8")
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert '("field_goals_made", fg_made, fg_made * 3.0' in scoring
    assert 'cron: "7,22,37,52 11-23 * * 0"' in workflow
