from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "db/012_clock_pregame_preview_5min.sql"


def test_pregame_preview_runs_every_five_minutes_from_9_to_noon():
    sql = SQL.read_text("utf-8")
    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("-- Post-lock broadcast rhythm", 1)[0]
    before_noon = prelock.split("if v_hour < 12 then", 1)[1].split("else", 1)[0]

    assert "one preview every five minutes" in before_noon
    assert "floor(extract(epoch from now()) / 300)" in before_noon
    assert "/ 600" not in before_noon
    assert "v_category := 'nfl_preview'" in before_noon


def test_noon_to_one_keeps_welcome_preview_interleave():
    sql = SQL.read_text("utf-8")
    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("-- Post-lock broadcast rhythm", 1)[0]

    assert "Noon-lock: Welcome at :00/:10/:20/" in prelock
    assert "preview at :05/:15/:25/" in prelock
    assert "mod(floor(v_minute / 5)::integer, 2) = 0" in prelock
    assert "v_category := 'welcome'" in prelock
    assert "v_category := 'nfl_preview'" in prelock


def test_postlock_rotation_is_unchanged():
    sql = SQL.read_text("utf-8")
    postlock = sql.split("-- Post-lock broadcast rhythm", 1)[1]

    for slot in (0, 3, 6, 9):
        assert f"when {slot} then v_category := 'weekly'" in postlock
    for slot in (1, 4, 7, 10):
        assert f"when {slot} then v_category := 'live_games'" in postlock
    assert "when 2 then v_category := case when v_caleb_live then 'caleb' else 'player' end" in postlock
    assert "when 8 then v_category := 'caleb'" in postlock
    assert "else v_category := 'manual';              -- :55" in postlock
