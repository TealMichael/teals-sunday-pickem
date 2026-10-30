"""Deterministic, network-free cache races for the second performance release."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, RLock
from types import SimpleNamespace

import pytest

from clock_broadcast import build_clock_snapshot
from gate4_results import archive_week_results
from store import SupabaseStore


UTC = timezone.utc


class Query:
    def __init__(self, store, table):
        self.store, self.table = store, table
        self.week_id = ""
        self.change = None
        self.fields = "*"

    def select(self, fields="*", **kwargs):
        self.fields = fields
        return self

    def order(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        if column in {"week_id", "id"}:
            self.week_id = str(value)
        return self

    def in_(self, *args, **kwargs):
        return self

    def update(self, fields):
        self.change = fields
        return self

    def execute(self):
        with self.store.fixture_lock:
            self.store.operations += 1
            if self.change is not None:
                self.store.tables[self.table][0].update(self.change)
            result = deepcopy(self.store.tables[self.table])
            if self.table == "lineups" and ",players(" in self.fields:
                fields = self.fields.split(",players(", 1)[0].split(",")
                projected = []
                for row in result:
                    value = {k: row.get(k) for k in fields}
                    profile = next((p for p in self.store.tables["players"] if p["id"] == row["player_id"]), None)
                    value["players"] = deepcopy(profile)
                    projected.append(value)
                result = projected
            should_hold = (self.store.block_table == self.table
                           and (self.store.block_week is None or self.week_id == self.store.block_week)
                           and not self.store.block_started.is_set())
            if should_hold:
                self.store.block_started.set()
            fail = self.store.fail_first and should_hold
        if should_hold:
            assert self.store.unblock.wait(10), "Probe owner was never released"
        if fail:
            raise OSError("Synthetic database failure")
        return SimpleNamespace(data=result)


class ProbeStore(SupabaseStore):
    def __init__(self):
        # All I/O is an in-memory adapter, never a live Supabase client.
        self._public_cache = {}
        self._public_cache_lock = RLock()
        self._public_cache_generations = {}
        self._bundle_flights = {}
        self.fixture_lock = Lock()
        self.operations = 0
        self.lookups = 0
        self.all_lookups = Event()
        self.block_started = Event()
        self.unblock = Event()
        self.block_table = None
        self.block_week = None
        self.fail_first = False
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        self.tables = {
            "lineups": [{"id": "l1", "week_id": "w1", "player_id": "p1", "confirmed_at": None}],
            "lineup_picks": [{"id": "pick1", "lineup_id": "l1", "position": "QB", "pool_player_id": "q1"}],
            "players": [{"id": "p1", "nickname": "Fixture", "emoji": "🏈"}],
            "weeks": [{"id": "w1", "season": 2026, "nfl_week": 4, "opens_at": past,
                       "data_status": "WAITING", "is_demo": False}],
        }
        self.pool = [{"id": "q1", "position": "QB", "player_name": "Fixture QB",
                      "score_total": 11.5, "availability_status": "HEALTHY", "is_visible": True}]
        self.games = [{"id": "g1", "week_id": "w1", "game_status": "LIVE"}]

    def _table(self, table):
        return Query(self, table)

    def _cache_get(self, key):
        if key[0] == "gate4_bundle":
            with self.fixture_lock:
                self.lookups += 1
                if self.lookups >= 8:
                    self.all_lookups.set()
        return super()._cache_get(key)

    def get_full_week_pool(self, week_id):
        with self.fixture_lock:
            self.operations += 1
            return deepcopy(self.pool)

    def get_nfl_games(self, week_id, *, eligible_only=False):
        with self.fixture_lock:
            self.operations += 1
            return deepcopy(self.games)


def _start_eight(store):
    executor = ThreadPoolExecutor(max_workers=8)
    futures = [executor.submit(store.get_week_public_bundle, "w1") for _ in range(8)]
    return executor, futures


def test_eight_concurrent_cold_readers_share_one_four_query_bundle():
    store = ProbeStore()
    store.block_table = "lineups"
    executor, futures = _start_eight(store)
    try:
        assert store.block_started.wait(10)
        assert store.all_lookups.wait(10)
    finally:
        store.unblock.set()
    try:
        results = [future.result(timeout=10) for future in futures]
    finally:
        executor.shutdown(wait=True)
    assert store.operations == 4
    assert all(result == results[0] for result in results)
    results[0]["pool"][0]["score_total"] = 999
    assert store.get_week_public_bundle("w1")["pool"][0]["score_total"] == 11.5
    assert store.operations == 4


def test_failed_builder_wakes_waiters_and_next_request_retries():
    store = ProbeStore()
    store.block_table = "lineups"
    store.fail_first = True
    executor, futures = _start_eight(store)
    try:
        assert store.block_started.wait(10)
        assert store.all_lookups.wait(10)
    finally:
        store.unblock.set()
    try:
        for future in futures:
            with pytest.raises(OSError, match="Synthetic"):
                future.result(timeout=10)
    finally:
        executor.shutdown(wait=True)
    assert store.operations == 1
    assert not store._public_cache
    assert store.get_week_public_bundle("w1")["lineups"]
    assert store.operations == 5


@pytest.mark.parametrize("clear_all", [False, True])
def test_invalidation_during_inflight_read_discards_stale_generation(clear_all):
    store = ProbeStore()
    store.block_table = "lineups"
    with ThreadPoolExecutor(max_workers=2) as executor:
        old_reader = executor.submit(store.get_week_public_bundle, "w1")
        assert store.block_started.wait(10)
        store.tables["lineups"][0]["confirmed_at"] = "new-confirmation"
        store.clear_week_cache(None if clear_all else "w1")
        fresh = executor.submit(store.get_week_public_bundle, "w1")
        assert fresh.result(timeout=10)["lineups"][0]["confirmed_at"] == "new-confirmation"
        store.unblock.set()
        assert old_reader.result(timeout=10)["lineups"][0]["confirmed_at"] == "new-confirmation"
    assert store.get_week_public_bundle("w1")["lineups"][0]["confirmed_at"] == "new-confirmation"
    assert store.operations == 8


def test_slow_week_does_not_block_a_different_week_key():
    store = ProbeStore()
    store.block_table = "lineups"
    store.block_week = "slow"
    with ThreadPoolExecutor(max_workers=2) as executor:
        slow = executor.submit(store.get_week_public_bundle, "slow")
        assert store.block_started.wait(10)
        fast = executor.submit(store.get_week_public_bundle, "fast")
        try:
            assert fast.result(timeout=10)["pool"]
        finally:
            store.unblock.set()
        assert slow.result(timeout=10)["pool"]
    assert store.operations == 8


def test_short_ttl_does_not_bypass_cache_but_explicit_fresh_does():
    store = ProbeStore()
    assert store.get_week_public_bundle("w1")["pool"][0]["score_total"] == 11.5
    store.pool[0]["score_total"] = 22.0
    assert store.get_week_public_bundle("w1", ttl_seconds=0.01)["pool"][0]["score_total"] == 11.5
    assert store.operations == 4
    assert store.get_week_public_bundle("w1", ttl_seconds=0.01, fresh=True)["pool"][0]["score_total"] == 22.0
    assert store.operations == 8


def test_explicit_fresh_read_retries_if_a_write_occurs_mid_read():
    store = ProbeStore()
    store.block_table = "lineups"
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(store.get_week_public_bundle, "w1", fresh=True)
        assert store.block_started.wait(10)
        store.tables["lineups"][0]["confirmed_at"] = "new-confirmation"
        store.clear_week_cache("w1")
        store.unblock.set()
        assert future.result(timeout=10)["lineups"][0]["confirmed_at"] == "new-confirmation"
    assert store.operations == 8
    assert ("gate4_bundle", "w1") not in store._public_cache


def test_confirmed_week_state_update_invalidates_current_week_alias():
    store = ProbeStore()
    assert store.get_real_week()["data_status"] == "WAITING"
    assert store.get_real_week()["data_status"] == "WAITING"
    store.update_week_data_state("w1", data_status="LIVE")
    assert store.get_real_week()["data_status"] == "LIVE"
    assert store.operations == 3  # original read, successful update, fresh read


def test_inflight_current_week_lookup_cannot_repopulate_old_alias():
    store = ProbeStore()
    store.block_table = "weeks"
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(store.get_real_week)
        assert store.block_started.wait(10)
        store.tables["weeks"][0]["data_status"] = "FINAL"
        store._invalidate_real_week_alias()
        store.unblock.set()
        assert future.result(timeout=10)["data_status"] == "FINAL"
    assert store.get_real_week()["data_status"] == "FINAL"
    assert store.operations == 2


class FreshConsumerStore:
    def __init__(self):
        self.calls = []
        self.scores = []

    def get_week_public_bundle(self, week_id, *, ttl_seconds=8.0, fresh=False):
        self.calls.append((week_id, fresh))
        return {"lineups": [], "picks": [], "players": [], "pool": [], "games": []}

    def get_registered_players(self):
        return []

    def get_weekly_results(self, **kwargs):
        return []

    def get_player_week_stats(self, *args):
        return []

    def upsert_weekly_results(self, rows):
        self.scores = rows

    def update_week_data_state(self, *args, **kwargs):
        return None


def test_clock_and_archival_are_explicitly_fresh_without_changing_outputs():
    store = FreshConsumerStore()
    week = {"id": "w1", "season": 2026, "nfl_week": 4, "data_status": "LIVE"}
    clock = build_clock_snapshot(store, week, now=datetime(2026, 10, 25, 18, tzinfo=UTC))
    archived = archive_week_results(store, week)
    assert store.calls == [("w1", True), ("w1", True)]
    assert clock["week_id"] == "w1" and clock["weekly_rich"] == []
    assert archived["rows"] == [] and archived["champions"] == []


def test_apply_pool_scores_rereads_commissioner_override_after_provider_wait():
    class ScoreStore(SupabaseStore):
        def __init__(self):
            self._public_cache = {}
            self.pool = [{"id": "q1", "manual_score_override": None}]
            self.saved = []

        def get_full_week_pool(self, week_id):
            return deepcopy(self.pool)

        def _table(self, name):
            assert name == "player_pool"

            def upsert(payload, **kwargs):
                self.saved = deepcopy(payload)
                return SimpleNamespace(execute=lambda: SimpleNamespace(data=deepcopy(payload)))
            return SimpleNamespace(upsert=upsert)

        def update_week_data_state(self, *args, **kwargs):
            return None

    store = ScoreStore()
    fetched = Event()
    continue_scoring = Event()

    def delayed_provider():
        fetched.set()
        assert continue_scoring.wait(10)
        return store.apply_pool_scores({"id": "w1"}, [{"pool_player_id": "q1", "points": 12.0}], score_status="LIVE")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(delayed_provider)
        assert fetched.wait(10)
        store.pool[0]["manual_score_override"] = 35.5
        continue_scoring.set()
        future.result(timeout=10)
    assert store.saved[0]["score_total"] == 35.5
