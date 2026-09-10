from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_review_rows_are_native_click_targets_for_each_position():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    assert 'st.caption("Tap any player to change your pick.")' in text
    assert 'key=f"review_edit_{position}"' in text
    assert 'on_click=_begin_review_edit' in text
    assert 'args=(position,)' in text
    assert '_render_player_card_button(' in text


def test_review_edit_callback_returns_to_review_after_replacement():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    start = text.index("def _begin_review_edit(")
    end = text.index("def _render_review_editable_lineup(", start)
    callback = text[start:end]
    assert 'builder_return_mode = "review"' in callback
    assert "builder_position = position" in callback
    assert 'builder_mode = "pick"' in callback
    assert "st.rerun()" not in callback


def test_review_cards_preserve_position_status_and_emergency_backup_context():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    start = text.index("def _render_review_editable_lineup(")
    end = text.index("def _advance_builder(", start)
    block = text[start:end]
    assert 'review_row["player_name"] = f"{position} · {_display_name(starter)}"' in block
    assert "QUESTIONABLE" in block
    assert "Emergency:" in block
    assert 'key=f"pickbtn_review_edit_missing_{position}"' in block
    assert "allow_out_click=True" in block


def test_shared_player_card_helper_can_show_review_backup_line_without_changing_picker_defaults():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    start = text.index("def _render_player_card_button(")
    end = text.index("def _builder(", start)
    block = text[start:end]
    assert 'extra_line: str = ""' in block
    assert "allow_out_click: bool = False" in block
    assert 'status == "OUT" and not allow_out_click' in block
    assert 'extra = f"\\n{_markdown_escape(extra_line)}" if extra_line else ""' in block
    assert 'label = f"{check}**{name}**{badge}\\n{meta}{extra}"' in block


def test_v105_version_and_reload_guard():
    assert 'APP_VERSION = "1.0.5"' in (ROOT / "config.py").read_text("utf-8")
    weekly = (ROOT / "weekly_ui.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    assert "WEEKLY_UI_SCHEMA_VERSION = 7" in weekly
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 7' in app
