from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sunday_pregame_is_four_way_privacy_safe_rotation():
    sql = (ROOT / "db" / "013_pregame_four_way_double_scroll.sql").read_text("utf-8")
    assert "case mod(floor(v_minute / 5)::integer, 4)" in sql
    assert "when 0 then v_category := 'preview'" in sql
    assert "when 1 then v_category := 'manual'" in sql
    assert "when 2 then v_category := 'readiness'" in sql
    assert "else v_category := 'season'" in sql
    # Current-week weekly standings must remain post-lock only.
    prelock = sql.split("if now() < v_week.locks_at then", 1)[1].split("  else\n    -- Post-lock", 1)[0]
    assert "v_payload->>'weekly'" not in prelock
    assert "player_updates" not in prelock


def test_pregame_preview_and_season_use_existing_snapshot_fields():
    sql = (ROOT / "db" / "013_pregame_four_way_double_scroll.sql").read_text("utf-8")
    assert "v_payload->>'sunday_preview'" in sql
    assert "v_payload->'sunday_preview_rich'" in sql
    assert "v_payload->>'season_text'" in sql
    assert "v_payload->'season_rich'" in sql


def test_saturday_preview_remains_every_fifteen_minutes():
    sql = (ROOT / "db" / "013_pregame_four_way_double_scroll.sql").read_text("utf-8")
    assert "extract(dow from v_local)::integer = 6" in sql
    assert "/ 900" in sql
    assert "'category', 'preview'" in sql


def test_post_lock_schedule_is_unchanged_from_717():
    sql = (ROOT / "db" / "013_pregame_four_way_double_scroll.sql").read_text("utf-8")
    expected = {
        0: "weekly", 1: "live_games", 2: "player", 3: "weekly",
        4: "live_games", 6: "weekly", 7: "live_games", 8: "player",
        9: "weekly", 10: "live_games",
    }
    for slot, category in expected.items():
        assert f"when {slot} then v_category := '{category}'" in sql
    assert "v_category := 'caleb'" not in sql


def test_only_requested_tickers_repeat_twice():
    script = (ROOT / "awtrix" / "PickemSunday.ax").read_text("utf-8")
    assert '# @version 1.0.7-hotfix7.18' in script
    assert 'if category == "preview" || category == "live_games" || category == "weekly"' in script
    assert "repeat_count = 2" in script
    assert script.count('"repeat": repeat_count') == 6
    assert 'category == "season" || category == "weekly"' not in script
    assert 'category == "manual" && data.find("test") != true' in script


def test_717_responsiveness_guards_remain_intact():
    script = (ROOT / "awtrix" / "PickemSunday.ax").read_text("utf-8")
    assert "stack_it = false" in script
    assert 'category == "live_games"' in script
    assert 'category == "preview"' in script
    assert "self.ticks = 10" in script
    assert "dow == 6" in script and "self.ticks = 30" in script
    # No endpoint or ACK behavior changes.
    assert '"/rest/v1/rpc/pickem_clock_feed"' in script
    assert '"/rest/v1/rpc/pickem_clock_ack"' in script
