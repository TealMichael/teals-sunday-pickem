"""Exercise actual Streamlit fragments and commissioner rendering offline."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from streamlit.testing.v1 import AppTest

import gate5
import gate5_ui
import weekly_ui


class RenderStore:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.week = {'id': 'week', 'season': 2026, 'nfl_week': 7,
                     'opens_at': (now - timedelta(days=1)).isoformat(),
                     'locks_at': (now + timedelta(days=1)).isoformat(),
                     'published_at': now.isoformat(), 'last_data_refresh_at': now.isoformat(),
                     'data_status': 'POOL_READY', 'is_demo': False}
        self.player = {'id': 'player'}
        self.pool = [{'id': pos, 'position': pos, 'is_visible': True, 'slot_rank': 1,
                      'player_name': pos + ' fixture', 'team_abbr': 'TST',
                      'availability_status': 'HEALTHY', 'schedule_eligible': True,
                      'kickoff_at': self.week['locks_at'], 'score_total': 10}
                     for pos in ['QB', 'RB', 'WR', 'TE', 'K']]
        self.pool.append({**self.pool[0], 'id': 'reserve', 'player_name': 'Reserve fixture',
                          'is_visible': False, 'slot_rank': 6})
        self.picks = [{'position': row['position'], 'pool_player_id': row['id']}
                      for row in self.pool if row['is_visible']]
        self.lineup_reads = self.pool_reads = self.usage_reads = 0

    def get_week(self, week_id):
        return deepcopy(self.week)

    def get_week_pool(self, week_id, *, visible_only=True):
        return deepcopy([r for r in self.pool if not visible_only or r['is_visible']])

    def get_lineup_state(self, week_id, player_id):
        self.lineup_reads += 1
        return {'id': 'lineup'}, deepcopy(self.picks)

    def get_pool_rows_by_ids(self, week_id, ids):
        return deepcopy([r for r in self.pool if r['id'] in ids])

    def get_full_week_pool(self, week_id):
        self.pool_reads += 1
        return deepcopy(self.pool)

    def get_pool_usage(self, week_id, pool_player_id):
        self.usage_reads += 1
        return {'affected_lineups': 0, 'affected_nicknames': []}

    def get_weekly_results(self, **kwargs):
        return []


def app_for(store, body):
    script = '''import streamlit as st
import weekly_ui
import gate5_ui
s = st.session_state.fixture_store
''' + body
    app = AppTest.from_string(script, default_timeout=10)
    app.session_state['fixture_store'] = store
    app.run()
    assert not app.exception
    return app


def test_pregame_home_shares_one_fresh_lineup_read_and_retains_ready_content(monkeypatch):
    monkeypatch.setattr(weekly_ui, 'maybe_recover_critical_automation', lambda s, w: (w, None))
    store = RenderStore()
    app = app_for(store, 'weekly_ui._open_home(s, s.week, s.player, s.get_week_pool("week"))')
    assert store.lineup_reads == 1
    assert any('YOUR FIVE ARE READY' in m.value for m in app.markdown)
    assert [b.label for b in app.button] == ['EDIT LINEUP']
    app.run()
    assert not app.exception
    assert store.lineup_reads == 2  # Immediate rerun still forces status freshness.


def test_status_fragment_rereads_after_recovery_and_resolves_hidden_starter(monkeypatch):
    def recovery(store, week):
        if store.lineup_reads:
            store.picks[0]['pool_player_id'] = 'reserve'
        return week, None

    monkeypatch.setattr(weekly_ui, 'maybe_recover_critical_automation', recovery)
    store = RenderStore()
    app = app_for(store, 'st.session_state.result = weekly_ui._render_live_prelock_status(s, s.week, s.player)')
    app.run()
    assert not app.exception
    assert store.lineup_reads == 2
    result = app.session_state['result']
    assert result[1][0]['pool_player_id'] == 'reserve'
    assert result[3]['reserve']['player_name'] == 'Reserve fixture'


def test_status_lock_transition_reruns_before_lineup_read(monkeypatch):
    class RerunRequested(BaseException):
        pass

    store = RenderStore()
    store.week['locks_at'] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    monkeypatch.setattr(weekly_ui, 'maybe_recover_critical_automation', lambda s, w: (w, None))
    monkeypatch.setattr(weekly_ui.st, 'rerun', lambda: (_ for _ in ()).throw(RerunRequested()))
    with pytest.raises(RerunRequested):
        weekly_ui._render_live_prelock_status.__wrapped__(store, store.week, store.player)
    assert store.lineup_reads == 0


def test_corrections_reads_pool_once_and_preserves_controls():
    store = RenderStore()
    app = app_for(store, 'gate5_ui._render_corrections(s, s.week)')
    assert store.pool_reads == 1
    assert store.usage_reads == 1
    assert [b.label for b in app.button] == ['Replace Player', 'Apply Override', 'Clear Override']
    assert app.button[1].disabled and app.button[2].disabled
    app.run()
    assert not app.exception
    assert store.pool_reads == 2


def test_failed_pool_mutation_rereads_before_manual_score_controls(monkeypatch):
    store = RenderStore()

    def failed_mutation(*args, **kwargs):
        store.pool[0]['is_visible'] = False
        store.pool[-1]['is_visible'] = True
        raise RuntimeError('Synthetic partial mutation failure')

    monkeypatch.setattr(gate5_ui, 'replace_pool_player', failed_mutation)
    app = app_for(store, 'gate5_ui._render_corrections(s, s.week)')
    app.checkbox[0].check().run()
    before = store.pool_reads
    app.button[0].click().run()
    assert not app.exception
    assert store.pool_reads == before + 2
    score_options = next(x.options for x in app.selectbox if x.label == 'Player score')
    assert any('Reserve fixture' in x for x in score_options)
    assert not any('QB fixture' in x for x in score_options)


def test_preview_context_matches_fresh_query_and_does_not_change_action_validation():
    store = RenderStore()
    fresh = gate5.pool_override_preview(store, store.week, 'QB')
    reused = gate5.pool_override_preview(store, store.week, 'QB', pool_rows=deepcopy(store.pool))
    assert fresh == reused
    assert store.pool_reads == 1 and store.usage_reads == 2
    with pytest.raises(gate5.CommissionerError):
        gate5.pool_override_preview(store, store.week, 'QB', pool_rows=[])
    locked = {**store.week, 'locks_at': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
    with pytest.raises(gate5.CommissionerError):
        gate5.replace_pool_player(store, locked, outgoing_pool_id='QB', replacement_pool_id='reserve', reason='fixture')


def test_warm_deploy_reloads_changed_dependencies_before_binding_ui():
    # Use a separate process so reloading classes cannot affect other tests'
    # imported exception identities. Only the import/guard prefix is executed.
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    script = '''
import socket
def blocked(*args, **kwargs):
    raise AssertionError("No network in warm-deploy check")
socket.socket.connect = blocked
socket.create_connection = blocked
import config, store, player_season_stats, gate5, weekly_ui, gate5_ui
import nfl_sources, nfl_sync, automation_recovery, gate4_ui
config.APP_BUILD_VERSION = "1.0.9-commissioner-unified"
store.STORE_SCHEMA_VERSION = 6
player_season_stats.PLAYER_SEASON_STATS_LOGIC_VERSION = 0
gate5.GATE5_LOGIC_SCHEMA_VERSION = 0
weekly_ui.WEEKLY_UI_SCHEMA_VERSION = 15
gate5_ui.GATE5_UI_SCHEMA_VERSION = 10
nfl_sources.NFL_SOURCES_SCHEMA_VERSION = 2
nfl_sync.NFL_SYNC_SCHEMA_VERSION = 6
from pathlib import Path
prefix = Path("app.py").read_text().split("\\npage_config()", 1)[0]
scope = {"__name__": "warm_deploy_probe"}
exec(compile(prefix, "app.py", "exec"), scope)
assert scope["APP_BUILD_VERSION"] == "1.0.12-performance3"
assert scope["APP_VERSION"] == "1.0.12"
assert store.STORE_SCHEMA_VERSION == 8
assert weekly_ui.WEEKLY_UI_SCHEMA_VERSION == 16
assert gate5_ui.GATE5_UI_SCHEMA_VERSION == 11
assert nfl_sources.NFL_SOURCES_SCHEMA_VERSION == 3
assert nfl_sync.NFL_SYNC_SCHEMA_VERSION == 7
assert nfl_sync.ESPNProvider is nfl_sources.ESPNProvider
assert automation_recovery.refresh_live_player_stats is nfl_sync.refresh_live_player_stats
assert gate4_ui.maybe_refresh_active_live_lane is automation_recovery.maybe_refresh_active_live_lane
assert weekly_ui.load_or_prepare_snapshot is player_season_stats.load_or_prepare_snapshot
assert gate5_ui.pool_override_preview is gate5.pool_override_preview
assert scope["render_player_game"] is weekly_ui.render_player_game
assert scope["render_commissioner_dashboard"] is gate5_ui.render_commissioner_dashboard
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=root,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
