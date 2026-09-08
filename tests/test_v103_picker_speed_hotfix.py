from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_picker_speed_hotfix_defers_writes_until_next():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    starter = text[text.index("def _select_starter"):text.index("def _select_backup")]
    backup = text[text.index("def _select_backup"):text.index("def _save_selected_position")]
    save_block = text[text.index("def _save_selected_position"):text.index("def _markdown_escape")]
    assert "store." not in starter
    assert "store." not in backup
    assert "store.save_pick(" in save_block


def test_next_is_the_only_place_that_commits_a_staged_position():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'st.session_state[_pending_builder_key("starter", week, player, position)] = str(row["id"])' in text
    assert 'st.session_state[_pending_builder_key("backup", week, player, position)] = str(row["id"])' in text
    assert "_save_selected_position(" in text
    assert "redundant Supabase upsert" in text


def test_picker_keeps_lineup_snapshot_warm_during_local_selection():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert "snapshot_ttl_seconds=300.0" in text
    assert "snapshot_ttl_seconds: float = LINEUP_SNAPSHOT_TTL_SECONDS" in text


def test_questionable_starter_and_backup_commit_together():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'emergency_pool_player_id=str(backup_id) if backup_id else None' in text
    assert 'starter_id=current_id' in text
    assert 'backup_id=backup_id' in text
    assert 'disabled=not backup_ready' in text


def test_picker_copy_matches_confirm_before_save_behavior():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert "Tap a player to highlight it. Your choice saves only when you tap Next." in text
    assert "Tap a player, then tap Next to save each position." in text


def test_player_tap_uses_callback_without_forced_second_rerun():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert "on_click=_select_starter" in text
    assert "on_click=_select_backup" in text
    starter_loop = text[text.index("    for row in rows:\n        _render_player_card_button("):text.index("    left, right = st.columns(2)", text.index("    for row in rows:\n        _render_player_card_button("))]
    assert "st.rerun()" not in starter_loop
    backup_start = text.index("        for row in rows:", text.index('if mode == "backup":'))
    backup_end = text.index("        return_mode =", backup_start)
    assert "st.rerun()" not in text[backup_start:backup_end]


def test_player_card_supports_pre_rerun_selection_callback():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    block = text[text.index("def _render_player_card_button"):text.index("def _builder")]
    assert "on_click=None" in block
    assert "args: tuple = ()" in block
    assert "on_click=on_click" in block
    assert "args=args" in block
