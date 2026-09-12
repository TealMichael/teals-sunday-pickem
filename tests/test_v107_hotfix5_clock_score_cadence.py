from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hotfix5_clock_cadence_has_nfl_scores_every_15_minutes():
    sql = (ROOT / "db/008_clock_nfl_score_cadence.sql").read_text("utf-8")
    # Five-minute slot map after lock:
    expected = {
        0: "weekly",
        1: "live_games",
        2: "player",
        3: "weekly",
        4: "live_games",
        6: "weekly",
        7: "live_games",
        8: "player",
        9: "weekly",
        10: "live_games",
    }
    for slot, category in expected.items():
        assert f"when {slot} then v_category := '{category}'" in sql

    # :25 is Pulse in Week 1 and Season standings from Week 2 onward.
    assert "when 5 then v_category := case when v_week.nfl_week >= 2 then 'season' else 'pulse' end" in sql
    # :55 is the sole manual-message slot.
    assert "else v_category := 'manual';             -- :55" in sql


def test_hotfix5_manual_messages_advance_once_per_hour():
    sql = (ROOT / "db/008_clock_nfl_score_cadence.sql").read_text("utf-8")
    assert "/ 3600" in sql
    assert "configured message rotation once per hour" in sql


def test_hotfix5_preserves_pregame_privacy_and_rpc_hardening():
    sql = (ROOT / "db/008_clock_nfl_score_cadence.sql").read_text("utf-8")
    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("-- Post-lock broadcast rhythm", 1)[0]
    assert "readiness" in prelock
    assert "weekly" not in prelock
    assert "pulse" not in prelock
    assert "set search_path = pickem, public, extensions, pg_temp" in sql
    assert "digest(p_token, 'sha256')" in sql


def test_hotfix5_does_not_change_awtrix_polling_or_nfl_refresh_workflow():
    awtrix = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert 'default=15 min=10 max=60 unit=sec' in awtrix
    assert "self.ticks = 15" in awtrix
    # Hotfix changes clock airtime only, not the NFL data-refresh cadence.
    assert "7,22,37,52" in workflow
