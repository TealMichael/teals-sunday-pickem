from pathlib import Path


def _ui():
    return Path("weekly_ui.py").read_text()


def test_complete_lineup_edit_opens_review_not_qb():
    text = _ui()
    marker = 'if st.button("EDIT LINEUP"'
    start = text.index(marker)
    block = text[start:start+350]
    assert 'builder_position = None' in block
    assert 'builder_mode = "review"' in block


def test_emergency_backup_rules_are_explained():
    text = _ui()
    assert "How the emergency backup works" in text
    assert "ruled OUT/inactive after the 1:00 PM ET lock" in text
    assert "If your starter plays at all, your starter counts" in text
    assert "backup stays private unless it activates" in text


def test_questionable_selection_uses_full_wording():
    text = _ui()
    assert '<span class="badge-q">⚠ QUESTIONABLE</span>' in text
    assert '⚠️ Q' not in text


def test_position_selection_waits_for_explicit_next():
    text = _ui()
    assert 'Tap a player to highlight it. Your choice saves only when you tap Next.' in text
    assert 'next_label = f"Next: {nxt} →" if nxt else "Review My Five →"' in text
    assert 'disabled=not current_id' in text


def test_demo_week_hides_fake_multi_decade_countdown():
    text = _ui()
    assert "TEST WEEK • LOCK OPEN" in text
    assert "Build and edit freely while testing." in text
    assert "Test lineup saved. You can keep editing while the Gate 2 test week is open." in text
