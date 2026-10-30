"""Read-only Live Sunday audit with an optional isolated bundle-loading experiment.

Only SQL/HTTP transport and wall-clock dates are replaced with synthetic fixtures.
Application source is never rewritten. Run in a fresh Python process.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import functools
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import sys
from threading import get_ident
import threading
import time
from types import SimpleNamespace

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--delay', type=float, default=0)
parser.add_argument('--owner', action='store_true')
parser.add_argument('--variant', choices=['baseline','release'], default='baseline')
args = parser.parse_args()
source = args.source.resolve()
output = args.output.resolve()
sys.path[:0] = [str(source), str(source / 'tests'), str(Path(__file__).resolve().parent)]
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
blocked_attempts = []

def blocked(*a, **kw):
    blocked_attempts.append('outbound socket')
    raise AssertionError('No external network is allowed in this audit')

socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked

import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.runtime.scriptrunner_utils.script_run_context import ScriptRunContext
import store as store_module
from espn_performance_fixture import Query as BaseQuery, fixture
import weekly_ui
import ui
import config
from google.protobuf.json_format import MessageToDict
from public_query_fixture import project
from types import MethodType

fixed_now = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)
class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)

for module_name in ['store', 'weekly', 'weekly_ui', 'gate4_ui', 'pulse_ui',
                    'automation_recovery', 'player_season_stats', 'commissioner_access',
                    'gate5', 'gate5_ui', 'gate6', 'gate6_ui', 'pickem_pulse',
                    'gate4', 'lineup_reveal', 'sunday_drama', 'personal_season_story']:
    module = importlib.import_module(module_name)
    if getattr(module, 'datetime', None) is datetime:
        module.datetime = FixedDateTime

PLAYER_ID = '00000000-0000-4000-8000-000000000001'
WEEK_ID = 'audit-week-8'
calls = Counter()
emissions = []
module_files = {str(p): p.name for p in source.glob('*.py')}
def profile(frame, event, arg):
    if event == 'call' and frame.f_code.co_filename in module_files:
        calls[module_files[frame.f_code.co_filename] + ':' + frame.f_code.co_name] += 1
threading.setprofile(profile)
original_enqueue = ScriptRunContext.enqueue
def measured_enqueue(self, message):
    emissions.append({'run': calls['app.py:<module>'], 'type':message.WhichOneof('type'),
                      'bytes':message.ByteSize()})
    return original_enqueue(self, message)
ScriptRunContext.enqueue = measured_enqueue

class Query(BaseQuery):
    def select(self, fields='*', **kw):
        self.fields = fields
        return self
    def like(self, key, value):
        assert value.endswith('%') and '%' not in value[:-1]
        self.filters.append(lambda row: str(row.get(key, '')).startswith(value[:-1]))
        return self
    def execute(self):
        trace = []
        f = sys._getframe(1)
        while f:
            if Path(f.f_code.co_filename).parent == source:
                trace.append(Path(f.f_code.co_filename).name + ':' + f.f_code.co_name)
            f = f.f_back
        self.store.queries.append({'operation': self.table + '.' + self.operation,
                                   'fields': getattr(self, 'fields', None), 'stack': trace})
        if self.store.delay:
            time.sleep(self.store.delay)
        if self.store.fail_next_write and self.operation != 'select':
            self.store.fail_next_write = False
            raise RuntimeError('Synthetic failed save')
        # AppTest uses a new script-runner thread. All queries remain on that thread.
        self.store.owner = get_ident()
        result = super().execute()
        if self.operation == 'select':
            result.data = project(result.data, getattr(self, 'fields', '*'), self.store.tables)
        return result

class AuditStore(store_module.SupabaseStore):
    def __init__(self):
        games, pool, _ = fixture()
        self.delay = args.delay
        self.queries = []
        self.operations = []
        self.fail_next_write = False
        self._public_cache = {}
        self.week = {'id': WEEK_ID, 'season': 2026, 'nfl_week': 8, 'label': 'Week 8',
                     'opens_at': '2026-10-20T10:00:00+00:00',
                     'locks_at': '2026-10-25T17:00:00+00:00',
                     'published_at': '2026-10-20T10:00:00+00:00',
                     'last_data_refresh_at': fixed_now.isoformat(),
                     'data_status': 'POOL_READY', 'is_demo': False}
        for row in pool:
            row.update(week_id=WEEK_ID, kickoff_at=self.week['locks_at'],
                       schedule_eligible=True, opponent_abbr='SYN')
        for row in games:
            row.update(week_id=WEEK_ID, game_status='SCHEDULED', period=0,
                       provider_updated_at=fixed_now.isoformat())
        self.player = {'id': PLAYER_ID, 'nickname': 'Mike T.' if args.owner else 'Synthetic One',
                       'emoji': '🏈', 'onboarding_completed_at': self.week['published_at']}
        others = [{'id': f'00000000-0000-4000-8000-{i:012d}', 'nickname': f'Synthetic {i}',
                   'emoji': '🏈', 'onboarding_completed_at': self.week['published_at']} for i in range(2,16)]
        self.tables = {'weeks': [self.week], 'player_pool': pool, 'nfl_games': games,
                       'players': [self.player, *others], 'lineups': [], 'lineup_picks': [],
                       'data_runs': [], 'weekly_results': [], 'season_champions': [],
                       'app_meta': [], 'refresh_leases': []}
        for person in others:
            lid = 'lineup-' + person['id']
            self.tables['lineups'].append({'id': lid, 'week_id': WEEK_ID, 'player_id': person['id']})
            for pos in ['QB','RB','WR','TE','K']:
                self.tables['lineup_picks'].append({'id': lid + pos, 'lineup_id': lid,
                                                   'position': pos, 'pool_player_id': 'pool-0-' + pos})
        for week_no in range(1,8):
            for rank, person in enumerate([self.player, *others], 1):
                self.tables['weekly_results'].append({'id': f'history-{week_no}-{rank}',
                    'week_id': f'history-week-{week_no}', 'season': 2026, 'nfl_week': week_no,
                    'player_id': person['id'], 'nickname_snapshot': person['nickname'],
                    'emoji_snapshot': person['emoji'], 'weekly_score': 100-rank,
                    'finish_rank': rank, 'season_points': 13-rank,
                    'is_champion': rank == 1, 'finalized_at': '2026-10-19T13:00:00+00:00'})
        summaries = {}
        for row in pool:
            summaries[row['id']] = {'gp': 7, 'passing_yards_pg': 200.0, 'passing_tds': 14,
                 'rushing_yards_pg': 60.0, 'receiving_yards_pg': 55.0,
                 'receptions_pg': 4.0, 'total_tds': 5, 'fg_made': 15, 'xp_made': 20, 'fg_pct': 90.0}
        from player_season_stats import snapshot_key, STATS_SNAPSHOT_SCHEMA
        self.tables['app_meta'].append({'key': snapshot_key(self.week), 'value': {
            'schema': STATS_SNAPSHOT_SCHEMA, 'through_week': 7, 'players': summaries}})
        self.tables['app_meta'].append({'key': 'commissioner_owner:v1', 'value': {'player_id': PLAYER_ID}})
    def _table(self, name):
        return Query(self, name)
    def expire(self):
        # Model natural TTL expiry only for ordinary completed cache entries.
        for key, (_, value) in list(self._public_cache.items()):
            self._public_cache[key] = (0.0, value)

fs = AuditStore()
class BoundStore(store_module.SupabaseStore):
    def __new__(cls, *a, **kw):
        return fs
store_module.SupabaseStore = BoundStore
st.cache_resource.clear()
app = AppTest.from_file(str(source / 'app.py'), default_timeout=20)
app.secrets.update({'SUPABASE_URL': 'https://audit.invalid', 'SUPABASE_SECRET_KEY': 'synthetic-key',
                    'PIN_PEPPER': 'synthetic-pin', 'SESSION_PEPPER': 'synthetic-session',
                    'COMMISH_USERNAME': 'synthetic-admin', 'COMMISH_PIN': '123456'})
app.session_state['player'] = deepcopy(fs.player)
app.session_state['remember_restore_checked'] = True
# Match already-shuffled session orders across the two independent app runs.
for position in ['QB','RB','WR','TE','K']:
    app.session_state[f'pool_order::{PLAYER_ID}::{WEEK_ID}::{position}'] = [
        f'pool-{i}-{position}' for i in [2,0,4,1,3]]
results = []

def normalized_tree(node):
    proto = MessageToDict(node.proto, preserving_proto_field_name=True) if node.proto is not None else {}
    def clean(value):
        if isinstance(value, dict):
            return {k:clean(v) for k,v in value.items() if k not in {'id','form_id','fragment_id'}}
        if isinstance(value,list): return [clean(v) for v in value]
        if isinstance(value,str):
            # Only the intentional build label differs across releases.
            return value.replace('Build ' + config.APP_VERSION, 'Build <version>')
        return value
    record = {'type':node.type,'proto':clean(proto)}
    if hasattr(node,'children'):
        record['children'] = [normalized_tree(v) for v in node.children.values()]
    elif node.type in {'button_group','selectbox','text_input','checkbox'}:
        record['value'] = node.value
    return record

def measure(name, action=None, *, allow_error=False):
    fs.queries.clear()
    fs.operations.clear()
    calls.clear()
    emissions.clear()
    started = time.perf_counter()
    if action:
        action()
    app.run()
    duration = time.perf_counter() - started
    assert not app.exception, [x.message for x in app.exception]
    assert allow_error or not app.error, [x.value for x in app.error]
    assert not blocked_attempts, blocked_attempts
    record = {'scenario': name, 'seconds': duration,
              'full_runs': calls['ui.py:hero'], 'queries': deepcopy(fs.queries),
              'query_count': len(fs.queries), 'operations': dict(Counter(fs.operations)),
              'protobuf_emissions_by_run': {str(run): {
                  'messages':sum(1 for e in emissions if e['run'] == run),
                  'bytes':sum(e['bytes'] for e in emissions if e['run'] == run)}
                  for run in sorted({e['run'] for e in emissions})},
              'calls': dict(calls), 'buttons': [{'label': b.label, 'disabled': b.disabled} for b in app.button],
              'errors': [e.value for e in app.error],
              'saved_picks': len([p for p in fs.tables['lineup_picks'] if any(
                  l['id'] == p['lineup_id'] and l['player_id'] == PLAYER_ID for l in fs.tables['lineups'])]),
              'own_picks': deepcopy([p for p in fs.tables['lineup_picks'] if any(
                  l['id'] == p['lineup_id'] and l['player_id'] == PLAYER_ID for l in fs.tables['lineups'])]),
              'ui_tree': normalized_tree(app.main),
              'mode': app.session_state['builder_mode'], 'position': app.session_state['builder_position'],
              'reactions': deepcopy([r for r in fs.tables['app_meta'] if r['key'].startswith('pickem_pulse_reaction:')])}
    results.append(record)
    print(name, record['full_runs'], record['query_count'], round(duration, 3), flush=True)

def button(label):
    return next(b for b in app.button if b.label == label)
def card(pos, i=0):
    return next(b for b in app.button if f'Synthetic {i} {pos}' in b.label)


# Populate 15 participants, including an empty and a partial lineup. Shuffle
# table storage independently so the experiment cannot rely on accidental order.
import random
from gate4 import build_weekly_leaderboard, build_storylines, build_weekly_recap
from lineup_reveal import build_lineup_reveal
from clock_broadcast import build_clock_snapshot
from gate4_results import archive_week_results
from newsletter import build_tuesday_newsletter, perfect_lineup
from personal_season_story import build_personal_season_story
from pickem_pulse import live_pulse, personal_goal

fs.tables['lineups'].insert(0, {'id':'own-lineup','week_id':WEEK_ID,'player_id':PLAYER_ID,'confirmed_at':'2026-10-25T16:30:00+00:00'})
fs.tables['lineup_picks'] = []
for i, lineup in enumerate(fs.tables['lineups']):
    positions = ['QB','RB','WR','TE','K'] if i < 13 else (['QB','RB','WR'] if i == 13 else [])
    for pos in positions:
        rank = 5 if i == 0 and pos in {'QB','TE'} else i % 5
        fs.tables['lineup_picks'].append({'id':lineup['id']+pos,'lineup_id':lineup['id'],
            'position':pos,'pool_player_id':f'pool-{rank}-{pos}',
            'emergency_pool_player_id':'pool-6-QB' if i == 0 and pos == 'QB' else None})
next(p for p in fs.tables['player_pool'] if p['id']=='pool-5-QB')['availability_status']='OUT'
# A private field on the account table must never enter the public bundle.
for row in fs.tables['players']:
    row.update(pin_hash='DO-NOT-SELECT-SYNTHETIC',pin_salt='DO-NOT-SELECT-SYNTHETIC')
rng=random.Random(114)
for table in ['lineups','lineup_picks','players']:
    rng.shuffle(fs.tables[table])
fixed_now = datetime(2026,10,25,18,0,tzinfo=timezone.utc)
fs.week.update(data_status='LIVE',last_data_refresh_at=fixed_now.isoformat())
for row in fs.tables['nfl_games']:
    row.update(game_status='LIVE',provider_updated_at=fixed_now.isoformat(),period=2)
fs.tables['data_runs'].append({'id':'state-fresh','run_type':'live_game_state','week_id':WEEK_ID,
    'started_at':fixed_now.isoformat(),'completed_at':fixed_now.isoformat(),'success':True})
measure('live_cold_15_players')
measure('live_warm')
fs.expire()
measure('live_expired_cache')
measure('own_roster_open',lambda:next(b for b in app.button if '← YOU' in b.label).click())
measure('own_roster_close',lambda:next(b for b in app.button if '← YOU' in b.label).click())
measure('other_roster_open',lambda:next(b for b in app.button if 'pts' in b.label and '← YOU' not in b.label).click())
selected_player = app.session_state['gate4_detail_player_id']
selected_other = next(l['id'] for l in fs.tables['lineups'] if l['player_id'] == selected_player)
measure('other_roster_switch',lambda:next(b for b in app.button if 'pts' in b.label and '← YOU' not in b.label and str(b.key) != 'leaderbtn_' + selected_other).click())
measure('cheer_add',lambda:next(b for b in app.button if str(b.key).startswith('pulse_emoji:')).click())
measure('cheer_remove',lambda:next(b for b in app.button if str(b.key).startswith('pulse_emoji:')).click())
measure('season_control',lambda:app.button_group[0].set_value('🏆 Season'))
measure('return_live',lambda:app.button_group[0].set_value('🏈 Sunday'))
# Actual store override path; write is outside the timed next-render measurement.
fs.set_manual_score_override(WEEK_ID,'pool-6-QB',33.25,'Synthetic audit override')
measure('after_manual_override')
fs.tables['players'] = [p for p in fs.tables['players'] if p['id'] != '00000000-0000-4000-8000-000000000002']
fs.clear_week_cache(WEEK_ID)
measure('missing_profile_left_join')
fs.update_week_data_state(WEEK_ID,data_status='PROVISIONAL')
measure('provisional_results')
fs.update_week_data_state(WEEK_ID,data_status='FINAL',finalized_at=fixed_now.isoformat())
measure('final_results')
fs.tables['lineup_picks']=[]
fs.clear_week_cache(WEEK_ID)
measure('empty_lineups_final')
fs.tables['lineups']=[]
fs.clear_week_cache(WEEK_ID)
measure('no_lineups_final')

result = {'source':str(source),'version':config.APP_VERSION,'variant':args.variant,
    'python':sys.version,'streamlit':st.__version__,'delay_per_query_seconds':args.delay,
    'linked_owner':args.owner,'blocked_network_attempts':len(blocked_attempts),'results':results,
    'limitations':['Actual application source is used unchanged; only I/O and dates are modeled.',
        'PostgREST JSON relationship semantics are modeled, not executed against a real database.',
        'AppTest server UI trees and synthetic waiting; no physical phone or production timing.',
        'Missing profile with retained lineup is a defensive fixture, not a claim about valid FK data.',
        'Reaction reruns remain; roster detail uses the actual release callback.']}
output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')

