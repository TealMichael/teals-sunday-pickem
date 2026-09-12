from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_gate4_files_and_schema_present():
    assert (ROOT / "db/004_gate4_live_social.sql").exists()
    assert (ROOT / "gate4.py").exists()
    assert (ROOT / "gate4_ui.py").exists()
    sql = (ROOT / "db/004_gate4_live_social.sql").read_text()
    assert "pickem.weekly_results" in sql
    assert "pickem.season_champions" in sql


def test_gate4_ui_contract():
    text = (ROOT / "gate4_ui.py").read_text()
    for needle in ["Sunday Storylines", "Most Popular Pick", "Went Alone", "Same Brain", "Season", "Trophy Case", "How to Play"]:
        assert needle in text
    assert "Emergency activated" in text
    assert "private" in text


def test_finalization_archives_and_tuesday_purges():
    sync = (ROOT / "nfl_sync.py").read_text()
    assert "archive_week_results" in sync
    assert "purge_prior_week_rosters" in sync
