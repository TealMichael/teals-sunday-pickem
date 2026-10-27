"""Network-free regressions for transport reuse and frozen picker statistics."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from threading import Event, RLock
from types import SimpleNamespace

import httpx
import pytest

from store import PICKEM_SCHEMA, StoreError, SupabaseStore
import player_season_stats as stats


@pytest.fixture
def wire_store(monkeypatch):
    from postgrest._sync import client as pg
    for key in os.environ:
        if key.lower().endswith('_proxy'):
            monkeypatch.delenv(key, raising=False)
    original = pg.Client
    clients, requests = [], []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=[{'id': request.url.params.get('id', 'fixture')}])

    def client(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handle)
        kwargs['trust_env'] = False
        result = original(*args, **kwargs)
        clients.append(result)
        return result

    monkeypatch.setattr(pg, 'Client', client)
    store = SupabaseStore('https://audit.invalid', 'audit-placeholder-key')
    yield store, clients, requests
    for client in clients:
        client.close()
    store.client.auth.close()


def test_one_transport_for_repeated_and_concurrent_independent_queries(wire_store):
    store, clients, requests = wire_store
    assert len(clients) == 1
    with ThreadPoolExecutor(max_workers=8) as executor:
        rows = list(executor.map(
            lambda i: store._table('weeks').select('id').eq('id', str(i)).execute().data,
            range(100),
        ))
    assert len(clients) == 1
    assert len(requests) == 100
    assert [row[0]['id'] for row in rows] == [f'eq.{i}' for i in range(100)]
    assert all(r.headers['accept-profile'] == PICKEM_SCHEMA for r in requests)
    assert all(r.extensions['timeout'] == {'connect': 8, 'read': 8, 'write': 8, 'pool': 8} for r in requests)
    assert store.client.options.auto_refresh_token is False
    assert store.client.options.persist_session is False


@pytest.mark.parametrize('operation', ['select', 'insert', 'upsert', 'update', 'delete'])
def test_request_semantics_match_original_schema_route(wire_store, operation):
    store, clients, requests = wire_store

    def prepare(table):
        if operation == 'select':
            return table.select('id,label').eq('id', 'w1').limit(1)
        if operation == 'insert':
            return table.insert({'id': 'w1', 'label': 'fixture'})
        if operation == 'upsert':
            return table.upsert({'id': 'w1', 'label': 'fixture'}, on_conflict='id')
        if operation == 'update':
            return table.update({'label': 'fixture'}).eq('id', 'w1')
        return table.delete().eq('id', 'w1')

    # Execute both constructions only through the in-memory HTTP transport.
    prepare(store.client.schema(PICKEM_SCHEMA).table('weeks')).execute()
    prepare(store._table('weeks')).execute()
    old, new = requests[-2:]
    assert old.method == new.method
    assert old.url == new.url
    assert old.content == new.content
    # The legacy child client duplicates X-Client-Info. It is identification
    # metadata, not an auth/schema/query option. All other headers must match.
    assert {k: v for k, v in old.headers.items() if k != 'x-client-info'} == {
        k: v for k, v in new.headers.items() if k != 'x-client-info'
    }
    assert 'supabase-py/2.31.0' in new.headers['x-client-info']
    assert old.extensions['timeout'] == new.extensions['timeout']
    fresh = store._table('players').select('id')
    assert 'id=' not in str(fresh.request.params)
    assert 'on_conflict' not in str(fresh.request.params)


class MetaStore(SupabaseStore):
    def __init__(self):
        self.meta, self.reads = {}, []
        self._season_card_stats_cache = {}
        self._season_card_stats_lock = RLock()
        self.fail_write = False
        self.after_write = None

    def get_app_meta(self, key):
        self.reads.append(key)
        return deepcopy(self.meta.get(key))

    def _table(self, name):
        assert name == 'app_meta'

        def upsert(payload, **kwargs):
            def execute():
                if self.fail_write:
                    raise StoreError('Synthetic write failure')
                self.meta[payload['key']] = deepcopy(payload)
                if self.after_write:
                    self.after_write()
                return SimpleNamespace(data=[deepcopy(payload)])
            return SimpleNamespace(execute=execute)
        return SimpleNamespace(upsert=upsert)


KEY = 'season_card_stats:2026:2:v1'
SNAPSHOT = {'schema': 1, 'season': 2026, 'nfl_week': 2, 'through_week': 1,
            'players': {'hidden-reserve': {'gp': 1, 'passing_yards_pg': 250}}}


def load(store, key=KEY, schema=1, through=1):
    return store.get_season_card_stats(key, schema=schema, through_week=through)


def test_completed_snapshot_reads_once_and_is_copy_isolated_across_callers():
    store = MetaStore()
    store.meta[KEY] = {'value': deepcopy(SNAPSHOT)}
    with ThreadPoolExecutor(max_workers=8) as executor:
        copies = list(executor.map(lambda _: load(store), range(16)))
    assert store.reads == [KEY]
    copies[0]['value']['players']['hidden-reserve']['gp'] = 999
    assert load(store)['value'] == SNAPSHOT
    assert all(row['value'] == SNAPSHOT for row in copies[1:])
    cards = stats.attach_snapshot([{'id': 'hidden-reserve'}], load(store)['value'])
    cards[0]['_season_stats']['gp'] = 123
    assert load(store)['value'] == SNAPSHOT


@pytest.mark.parametrize('value', [None, {}, {'retry_after': '2099-01-01T00:00:00+00:00'},
    {**SNAPSHOT, 'players': {}}, {**SNAPSHOT, 'schema': 9},
    {**SNAPSHOT, 'through_week': 0}, {**SNAPSHOT, 'players': []}])
def test_missing_failed_empty_and_mismatched_snapshots_are_never_frozen(value):
    store = MetaStore()
    if value is not None:
        store.meta[KEY] = {'value': deepcopy(value)}
    assert load(store) == load(store)
    assert store.reads == [KEY, KEY]
    assert not store._season_card_stats_cache


def test_keys_separate_seasons_weeks_and_schema_and_never_cache_authorization():
    store = MetaStore()
    for key, schema, through in [(KEY, 1, 1), ('season_card_stats:2027:2:v1', 1, 1),
                                 ('season_card_stats:2026:3:v1', 1, 2),
                                 ('season_card_stats:2026:2:v2', 2, 1)]:
        store.meta[key] = {'value': {**deepcopy(SNAPSHOT), 'schema': schema, 'through_week': through}}
        assert load(store, key, schema, through) == load(store, key, schema, through)
    assert len(store.reads) == 4
    for key in ['commissioner_owner:v1', 'commissioner_device:v1:fixture', 'pickem_pulse_reaction:w:p']:
        store.meta[key] = {'value': deepcopy(SNAPSHOT)}
        load(store, key)
        load(store, key)
        assert store.reads.count(key) == 2


def test_confirmed_write_invalidates_only_changed_frozen_key_and_failure_preserves_it():
    store = MetaStore()
    store.meta[KEY] = {'value': deepcopy(SNAPSHOT)}
    load(store)
    store.set_app_meta('commissioner_owner:v1', {'player_id': 'fixture'})
    load(store)
    assert store.reads == [KEY]
    changed = {**deepcopy(SNAPSHOT), 'players': {'hidden-reserve': {'gp': 2}}}
    store.set_app_meta(KEY, changed)
    assert load(store)['value'] == changed
    assert store.reads == [KEY, KEY]
    store.fail_write = True
    with pytest.raises(StoreError):
        store.set_app_meta(KEY, SNAPSHOT)
    assert load(store)['value'] == changed


def test_inflight_old_read_cannot_leave_stale_cache_after_write_returns():
    store = MetaStore()
    store.meta[KEY] = {'value': deepcopy(SNAPSHOT)}
    entered, written, release = Event(), Event(), Event()
    original = store.get_app_meta

    def held_read(key):
        row = original(key)
        entered.set()
        assert release.wait(3)
        return row

    store.get_app_meta = held_read
    store.after_write = written.set
    changed = {**deepcopy(SNAPSHOT), 'players': {'hidden-reserve': {'gp': 3}}}
    with ThreadPoolExecutor(max_workers=2) as executor:
        reader = executor.submit(load, store)
        assert entered.wait(3)
        writer = executor.submit(store.set_app_meta, KEY, changed)
        try:
            assert written.wait(3)
        finally:
            release.set()
        reader.result(timeout=3)
        writer.result(timeout=3)
    store.get_app_meta = original
    assert load(store)['value'] == changed


def test_snapshot_loader_preserves_retry_marker_and_provider_lease_rules():
    store = MetaStore()
    week = {'id': 'w2', 'season': 2026, 'nfl_week': 2, 'published_at': 'published'}
    until = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
    store.meta[KEY] = {'value': {'retry_after': until}}
    store.claim_refresh_lease = lambda *a, **k: pytest.fail('Unexpired failure marker must not acquire a lease')
    assert stats.load_or_prepare_snapshot(store, week) is None
    # A different process can publish a successful value while this one is open.
    store.meta[KEY] = {'value': deepcopy(SNAPSHOT)}
    assert stats.load_or_prepare_snapshot(store, week) == SNAPSHOT
    assert stats.load_or_prepare_snapshot(store, week) == SNAPSHOT
    assert store.reads == [KEY, KEY]
    assert stats.load_or_prepare_snapshot(store, {**week, 'is_demo': True}) is None
    assert stats.load_or_prepare_snapshot(store, {**week, 'published_at': None}) is None


def test_transient_snapshot_read_failure_is_not_cached():
    store = MetaStore()
    week = {'id': 'w2', 'season': 2026, 'nfl_week': 2, 'published_at': 'published'}
    original = store.get_app_meta
    store.get_app_meta = lambda key: (_ for _ in ()).throw(OSError('Synthetic outage'))
    assert stats.load_or_prepare_snapshot(store, week) is None
    store.get_app_meta = original
    store.meta[KEY] = {'value': deepcopy(SNAPSHOT)}
    assert stats.load_or_prepare_snapshot(store, week) == SNAPSHOT
