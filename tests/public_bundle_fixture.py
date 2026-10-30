"""Synthetic SQL responses for actual v1.0.14 store methods and consumers. No network."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import random
from threading import Event, RLock, get_ident
from time import sleep

from postgrest.exceptions import APIError
from espn_performance_fixture import Store, Query as BaseQuery, fixture, WEEK
from public_query_fixture import project
from gate4 import build_weekly_leaderboard, build_storylines, build_weekly_recap, build_season_standings
from lineup_reveal import build_lineup_reveal
from clock_broadcast import build_clock_snapshot
from gate4_results import archive_week_results
from newsletter import build_tuesday_newsletter, perfect_lineup
from personal_season_story import build_personal_season_story
from pickem_pulse import live_pulse, personal_goal

NOW = datetime(2026,10,25,18,0,tzinfo=timezone.utc)
class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

class Query(BaseQuery):
    def select(self, fields='*', **kw):
        self.fields = fields
        return self
    def execute(self):
        with self.store.lock:
            self.store.requests.append({'table':self.table,'operation':self.operation,'select':getattr(self,'fields',None)})
            self.store.owner = get_ident()
            result = super().execute()
            if self.operation == 'select':
                result.data = project(result.data,getattr(self,'fields','*'),self.store.tables)
            hold = self.table == self.store.hold_table and not self.store.started.is_set()
            if hold: self.store.started.set()
            fail = self.store.fail_code if ',players(' in getattr(self,'fields','') else None
            if fail: self.store.fail_code = None
            malformed = self.store.malformed if ',players(' in getattr(self,'fields','') else None
        if self.store.delay: sleep(self.store.delay)
        if hold:
            assert self.store.release.wait(10), 'Paused read not released'
            if self.store.fail_held:
                raise OSError('Synthetic read failure')
        if fail:
            raise APIError({'code':fail,'message':'Synthetic server error','details':None,'hint':None})
        if malformed and result.data:
            if malformed == 'missing_profile': result.data[0].pop('players')
            if malformed == 'array_profile': result.data[0]['players'] = []
            if malformed == 'wrong_player': result.data[0]['players']['id'] = 'wrong-player'
        return result

class BenchStore(Store):
    def __init__(self, variant='release', count=15, delay=0):
        games,pool,_ = fixture()
        super().__init__(games,pool)
        self.lock=RLock(); self.requests=[]; self.delay=delay
        self.hold_table=None; self.started=Event(); self.release=Event(); self.waiting=Event()
        self.lookups=0; self.fail_held=False; self.fail_code=None; self.malformed=None
        self.tables['weeks'][0].update(label='Week 8',published_at='2026-10-20T10:00:00+00:00',
            opens_at='2026-10-20T10:00:00+00:00',last_data_refresh_at=NOW.isoformat(),is_demo=False)
        self.tables['players']=[]; self.tables['lineups']=[]; self.tables['lineup_picks']=[]
        self.tables['weekly_results']=[]; self.tables['app_meta']=[]
        for i in range(count):
            self.tables['players'].append({'id':f'p{i}','nickname':f'Synthetic {i:02}','emoji':'🏈',
                'pin_hash':'NEVER-PUBLIC','pin_salt':'NEVER-PUBLIC'})
            self.tables['lineups'].append({'id':f'l{i}','week_id':WEEK['id'],'player_id':f'p{i}',
                'confirmed_at':NOW.isoformat() if i%2 else None})
            positions=['QB','RB','WR','TE','K'] if i != count-1 or count == 1 else ['QB','RB','WR']
            for position in positions:
                rank=5 if i == 0 and position in {'QB','TE'} else i%5
                self.tables['lineup_picks'].append({'id':f'pick{i}{position}','lineup_id':f'l{i}',
                    'position':position,'pool_player_id':f'pool-{rank}-{position}',
                    'emergency_pool_player_id':'pool-6-QB' if i==0 and position=='QB' else None})
            for prior in (6,7):
                self.tables['weekly_results'].append({'id':f'h{prior}-{i}','week_id':f'w{prior}',
                    'season':2026,'nfl_week':prior,'player_id':f'p{i}','nickname_snapshot':f'Synthetic {i:02}',
                    'emoji_snapshot':'🏈','weekly_score':100-i,'finish_rank':i+1,'season_points':max(0,12-i),
                    'is_champion':i==0,'finalized_at':NOW.isoformat()})
        for row in self.tables['player_pool']:
            row.update(schedule_eligible=True,kickoff_at=WEEK['locks_at'],opponent_abbr='SYN')
        next(p for p in self.tables['player_pool'] if p['id']=='pool-5-QB')['availability_status']='OUT'
        next(p for p in self.tables['player_pool'] if p['id']=='pool-6-QB')['manual_score_override']=23.75
        rng=random.Random(114)
        for table in ['players','lineups','lineup_picks']: rng.shuffle(self.tables[table])
        if variant == 'legacy': self._load_week_public_bundle = self._load_week_public_bundle_legacy
    def _table(self, name): return Query(self,name)
    def _cache_get(self,key):
        if key[0]=='gate4_bundle':
            with self.lock:
                self.lookups+=1
                if self.lookups>=8: self.waiting.set()
        return super()._cache_get(key)

def public_rows(bundle):
    # Profile query order was unspecified. Pick/lineup order must remain exact.
    result=deepcopy(bundle)
    for key in ('players',): result[key]=sorted(result[key],key=lambda r:str(r['id']))
    return result

def consumer_outputs(store):
    week=store.get_week(WEEK['id'])
    bundle=store.get_week_public_bundle(WEEK['id'],fresh=True)
    assert 'NEVER-PUBLIC' not in json.dumps(bundle)
    board=build_weekly_leaderboard(bundle)
    clock=build_clock_snapshot(store,week,now=NOW)
    assert 'PHI' in clock['live_games'] and 'WAS' in clock['live_games']
    history=store.get_weekly_results(season=2026)
    final={**week,'data_status':'FINAL','finalized_at':NOW.isoformat()}
    archive=archive_week_results(store,final)
    results=store.get_weekly_results(season=2026)
    values={'public_rows':public_rows(bundle),'standings':board,
        'storylines':build_storylines(bundle,board),'recap':build_weekly_recap(bundle,board,results,current_week=8),
        'lineup_reveal':build_lineup_reveal(bundle),'clock':clock,'archive':archive,
        'season':build_season_standings(results),'achievements':build_personal_season_story(results,'p0'),
        'newsletter':build_tuesday_newsletter(final_week=final,final_results=archive['rows'],
            perfect=perfect_lineup(bundle['pool']),season_results=results,next_week={'nfl_week':9},
            lineup_url='https://example.invalid/pickem'),
        'pulse':live_pulse(board,'p0',None,personal_goal(history,'p0')),
        'saved_picks':store.tables['lineup_picks']}
    return {k:digest(v) for k,v in values.items()}

