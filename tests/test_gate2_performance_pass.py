from pathlib import Path


def _store():
    return Path("store.py").read_text()


def _ui():
    return Path("weekly_ui.py").read_text()


def test_public_week_and_pool_reads_have_short_ttl_cache():
    text = _store()
    assert 'def _cache_get(self, key: tuple)' in text
    assert '("real_week",)' in text
    assert '("demo_week",)' in text
    assert '("week_pool", str(week_id), bool(visible_only))' in text
    assert 'self._cache_set(cache_key, rows, 20)' in text


def test_player_ui_fetches_only_visible_top_five_pool_rows():
    text = _store()
    assert 'def get_week_pool(self, week_id: str, *, visible_only: bool = True)' in text
    assert 'query = query.eq("is_visible", True)' in text
    ui = _ui()
    assert 'visible_only=True' in ui


def test_lineup_and_picks_are_loaded_in_one_postgrest_request():
    text = _store()
    assert 'def get_lineup_state' in text
    assert 'lineup_picks(id,lineup_id,position,pool_player_id,emergency_pool_player_id,updated_at)' in text
    ui = _ui()
    assert 'store.get_lineup_state' in ui
    assert 'store.get_lineup_picks' not in ui


def test_pick_write_reuses_already_loaded_week_pool_and_lineup():
    text = _store()
    assert 'known_week: dict[str, Any] | None = None' in text
    assert 'known_pool: list[dict[str, Any]] | None = None' in text
    assert 'lineup_id: str | None = None' in text
    ui = _ui()
    assert 'known_week=week' in ui
    assert 'known_pool=pool' in ui
    assert 'lineup_id=str(lineup["id"]) if lineup else None' in ui


def test_immediate_post_write_rerun_uses_short_local_lineup_snapshot():
    text = _ui()
    assert 'LINEUP_SNAPSHOT_TTL_SECONDS = 12.0' in text
    assert 'def _stash_lineup_snapshot' in text
    assert '_merge_saved_pick(picks, saved)' in text
    assert 'age <= float(snapshot_ttl_seconds)' in text
