from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_commissioner_messages_are_added_to_existing_double_scroll_allowlist_only():
    script = (ROOT / "awtrix" / "PickemSunday.ax").read_text("utf-8")
    assert '# @version 1.0.7-hotfix7.18.1' in script
    assert 'if category == "preview" || category == "live_games" || category == "weekly" || category == "manual"' in script
    assert 'repeat_count = 2' in script
    assert 'category == "player"' not in script.split('repeat_count = 2', 1)[0].split('var repeat_count = 1', 1)[1]
    assert 'category == "season"' not in script.split('repeat_count = 2', 1)[0].split('var repeat_count = 1', 1)[1]
    assert 'category == "readiness"' not in script.split('repeat_count = 2', 1)[0].split('var repeat_count = 1', 1)[1]


def test_melody_and_responsiveness_behavior_remain_present():
    script = (ROOT / "awtrix" / "PickemSunday.ax").read_text("utf-8")
    assert 'category == "manual" && data.find("test") != true' in script
    assert '"soundRtttl": str(melody)' in script
    assert 'stack_it = false' in script
    assert 'self.ticks = 10' in script
    assert 'self.ticks = 30' in script
    assert '"/rest/v1/rpc/pickem_clock_feed"' in script
    assert '"/rest/v1/rpc/pickem_clock_ack"' in script
