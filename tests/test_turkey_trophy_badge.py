"""Pure presentation tests: 18px championship icon, no lineup/scoring changes."""
from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from struct import unpack

from turkey_trophy_badge import trophy_badge_html, trophy_badge_markdown


def test_trophy_is_a_retina_png_rendered_at_18_css_pixels():
    html = trophy_badge_html()
    assert 'width="18" height="18"' in html
    assert 'width:18px;height:18px' in html
    assert 'vertical-align:-3px' in html
    assert 'alt="Turkey Bowl champion"' in html
    assert '<img src="data:image/png;base64,' in html
    data = html.split('base64,', 1)[1].split('"', 1)[0]
    raw = b64decode(data)
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    # PNG IHDR: 36x36 raster = 2x pixel density at 18 CSS px.
    assert unpack('>II', raw[16:24]) == (36, 36)
    assert Path('assets/turkey_bowl_trophy_36px.png').is_file()


def test_button_badge_uses_supported_markdown_image():
    label = trophy_badge_markdown()
    assert label.startswith('![Turkey Bowl champion](data:image/png;base64,')
    assert label.endswith(')')


def test_app_uses_badges_without_mutating_leaderboard_nicknames():
    gate4 = Path('gate4_ui.py').read_text(encoding='utf-8')
    holiday = Path('turkey_bowl_ui.py').read_text(encoding='utf-8')
    assert 'trophy_badge_html()' in gate4
    assert 'trophy_badge_markdown()' in gate4
    assert 'trophy_ids=trophy_ids' in gate4
    assert 'trophy_badge_html()' in holiday
    assert 'trophy_badge_markdown()' in holiday
    assert 'dict(row, nickname=' not in gate4  # no nickname mutation for a UI badge
    assert '🦃🏆' not in gate4 and '🦃🏆' not in holiday
