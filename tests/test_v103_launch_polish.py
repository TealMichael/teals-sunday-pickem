from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v103_version_and_weekly_ui_reload_guard():
    assert 'APP_VERSION = "1.0.3"' in (ROOT / "config.py").read_text("utf-8")
    assert 'WEEKLY_UI_SCHEMA_VERSION = 3' in (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 3' in (ROOT / "app.py").read_text("utf-8")


def test_player_tap_autosaves_but_does_not_auto_advance():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    start = text.index("def _select_starter")
    end = text.index("def _select_backup")
    starter = text[start:end]
    assert "store.save_pick(" in starter
    assert 'builder_mode = "pick"' in starter
    assert "_complete_builder_step(position)" not in starter

    backup_start = end
    backup_end = text.index("def _markdown_escape")
    backup = text[backup_start:backup_end]
    assert "store.set_emergency_backup(" in backup
    assert 'builder_mode = "backup"' in backup
    assert "_complete_builder_step(position)" not in backup


def test_builder_has_deliberate_next_and_questionable_backup_step():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'starter_needs_backup = bool(current and position in required_backup_positions([current], pool_by_id))' in text
    assert 'next_label = "Choose Emergency Backup →"' in text
    assert 'next_label = f"Next: {nxt} →" if nxt else "Review My Five →"' in text
    assert 'next_label = "Return to Review →"' in text
    assert 'next_label = "Return to Lineup →"' in text
    assert 'disabled=not current_id' in text
    assert 'disabled=not backup_id' in text


def test_tuesday_publish_has_redundant_noon_retry_window():
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert 'cron: "7,17,27,37,47,57 12 * * 2"' in workflow
    assert "retry every 10 minutes through 12:57" in workflow
    # Manual publish remains available as a fallback.
    assert "- publish" in workflow
