"""Bounded HTTP retrieval, failure isolation, ordered scoring and cleanup."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from threading import Barrier, Event, Lock, enumerate as threads, get_ident
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from urllib3.response import HTTPResponse
from urllib3.util.retry import Retry

import nfl_sources
import nfl_sync
import store as store_module
from nfl_sources import ESPNProvider, SourceError, iter_espn_summary_results
from espn_performance_fixture import Store, WEEK, fixture


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 25, 18, 2, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(nfl_sync, "datetime", FixedDateTime)
    monkeypatch.setattr(store_module, "datetime", FixedDateTime)


class FakeSession(requests.Session):
    def __init__(self, factory):
        super().__init__()
        self.factory = factory
        self.owner = get_ident()
        self.closed = False

    def get(self, url, params=None, timeout=None):
        assert self.owner == get_ident(), "HTTP session shared between threads"
        assert not self.closed
        assert timeout == 12
        event = (params or {}).get("gameId") or (params or {}).get("event")
        f = self.factory
        with f.lock:
            f.active += 1
            f.peak = max(f.peak, f.active)
            f.calls.append((event, url))
        try:
            if f.before: f.before(event, url, self)
            if event in f.failures or (f.fallback and url == ESPNProvider.CDN_BOXSCORE_URL):
                raise requests.exceptions.ReadTimeout("Synthetic provider timeout")
            payload = deepcopy(f.summaries[event])
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
        finally:
            with f.lock:
                f.active -= 1
                f.completed.append(event)
            if f.after: f.after(event, url, self)

    def close(self):
        assert self.owner == get_ident(), "Session closed by another thread"
        self.closed = True
        super().close()


class SessionFactory:
    def __init__(self, summaries, *, before=None, after=None, failures=(), fallback=False):
        self.summaries, self.before = summaries, before
        self.after = after
        self.failures, self.fallback = set(failures), fallback
        self.lock = Lock()
        self.sessions, self.calls, self.completed = [], [], []
        self.active = self.peak = 0

    def __call__(self):
        session = FakeSession(self)
        with self.lock: self.sessions.append(session)
        return session


def no_workers_left():
    assert not [t for t in threads() if t.name.startswith("pickem-espn")]


def test_three_requests_overlap_but_fourth_waits_and_results_stay_ordered(monkeypatch):
    _, _, summaries = fixture()
    starts = {event: Event() for event in summaries}
    releases = {event: Event() for event in summaries}
    for event in list(summaries)[3:]: releases[event].set()

    def held(event, url, session):
        starts[event].set()
        assert releases[event].wait(10)

    factory = SessionFactory(summaries, before=held)
    monkeypatch.setattr(nfl_sources, "_session", factory)
    provider = ESPNProvider()
    provider.session.headers["X-Fixture"] = "same"
    provider.session.cookies.set("scoreboard", "retained")
    with ThreadPoolExecutor(max_workers=1) as caller:
        result = caller.submit(lambda: list(iter_espn_summary_results(provider, list(summaries))))
        try:
            for event in list(summaries)[:3]: assert starts[event].wait(10)
            assert factory.peak == 3 and factory.active == 3
            assert not starts["event-03"].is_set()
            releases["event-02"].set()
            assert starts["event-03"].wait(10)
            releases["event-01"].set()
            releases["event-00"].set()
        finally:
            for release in releases.values(): release.set()
        outcomes = result.result(timeout=10)
    assert [p for p,e in outcomes] == list(summaries.values())
    assert all(e is None for p,e in outcomes)
    assert factory.completed[0] == "event-02"
    assert factory.peak == 3 and len(factory.calls) == 10
    assert all(s.closed for s in factory.sessions[1:])
    assert not provider.session.closed
    assert all(s.headers["X-Fixture"] == "same" for s in factory.sessions[1:])
    assert all(s.cookies["scoreboard"] == "retained" for s in factory.sessions[1:])
    assert len({id(s.headers) for s in factory.sessions}) == len(factory.sessions)
    assert len({id(s.cookies) for s in factory.sessions}) == len(factory.sessions)
    # At least one worker uses its session for multiple games.
    assert len(factory.sessions) == 4
    provider.session.close()
    no_workers_left()


@pytest.mark.parametrize("mode", ["success", "mixed_order", "one_timeout", "all_timeout", "parser_error", "missing_player", "fallback"])
def test_concurrent_scoring_matches_sequential_results_and_writes(monkeypatch, mode):
    games, pool, summaries = fixture()
    if mode == "parser_error": summaries["event-02"]["boxscore"]["players"] = [None]
    if mode == "missing_player": summaries["event-02"]["boxscore"]["players"] = []
    failures = ("event-02",) if mode == "one_timeout" else tuple(summaries) if mode == "all_timeout" else ()
    fingerprints = []
    for concurrent in (False, True):
        store = Store(games, pool)
        factory = SessionFactory(summaries, failures=failures, fallback=mode == "fallback")
        if concurrent and mode in {"success", "mixed_order"}:
            arrived = Barrier(3)
            finished = {event:Event() for event in list(summaries)[:3]}
            order = ["event-02", "event-01", "event-00"] if mode == "success" else ["event-01", "event-00", "event-02"]
            def force_order(event, url, session):
                if event in finished:
                    arrived.wait(timeout=10)
                    index = order.index(event)
                    if index: assert finished[order[index-1]].wait(10)
            factory.before = force_order
            factory.after = lambda event,url,session: finished[event].set() if event in finished else None
        monkeypatch.setattr(nfl_sources, "_session", factory)
        provider = ESPNProvider() if concurrent else ESPNProvider(factory())
        caller = get_ident()
        original_parse = ESPNProvider.player_stats
        def parse(payload):
            assert get_ident() == caller
            assert factory.active == 0
            if concurrent: assert all(s.closed for s in factory.sessions[1:])
            return original_parse(payload)
        monkeypatch.setattr(ESPNProvider, "player_stats", staticmethod(parse))
        try:
            result = nfl_sync.refresh_live_player_stats(store, deepcopy(WEEK), provider)
            error = None
        except nfl_sync.Gate3Error as exc:
            result, error = None, type(exc).__name__
        finally:
            monkeypatch.setattr(ESPNProvider, "player_stats", staticmethod(original_parse))
            provider.session.close()
        fingerprints.append((result, error, deepcopy(store.tables), list(store.operations), Counter(factory.calls)))
        if mode == "all_timeout":
            assert error == "Gate3Error"
            assert "weeks.update" not in store.operations and "player_pool.upsert" not in store.operations
            assert all(r["score_total"] == 9.5 for r in store.tables["player_pool"])
        else:
            assert store.operations.count("player_pool.select") == 2
            assert store.operations.count("player_pool.upsert") == 1
            assert len(store.tables["player_pool"]) == 45
            assert sum(not r["is_visible"] for r in store.tables["player_pool"]) == 20
            assert store.tables["lineup_picks"][0]["emergency_pool_player_id"] == "pool-5-QB"
            scores = {r["position"]:r["score_total"] for r in store.tables["player_pool"] if r["team_abbr"] == "BUF"}
            assert scores == {"QB":16.0,"RB":12.7,"WR":16.8,"TE":5.0,"K":9.0}
        assert all(s.closed for s in factory.sessions)
        if concurrent and mode in {"success", "mixed_order"}:
            assert [e for e in factory.completed if e in order] == order
            assert factory.peak == 3
        no_workers_left()
    assert fingerprints[0] == fingerprints[1]


def test_override_during_parallel_wait_is_reread_and_preserved(monkeypatch):
    games, pool, summaries = fixture()
    entered, release = Event(), Event()
    holder = {}
    def hold(event, url, session):
        if event == "event-00":
            entered.set()
            assert release.wait(10)
    factory = SessionFactory(summaries, before=hold)
    monkeypatch.setattr(nfl_sources, "_session", factory)
    def run():
        store = holder["store"] = Store(games, pool)
        provider = ESPNProvider()
        try: return nfl_sync.refresh_live_player_stats(store, WEEK, provider)
        finally: provider.session.close()
    with ThreadPoolExecutor(max_workers=1) as caller:
        job = caller.submit(run)
        try:
            assert entered.wait(10)
            assert holder["store"].operations.count("player_pool.select") == 1
            holder["store"].tables["player_pool"][0]["manual_score_override"] = 37.25
        finally: release.set()
        assert job.result(timeout=10)["players"] == 45
    assert holder["store"].tables["player_pool"][0]["score_total"] == 37.25
    assert holder["store"].operations.count("player_pool.select") == 2
    assert all(s.closed for s in factory.sessions)
    no_workers_left()


def test_game_selection_skips_only_original_cases_and_keeps_live_no_pool(monkeypatch):
    games, pool, summaries = fixture()
    # Final captured, final needing one recapture, scheduled, ineligible, no id.
    games[0]["game_status"] = "FINAL"
    games[1]["game_status"] = "FINAL"
    for row in pool:
        if row["team_abbr"] == "BUF": row["game_status"] = "FINAL"
    games[2]["game_status"] = "SCHEDULED"
    games[3]["is_eligible"] = False
    games[4]["provider_event_id"] = ""
    extra = deepcopy(games[9]); extra.update(provider_event_id="no-pool-final", game_status="FINAL")
    games.append(extra)
    factory = SessionFactory(summaries)
    monkeypatch.setattr(nfl_sources, "_session", factory)
    store = Store(games, pool)
    provider = ESPNProvider()
    try: nfl_sync.refresh_live_player_stats(store, WEEK, provider)
    finally: provider.session.close()
    assert {e for e,u in factory.calls} == {"event-01", "event-05", "event-06", "event-07", "event-08", "event-09"}
    assert all(r["score_total"] == 9.5 for r in store.tables["player_pool"] if r["team_abbr"] == "BUF")


@pytest.mark.parametrize("count", [0,1])
def test_zero_or_one_job_avoids_executor_and_keeps_caller_session(monkeypatch, count):
    _, _, summaries = fixture()
    factory = SessionFactory(summaries)
    monkeypatch.setattr(nfl_sources, "_session", factory)
    def forbidden(*a, **kw): raise AssertionError("Executor unnecessary")
    monkeypatch.setattr(nfl_sources, "ThreadPoolExecutor", forbidden)
    provider = ESPNProvider()
    assert len(list(iter_espn_summary_results(provider, list(summaries)[:count]))) == count
    assert len(factory.sessions) == 1 and not provider.session.closed
    provider.session.close()


@pytest.mark.parametrize("kind", ["custom_session", "subclass", "instance_override", "replaced_session", "duck"])
def test_custom_provider_compatibility_remains_lazy_and_sequential(monkeypatch, kind):
    _, _, summaries = fixture()
    factory = SessionFactory(summaries)
    monkeypatch.setattr(nfl_sources, "_session", factory)
    def forbidden(*a, **kw): raise AssertionError("Custom provider must stay sequential")
    monkeypatch.setattr(nfl_sources, "ThreadPoolExecutor", forbidden)
    if kind == "custom_session": provider = ESPNProvider(factory())
    elif kind == "subclass":
        class Custom(ESPNProvider): pass
        provider = Custom()
    elif kind == "duck": provider = SimpleNamespace(summary=lambda event: summaries[event])
    else:
        provider = ESPNProvider()
        if kind == "instance_override": provider.summary = lambda event: summaries[event]
        else: provider.session = factory()
    values = iter_espn_summary_results(provider, ["event-00", "event-01"])
    assert factory.calls == []
    assert next(values)[0] == summaries["event-00"]
    assert len(factory.calls) <= 1
    assert next(values)[0] == summaries["event-01"]
    assert all(not s.closed for s in factory.sessions)
    for session in factory.sessions: session.close()


def test_duplicate_events_and_normalized_collisions_preserve_input_merge_order(monkeypatch):
    games, pool, summaries = fixture()
    games = [games[0], games[1], deepcopy(games[0])]
    games[1]["home_team"] = "BUF"
    summaries["event-01"] = deepcopy(summaries["event-00"])
    summaries["event-01"]["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][0] = "500"
    summaries["event-01"]["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["athlete"]["displayName"] += " Jr."
    expected = None
    for concurrent in (False,True):
        factory = SessionFactory(summaries)
        monkeypatch.setattr(nfl_sources, "_session", factory)
        provider = ESPNProvider() if concurrent else ESPNProvider(factory())
        store = Store(games,pool)
        try: result = nfl_sync.refresh_live_player_stats(store,WEEK,provider)
        finally: provider.session.close()
        actual = (result, store.tables, store.operations)
        if expected is None: expected = actual
        else: assert actual == expected
        assert Counter(e for e,u in factory.calls) == {"event-00":2,"event-01":1}
        # summary_cache keeps the original insertion order even after a repeat.
        assert store.tables["player_pool"][0]["score_total"] == 26.0


def test_worker_setup_failure_closes_peers_and_prevents_scoring_writes(monkeypatch):
    games,pool,summaries = fixture()
    factory = SessionFactory(summaries)
    counter_lock = Lock()
    created = 0
    def fail_one():
        nonlocal created
        with counter_lock:
            created += 1
            fail = created == 2
        if fail: raise RuntimeError("Synthetic session setup error")
        return factory()
    monkeypatch.setattr(nfl_sources,"_session",fail_one)
    provider = ESPNProvider()
    store = Store(games,pool)
    try:
        with pytest.raises(RuntimeError,match="setup error"):
            nfl_sync.refresh_live_player_stats(store,WEEK,provider)
    finally: provider.session.close()
    assert not store.tables["player_week_stats"]
    assert "player_pool.upsert" not in store.operations
    assert "weeks.update" not in store.operations
    assert store.tables["data_runs"][-1]["success"] is False
    assert all(s.closed for s in factory.sessions)
    no_workers_left()


@pytest.mark.parametrize("failure", ["503", "429", "timeout"])
def test_real_http_adapter_retains_retries_timeouts_and_endpoint_fallback(monkeypatch,failure):
    from urllib3.connectionpool import HTTPSConnectionPool
    from urllib3.exceptions import ReadTimeoutError
    attempts, sleeps = [], []
    def transport(pool,conn,method,url,**kwargs):
        attempts.append((url,kwargs["timeout"].connect_timeout,kwargs["timeout"].read_timeout))
        if "/boxscore" in url:
            if failure == "timeout": raise ReadTimeoutError(pool,url,"Synthetic read timeout")
            return HTTPResponse(status=int(failure),headers={"Retry-After":"2"},body=BytesIO(b"unavailable"),preload_content=False)
        return HTTPResponse(status=200,headers={"Content-Type":"application/json"},
                            body=BytesIO(json.dumps({"header":{"id":"test"}}).encode()),preload_content=False)
    monkeypatch.setattr(HTTPSConnectionPool,"_make_request",transport)
    monkeypatch.setattr(Retry,"sleep",lambda self,response=None:sleeps.append(self.get_retry_after(response) if response else None))
    with nfl_sources._session() as session:
        session.trust_env=False
        payload = ESPNProvider(session).summary("test")
    assert payload == {"header":{"id":"test"}}
    assert len(attempts) == 4
    assert sum("/boxscore" in url for url,c,r in attempts) == 3
    assert "/game?" in attempts[-1][0]
    assert all(c==12 and r==12 for u,c,r in attempts)
    if failure != "timeout": assert sleeps == [2,2]


def test_default_adapter_settings_unchanged():
    with nfl_sources._session() as session:
        retry = session.get_adapter("https://").max_retries
        assert (retry.total,retry.connect,retry.read,retry.backoff_factor) == (2,2,2,0.35)
        assert retry.status_forcelist == (429,500,502,503,504)
        assert retry.allowed_methods == frozenset({"GET"})
        assert retry.respect_retry_after_header
