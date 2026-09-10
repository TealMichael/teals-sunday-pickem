from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v103_version_and_weekly_ui_reload_guard():
    assert 'APP_VERSION = "1.0.4"' in (ROOT / "config.py").read_text("utf-8")
    assert 'WEEKLY_UI_SCHEMA_VERSION = 6' in (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 6' in (ROOT / "app.py").read_text("utf-8")


def test_player_tap_is_local_and_next_owns_the_supabase_write():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")

    starter_start = text.index("def _select_starter")
    starter_end = text.index("def _select_backup")
    starter = text[starter_start:starter_end]
    assert "store.save_pick(" not in starter
    assert 'builder_pending::{kind}' in text
    assert 'builder_mode = "pick"' in starter

    backup_start = starter_end
    backup_end = text.index("def _save_selected_position")
    backup = text[backup_start:backup_end]
    assert "store.set_emergency_backup(" not in backup
    assert "store.save_pick(" not in backup
    assert 'builder_mode = "backup"' in backup

    save_start = backup_end
    save_end = text.index("def _markdown_escape")
    save_block = text[save_start:save_end]
    assert "store.save_pick(" in save_block
    assert "redundant Supabase upsert" in save_block


def test_builder_has_deliberate_next_and_questionable_backup_step():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'starter_needs_backup = bool(starter_is_questionable and not backup_ready)' in text
    assert 'next_label = "Choose Emergency Backup →"' in text
    assert 'next_label = f"Next: {nxt} →" if nxt else "Review My Five →"' in text
    assert 'next_label = "Return to Review →"' in text
    assert 'next_label = "Return to Lineup →"' in text
    assert 'disabled=not current_id' in text
    assert 'disabled=not backup_ready' in text


def test_tuesday_publish_has_redundant_noon_retry_window():
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert 'cron: "7,17,27,37,47,57 12 * * 2"' in workflow
    assert "retry every 10 minutes through 12:57" in workflow
    # Manual publish remains available as a fallback.
    assert "- publish" in workflow
