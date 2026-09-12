from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_renderfix_uses_awtrix_ng_fragment_schema():
    py = (ROOT / "clock_broadcast.py").read_text("utf-8")
    sql = (ROOT / "db/010_clock_rich_fragment_render_fix.sql").read_text("utf-8")
    assert 'return {"text":' in py
    assert '"color":' in py
    assert "jsonb_build_object('text'," in sql
    assert ", 'color'," in sql


def test_renderfix_awtrix_accepts_new_and_legacy_fragment_shapes_and_has_plain_fallback():
    text = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert '# @version 1.0.7-hotfix7.1' in text
    assert 'part.find("text")' in text
    assert 'part.find("t")' in text
    assert 'part.find("color")' in text
    assert 'part.find("c")' in text
    assert 'out.push({"text": str(text), "color": str(color)})' in text
    assert 'if !accepted' in text
    assert '"textColor": str(color)' in text


def test_renderfix_removes_unsupported_emoji_from_caleb_clock_copy():
    py = (ROOT / "clock_broadcast.py").read_text("utf-8")
    sql = (ROOT / "db/010_clock_rich_fragment_render_fix.sql").read_text("utf-8")
    for unsupported in ("🐻", "👀", "😱"):
        assert unsupported not in py
        assert unsupported not in sql
    assert "CALEB 4K WATCH" in py
    assert "BEAR DOWN? DON'T JINX IT" in py


def test_renderfix_preserves_polling_rpc_and_security_contract():
    text = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert 'default=15 min=10 max=60 unit=sec' in text
    assert 'self.ticks = 15' in text
    assert '/rest/v1/rpc/pickem_clock_feed' in text
    assert '/rest/v1/rpc/pickem_clock_ack' in text
    assert 'SERVICE_ROLE' not in text.upper()
