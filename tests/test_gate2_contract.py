from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gate2_migration_has_core_weekly_tables_and_lock_trigger():
    sql = (ROOT / "db/002_gate2_weekly_game.sql").read_text()
    for name in ["pickem.weeks", "pickem.player_pool", "pickem.lineups", "pickem.lineup_picks"]:
        assert name in sql
    assert "trg_guard_lineup_pick" in sql
    assert "now() >= v_week.locks_at" in sql
    assert "2026-09-08 12:00:00-04" in sql
    assert "2026-09-13 13:00:00-04" in sql


def test_gate2_ui_contract_keeps_simple_five_position_flow():
    text = (ROOT / "weekly_ui.py").read_text()
    assert "SAVE MY LINEUP" in text
    assert "QB · RB · WR · TE · K" in text
    assert "One tap selects" in text
    assert "emergency backup" in text.lower()
    assert "Preview Gate 2 Test Week" in text


def test_gate2_does_not_rank_or_recommend_on_player_cards():
    text = (ROOT / "weekly_ui.py").read_text().lower()
    assert "projection" not in text
    assert "matchup rating" not in text
    assert "slot_rank" not in text
