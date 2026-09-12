from pathlib import Path


def _ui():
    return Path("weekly_ui.py").read_text()


def test_questionable_selection_uses_yellow_inline_badge():
    text = _ui()
    assert '<span class="badge-q">⚠ QUESTIONABLE</span>' in text
    assert ':yellow-badge[⚠ QUESTIONABLE]' in text


def test_completed_lineup_change_returns_to_review():
    text = _ui()
    assert 'builder_return_mode = "review"' in text
    assert 'def _complete_builder_step(position: str)' in text
    assert '_complete_builder_step(position)' in text
    assert 'return_mode in {"review", "home"}' in text


def test_edit_back_button_returns_to_review():
    text = _ui()
    assert 'back_label = "← Review" if return_mode == "review"' in text


def test_initial_builder_still_has_normal_advance_path():
    text = _ui()
    assert 'def _advance_builder(position: str)' in text
    assert 'nxt = next_position(position)' in text
