from pathlib import Path


def test_commissioner_has_scoring_test_button_and_report():
    text = Path("gate5_ui.py").read_text()
    assert 'Run Gate 3 Scoring Test' in text
    assert 'run_scoring_diagnostic' in text
    assert 'Week 1 isolation' in text
    assert 'cleanup' in text


def test_release_contains_scoring_diagnostic_module():
    assert Path("scoring_diagnostic.py").exists()
