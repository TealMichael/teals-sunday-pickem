"""Anonymous in-memory transport for actual store/UI interaction tests."""
from copy import deepcopy
from datetime import datetime, timezone
from threading import get_ident

import streamlit as st
from streamlit.testing.v1 import AppTest

from espn_performance_fixture import Query as BaseQuery, fixture
from player_season_stats import snapshot_key, STATS_SNAPSHOT_SCHEMA
from store import SupabaseStore

class Clock(datetime):
    at = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)
    @classmethod
    def now(cls, tz=None):
        return cls.at.astimezone(tz) if tz else cls.at.replace(tzinfo=None)

class Query(BaseQuery):
    def select(self, fields='*', **kwargs):
        self.fields = fields
        return self
    def like(self, key, value):
        self.filters.append(lambda row: str(row.get(key, '')).startswith(value.rstrip('%')))
        return self
    def execute(self):
        self.store.owner = get_ident()
        if self.store.reject_write and self.operation != 'select':
            message = self.store.reject_write
            self.store.reject_write = ''
            self.store.attempted_writes += 1
            raise RuntimeError(message)
        if self.operation != 'select':
            self.store.attempted_writes += 1
        result = super().execute()
        if self.operation != 'select' and self.store.after_write:
            callback, self.store.after_write = self.store.after_write, None
            callback()
        if self.operation == 'select' and 'lineup_picks(' in getattr(self, 'fields', ''):
            for row in result.data:
                row['lineup_picks'] = deepcopy([p for p in self.store.tables['lineup_picks']
                                               if p['lineup_id'] == row['id']])
        if self.operation == 'select' and ',players(' in getattr(self, 'fields', ''):
            projected = []
            for row in result.data:
                value = {k: row.get(k) for k in self.fields.split(',players(', 1)[0].split(',')}
                person = next((p for p in self.store.tables['players'] if p['id'] == row['player_id']), None)
                value['players'] = {k: person.get(k) for k in ['id','nickname','emoji']} if person else None
                projected.append(value)
            result.data = projected
        return result

class LineupStore(SupabaseStore):
    def __init__(self, *, complete=False):
        games, pool, _ = fixture()
        self.operations = []
        self.attempted_writes = 0
        self.reject_write = ''
        self.after_write = None
        self._public_cache = {}
        self.week = {'id':'week', 'is_demo':False, 'season':2026, 'nfl_week':8,
                     'opens_at':'2026-10-20T10:00:00+00:00',
                     'locks_at':'2026-10-25T17:00:00+00:00',
                     'published_at':'2026-10-20T10:00:00+00:00',
                     'last_data_refresh_at':Clock.at.isoformat(), 'data_status':'POOL_READY'}
        self.player = {'id':'00000000-0000-4000-8000-000000000001', 'nickname':'Synthetic',
                       'emoji':'🏈', 'onboarding_completed_at':Clock.at.isoformat()}
        for row in pool:
            row.update(week_id='week', kickoff_at=self.week['locks_at'], schedule_eligible=True)
        for row in games:
            row.update(week_id='week', game_status='SCHEDULED')
        self.tables = {'weeks':[self.week], 'player_pool':pool, 'nfl_games':games,
                       'players':[self.player], 'lineups':[], 'lineup_picks':[],
                       'app_meta':[{'key':snapshot_key(self.week), 'value':{
                           'schema':STATS_SNAPSHOT_SCHEMA, 'through_week':7,
                           'players':{'fixture-placeholder':{'gp':1}}}}],
                       'weekly_results':[], 'season_champions':[], 'data_runs':[]}
        if complete:
            self.tables['lineups'] = [{'id':'lineup', 'week_id':'week', 'player_id':self.player['id']}]
            self.tables['lineup_picks'] = [{'id':'pick-'+pos, 'lineup_id':'lineup', 'position':pos,
                'pool_player_id':'pool-0-'+pos, 'emergency_pool_player_id':None}
                for pos in ['QB','RB','WR','TE','K']]
    def _table(self, name):
        return Query(self, name)
    def pool_row(self, ident):
        return next(p for p in self.tables['player_pool'] if p['id'] == ident)
    def pick(self, position):
        return next((p for p in self.tables['lineup_picks'] if p['position'] == position), None)
    def reset_counts(self):
        self.operations.clear()
        self.attempted_writes = 0

def app_for(store, *, mode='home', position=None, return_mode=None, demo=False):
    script = '''import streamlit as st
import weekly_ui
st.session_state.test_runs = st.session_state.get('test_runs', 0) + 1
weekly_ui.render_player_game(st.session_state.fixture_store, st.session_state.player,
                            allow_demo_week=st.session_state.fixture_demo)
'''
    app = AppTest.from_string(script, default_timeout=10)
    app.session_state['fixture_store'] = store
    app.session_state['fixture_demo'] = demo
    app.session_state['player'] = store.player
    app.session_state['builder_mode'] = mode
    app.session_state['builder_position'] = position
    if return_mode:
        app.session_state['builder_return_mode'] = return_mode
    if demo:
        store.week['is_demo'] = True
        app.session_state['use_demo_week'] = True
    app.run()
    assert not app.exception
    return app

def button(app, label):
    return next(b for b in app.button if b.label == label)

def card(app, position, index=0):
    return next(b for b in app.button if f'Synthetic {index} {position}' in b.label)

def click_once(app, target):
    before = app.session_state['test_runs']
    target.click().run()
    assert not app.exception
    assert app.session_state['test_runs'] == before + 1
    return app
