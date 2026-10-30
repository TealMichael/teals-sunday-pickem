"""Actual loader acceptance: public data, order, freshness, failure and wire semantics."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib
import json
import os
import random
from types import SimpleNamespace

import httpx
import pytest
from postgrest.exceptions import APIError
from public_bundle_fixture import BenchStore, FixedDateTime, WEEK, consumer_outputs, public_rows
from public_query_fixture import project
from store import StoreError, SupabaseStore

@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    for name in ['store','weekly','gate4','clock_broadcast','gate4_results','newsletter','personal_season_story','pickem_pulse']:
        monkeypatch.setattr(importlib.import_module(name), 'datetime', FixedDateTime, raising=False)

@pytest.mark.parametrize('count', [0,1,15,50])
def test_all_public_consumers_match_original_loader(count):
    old, new = BenchStore('legacy',count=count), BenchStore(count=count)
    assert consumer_outputs(old) == consumer_outputs(new)
    assert len(consumer_outputs(new)) == 12

@pytest.mark.parametrize('shape', ['no_picks','no_profile','partial','duplicate_profile'])
def test_empty_partial_left_join_and_profile_dedup_keep_outputs(shape):
    old, new = BenchStore('legacy'), BenchStore()
    if shape == 'no_picks': old.tables['lineup_picks'] = []
    elif shape == 'no_profile': old.tables['players'] = old.tables['players'][1:]
    elif shape == 'partial': old.tables['lineup_picks'] = old.tables['lineup_picks'][::2]
    else:
        old.tables['lineups'].append({**old.tables['lineups'][0], 'id':'duplicate-fixture'})
    new.tables = deepcopy(old.tables)
    assert consumer_outputs(old) == consumer_outputs(new)
    bundle = new.get_week_public_bundle(WEEK['id'])
    assert len(bundle['players']) == len({p['id'] for p in bundle['players']})
    assert len(bundle['lineups']) == len(new.tables['lineups'])

@pytest.mark.parametrize('seed', range(30))
def test_equal_name_ties_keep_original_pick_order_and_all_consumers(seed):
    old, new = BenchStore('legacy',count=11), BenchStore(count=11)
    rng = random.Random(seed)
    for table in ['lineups','lineup_picks','players']: rng.shuffle(old.tables[table])
    for row in old.tables['player_pool']:
        if row['id'] in {'pool-0-QB','pool-1-QB'}: row['player_name'] = 'Same Name QB'
    new.tables = deepcopy(old.tables)
    before, after = old.get_week_public_bundle(WEEK['id']), new.get_week_public_bundle(WEEK['id'])
    assert before['picks'] == after['picks']
    assert consumer_outputs(old) == consumer_outputs(new)

def test_four_queries_hidden_pool_all_games_no_private_profile_fields():
    store = BenchStore()
    bundle = store.get_week_public_bundle(WEEK['id'])
    assert [r['table'] for r in store.requests] == ['lineups','lineup_picks','player_pool','nfl_games']
    assert store.requests[0]['select'] == 'id,week_id,player_id,confirmed_at,created_at,updated_at,players(id,nickname,emoji)'
    assert store.requests[1]['select'] == 'id,lineup_id,position,pool_player_id,emergency_pool_player_id,updated_at'
    assert 'NEVER-PUBLIC' not in json.dumps(bundle)
    assert all(set(p) == {'id','nickname','emoji'} for p in bundle['players'])
    assert len(bundle['pool']) == 45 and any(not p['is_visible'] for p in bundle['pool'])
    assert len(bundle['games']) == 10 and bundle['games'][-1]['home_team'] == 'PHI'
    assert next(p for p in bundle['pool'] if p['id']=='pool-6-QB')['manual_score_override'] == 23.75

@pytest.mark.parametrize('code', ['PGRST200','PGRST201'])
def test_only_relationship_errors_use_exact_legacy_reads_without_sticky_fallback(code):
    store = BenchStore(); store.fail_code = code
    value = store.get_week_public_bundle(WEEK['id'])
    assert public_rows(value) == public_rows(BenchStore('legacy').get_week_public_bundle(WEEK['id']))
    assert [r['table'] for r in store.requests] == ['lineups','lineups','lineup_picks','players','player_pool','nfl_games']
    assert store.get_week_public_bundle(WEEK['id']) == value and len(store.requests) == 6
    store.clear_week_cache(WEEK['id']); store.requests.clear()
    assert public_rows(store.get_week_public_bundle(WEEK['id'])) == public_rows(value)
    assert len(store.requests) == 4

@pytest.mark.parametrize('code', ['42501','PGRST000','PGRST301','57014','XX000'])
def test_other_api_failures_propagate_and_do_not_cache(code):
    store = BenchStore(); store.fail_code = code
    with pytest.raises(APIError) as exc: store.get_week_public_bundle(WEEK['id'])
    assert exc.value.code == code
    assert len(store.requests) == 1 and not store._public_cache and not store._bundle_flights
    assert store.get_week_public_bundle(WEEK['id'])['lineups']
    assert len(store.requests) == 5

@pytest.mark.parametrize('malformed', ['missing_profile','array_profile','wrong_player'])
def test_malformed_join_rejected_then_recoverable(malformed):
    store = BenchStore(); store.malformed = malformed
    with pytest.raises(StoreError): store.get_week_public_bundle(WEEK['id'])
    assert len(store.requests) == 1 and not store._public_cache
    store.malformed = None
    assert store.get_week_public_bundle(WEEK['id'])['lineups']

@pytest.mark.parametrize('shape', ['dict','false','missing_lineup_id','null_player','profile_missing_nickname','profile_empty','string_row'])
def test_invalid_response_shape_never_becomes_partial_cache(monkeypatch,shape):
    store = BenchStore(); table = store._table
    def broken(name):
        query = table(name); original = query.execute
        if name == 'lineups':
            def execute():
                result = original()
                if shape == 'dict': result.data = {}
                elif shape == 'false': result.data = False
                elif shape == 'missing_lineup_id': result.data[0].pop('id')
                elif shape == 'null_player': result.data[0]['player_id'] = None
                elif shape == 'profile_missing_nickname': result.data[0]['players'].pop('nickname')
                elif shape == 'profile_empty': result.data[0]['players'] = {}
                else: result.data[0] = 'invalid'
                return result
            query.execute = execute
        return query
    monkeypatch.setattr(store,'_table',broken)
    with pytest.raises(StoreError): store.get_week_public_bundle(WEEK['id'])
    assert not store._public_cache and not store._bundle_flights

@pytest.mark.parametrize('table', ['lineups','lineup_picks','player_pool','nfl_games'])
def test_failure_at_each_read_wakes_all_waiters_without_partial_cache(table):
    store = BenchStore(); store.hold_table = table; store.fail_held = True
    with ThreadPoolExecutor(max_workers=8) as ex:
        jobs = [ex.submit(store.get_week_public_bundle,WEEK['id']) for _ in range(8)]
        try: assert store.started.wait(10) and store.waiting.wait(10)
        finally: store.release.set()
        for job in jobs:
            with pytest.raises(OSError,match='Synthetic'): job.result(timeout=10)
    assert not store._public_cache and not store._bundle_flights
    store.fail_held = False
    assert store.get_week_public_bundle(WEEK['id'])['lineups']

def test_fresh_during_normal_inflight_load_does_not_wait_or_publish_cache():
    store = BenchStore(); store.hold_table = 'lineups'
    with ThreadPoolExecutor(max_workers=2) as ex:
        ordinary = ex.submit(store.get_week_public_bundle,WEEK['id'])
        assert store.started.wait(10)
        try:
            fresh = ex.submit(store.get_week_public_bundle,WEEK['id'],fresh=True).result(timeout=10)
            assert fresh['lineups'] and ('gate4_bundle',WEEK['id']) not in store._public_cache
        finally: store.release.set()
        assert ordinary.result(timeout=10) == fresh
    assert len(store.requests) == 8
    assert store.get_week_public_bundle(WEEK['id']) == fresh and len(store.requests) == 8

def test_expiry_and_fresh_profile_reads_keep_copy_isolation():
    store = BenchStore(); cached = store.get_week_public_bundle(WEEK['id'])
    ident = cached['players'][0]['id']
    next(p for p in store.tables['players'] if p['id']==ident)['nickname'] = 'Updated'
    fresh = store.get_week_public_bundle(WEEK['id'],fresh=True)
    assert next(p for p in fresh['players'] if p['id']==ident)['nickname'] == 'Updated'
    assert store.get_week_public_bundle(WEEK['id']) == cached
    fresh['players'][0]['nickname'] = 'Local mutation'
    key = ('gate4_bundle',WEEK['id']); store._public_cache[key] = (0,store._public_cache[key][1])
    expired = store.get_week_public_bundle(WEEK['id'])
    assert next(p for p in expired['players'] if p['id']==ident)['nickname'] == 'Updated'
    assert len(store.requests) == 12

@pytest.mark.parametrize('stage,code', [('lineups',None),('lineups','PGRST200'),('lineups','PGRST201'),('lineups','42501'),('lineup_picks','PGRST200'),('player_pool','PGRST200'),('nfl_games','PGRST200')])
def test_real_sdk_wire_projection_filter_timeout_and_fallback(monkeypatch,stage,code):
    from postgrest._sync import client as pg
    for key in list(os.environ):
        if key.lower().endswith('_proxy'): monkeypatch.delenv(key,raising=False)
    data = BenchStore(count=1).tables
    requests, clients = [], []
    errors = [code] if code else []
    def handle(req):
        requests.append(req); name = req.url.path.rsplit('/',1)[-1]
        if errors and name == stage:
            return httpx.Response(400,json={'code':errors.pop(),'message':'Synthetic SDK failure','details':None,'hint':None})
        return httpx.Response(200,json=project(deepcopy(data[name]),req.url.params.get('select','*'),data))
    original = pg.Client
    def client(*a,**kw):
        kw.update(transport=httpx.MockTransport(handle),trust_env=False)
        value=original(*a,**kw); clients.append(value); return value
    monkeypatch.setattr(pg,'Client',client)
    store = SupabaseStore('https://audit.invalid','synthetic-key')
    try:
        if code and (stage!='lineups' or code=='42501'):
            with pytest.raises(APIError) as exc: store.get_week_public_bundle(WEEK['id'])
            assert exc.value.code == code
            assert not store._public_cache
            assert sum(r.url.path.endswith('/lineups') for r in requests) == 1
        else:
            bundle = store.get_week_public_bundle(WEEK['id'])
            assert len(bundle['lineups']) == 1 and len(bundle['picks']) == 5
            assert len(requests) == (6 if code else 4)
        req = requests[0]
        assert req.method == 'GET'
        assert req.url.params['select'] == 'id,week_id,player_id,confirmed_at,created_at,updated_at,players(id,nickname,emoji)'
        assert req.url.params['week_id'] == 'eq.' + WEEK['id']
        assert all(r.headers['accept-profile'] == 'pickem' for r in requests)
        assert all(r.extensions['timeout'] == dict.fromkeys(['connect','read','write','pool'],8) for r in requests)
        assert all('pin_' not in r.url.params.get('select','') and '!inner' not in r.url.params.get('select','') for r in requests)
        if any(r.url.path.endswith('/lineup_picks') for r in requests):
            assert next(r for r in requests if r.url.path.endswith('/lineup_picks')).url.params['lineup_id'] == 'in.(l0)'
        if any(r.url.path.endswith('/nfl_games') for r in requests):
            assert 'is_eligible' not in next(r for r in requests if r.url.path.endswith('/nfl_games')).url.params
    finally:
        for client in clients: client.close()
        store.client.auth.close()
