from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from struct import unpack

from turkey_bowl import TurkeyBowlService
from turkey_loser_badge import loser_badge_html, loser_badge_markdown


def test_loser_badge_is_a_retina_png_rendered_at_18_css_pixels():
    html = loser_badge_html()
    assert 'width="18" height="18"' in html
    assert 'width:18px;height:18px' in html
    assert 'vertical-align:-3px' in html
    assert 'alt="Turkey Bowl loser"' in html
    assert '<img src="data:image/png;base64,' in html
    data = html.split('base64,', 1)[1].split('"', 1)[0]
    raw = b64decode(data)
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    assert unpack('>II', raw[16:24]) == (36, 36)
    assert Path('assets/turkey_bowl_loser_badge_36px.png').is_file()


def test_loser_badge_markdown_uses_supported_image():
    label = loser_badge_markdown()
    assert label.startswith('![Turkey Bowl loser](data:image/png;base64,')
    assert label.endswith(')')


def test_archive_persists_last_place_badge_recipients_and_lookup_is_season_scoped():
    class Store:
        def __init__(self):
            self.saved = {}
        def get_app_meta(self, key):
            if key in self.saved:
                return {'key': key, 'value': self.saved[key]}
            return None
        def set_app_meta(self, key, value):
            self.saved[key] = dict(value)
            return {'key': key, 'value': value}

    class Table:
        def __init__(self):
            self.updated = []
        def upsert(self, payload, **kwargs):
            self.updated.append(('upsert', payload, kwargs))
            return self
        def update(self, payload):
            self.updated.append(('update', payload, {}))
            return self
        def eq(self, *_args, **_kwargs):
            return self
        def execute(self):
            return type('Result', (), {'data': []})()

    class FakeService(TurkeyBowlService):
        def __init__(self):
            self.store = Store()
            self.tables = {'special_results': Table(), 'special_events': Table()}
        def table(self, name):
            return self.tables[name]
        def games(self, _event_id):
            return [{'game_status': 'FINAL'}] * 3
        def pool(self, _event_id, *, visible_only=False):
            return [{'score_status': 'FINAL', 'score_updated_at': 'yes'}]
        def leaderboard(self, _event):
            return [
                {'player_id': 'winner', 'nickname': 'Winner', 'emoji': '😀', 'score': 90, 'rank': 1},
                {'player_id': 'loser1', 'nickname': 'Loser 1', 'emoji': '😬', 'score': 12, 'rank': 2},
                {'player_id': 'loser2', 'nickname': 'Loser 2', 'emoji': '😵', 'score': 12, 'rank': 2},
            ]

    service = FakeService()
    event = {'id': 'event1', 'season': 2026, 'nfl_week': 12, 'published_at': 'yes', 'locks_at': '2000-11-26T18:00:00+00:00'}
    summary = service.archive(event)
    assert summary['losers'] == ['Loser 1', 'Loser 2']
    assert service.store.saved['turkey_bowl_loser_badge:2026']['player_ids'] == ['loser1', 'loser2']
    assert service.loser_badge_ids(2026) == {'loser1', 'loser2'}
    assert service.loser_badge_ids(2027) == set()


def test_gate4_and_turkey_views_use_loser_badges_without_mutating_names():
    gate4 = Path('gate4_ui.py').read_text(encoding='utf-8')
    holiday = Path('turkey_bowl_ui.py').read_text(encoding='utf-8')
    assert 'loser_badge_html' in gate4
    assert 'loser_badge_markdown' in gate4
    assert 'loser_ids=loser_ids' in gate4
    assert 'loser_badge_html' in holiday
    assert 'dict(row, nickname=' not in gate4
