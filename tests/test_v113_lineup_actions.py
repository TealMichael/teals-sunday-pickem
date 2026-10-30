"""Real Streamlit callbacks + original store methods, with no external I/O."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import importlib

import pytest
import weekly_ui
from lineup_ui_fixture import Clock, LineupStore, app_for, button, card, click_once

@pytest.fixture(autouse=True)
def clock(monkeypatch):
    Clock.at = datetime(2026,10,25,15,0,tzinfo=timezone.utc)
    for name in ['store','weekly','weekly_ui','gate4_ui','gate4','pulse_ui','automation_recovery',
                 'player_season_stats','lineup_reveal','sunday_drama','pickem_pulse']:
        monkeypatch.setattr(importlib.import_module(name), 'datetime', Clock, raising=False)

def test_all_five_save_once_then_confirm_and_edit_in_one_run():
    store = LineupStore()
    app = app_for(store)
    click_once(app, button(app, 'Build My Five'))
    for pos in ['QB','RB','WR','TE','K']:
        store.reset_counts()
        click_once(app, card(app, pos))
        assert store.attempted_writes == 0
        target = next(b for b in app.button if b.label.startswith('Next:') or b.label == 'Review My Five →')
        click_once(app, target)
        assert store.operations.count('lineup_picks.upsert') == 1
        assert store.pick(pos)['pool_player_id'] == 'pool-0-'+pos
        assert store.operations.count('player_pool.select') == 1  # post-save invalidation retained
    assert len(store.tables['lineup_picks']) == 5
    store.reset_counts()
    click_once(app, button(app, 'SAVE MY LINEUP'))
    assert store.operations.count('lineups.update') == 1
    assert store.operations.count('lineups.select') == 1  # fresh status after confirmation
    assert any('Lineup saved.' in m.value for m in app.success)
    store.reset_counts()
    click_once(app, button(app, 'EDIT LINEUP'))
    assert store.operations.count('lineups.select') == 1  # home-origin fresh read retained
    assert app.session_state['builder_mode'] == 'review'

@pytest.mark.parametrize('return_mode', [None, 'review', 'home'])
def test_back_discards_staged_selection_without_a_write(return_mode):
    store = LineupStore(complete=True)
    app = app_for(store, mode='pick', position='WR', return_mode=return_mode)
    click_once(app, card(app, 'WR', 1))
    store.reset_counts()
    click_once(app, next(b for b in app.button if b.label.startswith('←')))
    assert store.attempted_writes == 0
    assert store.pick('WR')['pool_player_id'] == 'pool-0-WR'
    assert not app.session_state.filtered_state.get('builder_pending::starter::week::'+store.player['id']+'::WR')
    assert app.session_state['builder_mode'] == (return_mode or 'pick')
    assert app.session_state['builder_position'] == (None if return_mode else 'RB')

@pytest.mark.parametrize('return_mode', [None, 'review', 'home'])
def test_next_unchanged_skips_write_and_returns_correctly(return_mode):
    store = LineupStore(complete=True)
    app = app_for(store, mode='pick', position='WR', return_mode=return_mode)
    store.reset_counts()
    click_once(app, next(b for b in app.button if b.label.startswith(('Next:', 'Return to'))))
    assert store.attempted_writes == 0
    assert app.session_state['builder_mode'] == (return_mode or 'pick')
    assert app.session_state['builder_position'] == (None if return_mode else 'TE')

def test_questionable_and_backup_save_together_after_change_starter():
    store = LineupStore(complete=True)
    store.pool_row('pool-1-QB')['availability_status'] = 'QUESTIONABLE'
    app = app_for(store, mode='pick', position='QB', return_mode='review')
    click_once(app, card(app, 'QB', 1))
    click_once(app, button(app, 'Choose Emergency Backup →'))
    click_once(app, card(app, 'QB', 2))
    click_once(app, button(app, 'Change starter'))
    assert store.attempted_writes == 0
    assert store.pick('QB')['pool_player_id'] == 'pool-0-QB'
    click_once(app, button(app, 'Choose Emergency Backup →'))
    click_once(app, card(app, 'QB', 2))
    store.reset_counts()
    click_once(app, button(app, 'Return to Review →'))
    assert store.operations.count('lineup_picks.upsert') == 1
    assert store.pick('QB')['pool_player_id'] == 'pool-1-QB'
    assert store.pick('QB')['emergency_pool_player_id'] == 'pool-2-QB'

@pytest.mark.parametrize('confirm', [False, True])
def test_save_error_retains_original_screen_and_retry_is_explicit(confirm):
    store = LineupStore(complete=True)
    app = app_for(store, mode='review' if confirm else 'pick', position=None if confirm else 'QB')
    if not confirm:
        click_once(app, card(app,'QB',1))
    label = 'SAVE MY LINEUP' if confirm else 'Next: RB →'
    old_picks = deepcopy(store.tables['lineup_picks'])
    store.reject_write = 'Synthetic failed save'
    store.reset_counts()
    click_once(app, button(app,label))
    assert store.attempted_writes == 1
    assert store.tables['lineup_picks'] == old_picks
    assert [e.value for e in app.error] == ['Synthetic failed save']
    assert app.session_state['builder_mode'] == ('review' if confirm else 'pick')
    app.run()  # no silent retry on the next unrelated render
    assert store.attempted_writes == 1
    click_once(app, button(app,label))
    assert store.attempted_writes == 2
    assert not app.error
    if not confirm:
        assert store.pick('QB')['pool_player_id'] == 'pool-1-QB'

@pytest.mark.parametrize('change', ['account','same_account_login','token','mode','position','return_mode','week','tab','pool','lock'])
def test_change_between_click_and_render_cannot_replay_a_save(change):
    store = LineupStore(complete=True)
    app = app_for(store, mode='pick', position='QB')
    click_once(app, card(app,'QB',1))
    button(app,'Next: RB →').click()
    if change in {'account','same_account_login'}:
        player = dict(store.player)
        if change == 'account': player['id'] = '00000000-0000-4000-8000-000000000002'
        app.session_state['player'] = player
    elif change == 'token': app.session_state['active_device_token'] = 'different-session'
    elif change == 'mode': app.session_state['builder_mode'] = 'review'
    elif change == 'position': app.session_state['builder_position'] = 'WR'
    elif change == 'return_mode': app.session_state['builder_return_mode'] = 'home'
    elif change == 'week':
        store.week['id'] = 'another-week'
        for row in store.tables['player_pool']: row['week_id'] = 'another-week'
        store.clear_week_cache()
    elif change == 'tab': app.button_group[0].set_value('🕘 History')
    elif change == 'pool':
        store.pool_row('pool-0-K')['is_visible'] = False
        store.clear_week_cache()
    elif change == 'lock':
        Clock.at = datetime(2026,10,25,17,0,tzinfo=timezone.utc)
        store.week['data_status'] = 'FINAL'
        store.clear_week_cache()
    store.reset_counts()
    app.run()
    assert not app.exception
    assert store.attempted_writes == 0
    assert store.pick('QB')['pool_player_id'] == 'pool-0-QB'
    assert 'lineup_action' not in app.session_state.filtered_state
    if change == 'tab': app.button_group[0].set_value('🏈 Sunday')
    app.run()
    assert store.attempted_writes == 0

@pytest.mark.parametrize('status', ['OUT', 'ineligible', 'hidden', 'QUESTIONABLE'])
def test_fresh_pool_change_before_next_keeps_existing_safety_behavior(status):
    store = LineupStore(complete=True)
    app = app_for(store, mode='pick', position='QB')
    click_once(app, card(app,'QB',1))
    button(app,'Next: RB →').click()
    row = store.pool_row('pool-1-QB')
    if status == 'hidden':
        row['is_visible'] = False
        store.pool_row('pool-5-QB')['is_visible'] = True
    elif status == 'ineligible': row['schedule_eligible'] = False
    else: row['availability_status'] = status
    store.clear_week_cache()
    store.reset_counts()
    app.run()
    assert not app.exception
    assert store.attempted_writes == 0
    assert store.pick('QB')['pool_player_id'] == 'pool-0-QB'
    assert app.session_state['builder_position'] == 'QB'
    if status == 'QUESTIONABLE':
        # The old Next button's label changed; it cannot silently save or enter
        # backup mode. A new deliberate tap chooses the backup screen.
        assert not app.error
        click_once(app, button(app,'Choose Emergency Backup →'))

def test_hidden_out_starter_is_preserved_until_replaced():
    store = LineupStore(complete=True)
    store.pool_row('pool-0-QB').update(is_visible=False, availability_status='OUT')
    store.pool_row('pool-5-QB')['is_visible'] = True
    app = app_for(store)
    click_once(app, button(app,'Replace Unavailable Player'))
    assert store.pick('QB')['pool_player_id'] == 'pool-0-QB'
    assert any('Your saved QB pick' in w.value for w in app.warning)
    assert not any('Synthetic 0 QB' in b.label for b in app.button)
    click_once(app, card(app,'QB',1))
    click_once(app, button(app,'Return to Lineup →'))
    assert store.pick('QB')['pool_player_id'] == 'pool-1-QB'

def test_repeated_callback_from_old_render_is_discarded(monkeypatch):
    class State(dict):
        __getattr__ = dict.__getitem__
        __setattr__ = dict.__setitem__
    player = {'id':'synthetic'}
    state = State(player=player, builder_mode='pick', builder_position='QB', lineup_render_generation=1)
    monkeypatch.setattr(weekly_ui, 'st', SimpleNamespace(session_state=state))
    request = weekly_ui._lineup_action('next','Next: RB →',{'id':'week'},player)['args'][0]
    weekly_ui._queue_lineup_action(request)
    weekly_ui._queue_lineup_action(request)
    assert weekly_ui._take_lineup_action(player) == request
    weekly_ui._queue_lineup_action(request)
    assert weekly_ui._take_lineup_action(player) is None

def test_home_action_keeps_fresh_status_read_after_recovery(monkeypatch):
    store = LineupStore(complete=True)
    app = app_for(store)
    original = weekly_ui.maybe_recover_critical_automation
    calls = []
    def recovery(s,w):
        calls.append(w['id'])
        # The inner home status recovery changes the lineup between reads.
        if len(calls) == 2:
            s.tables['lineup_picks'] = [p for p in s.tables['lineup_picks'] if p['position'] != 'QB']
        return original(s,w)
    monkeypatch.setattr(weekly_ui,'maybe_recover_critical_automation',recovery)
    store.reset_counts()
    button(app,'EDIT LINEUP').click().run()
    assert not app.exception
    assert store.attempted_writes == 0
    assert app.session_state['builder_mode'] == 'home'
    assert any(b.label == 'Continue Building' for b in app.button)
    assert store.operations.count('lineups.select') >= 1

def test_isolated_demo_navigation_keeps_real_week_untouched():
    store = LineupStore()
    app = app_for(store,demo=True)
    click_once(app,button(app,'Build My Five'))
    click_once(app,card(app,'QB'))
    click_once(app,button(app,'Next: RB →'))
    assert store.pick('QB')['pool_player_id'] == 'pool-0-QB'
    assert all(l['week_id'] == store.week['id'] for l in store.tables['lineups'])


@pytest.mark.parametrize('condition,label,expected_mode', [
    ('missing','Continue Building','pick'),
    ('out','Replace unavailable player','pick'),
    ('questionable','Fix injury backup','backup'),
])
def test_review_repair_actions_keep_the_correct_destination(condition,label,expected_mode):
    store = LineupStore(complete=True)
    if condition == 'missing':
        store.tables['lineup_picks'] = [p for p in store.tables['lineup_picks'] if p['position'] != 'QB']
    else:
        store.pool_row('pool-0-QB')['availability_status'] = 'OUT' if condition == 'out' else 'QUESTIONABLE'
    app = app_for(store,mode='review')
    store.reset_counts()
    click_once(app,button(app,label))
    assert store.attempted_writes == 0
    assert app.session_state['builder_position'] == 'QB'
    assert app.session_state['builder_mode'] == expected_mode


def test_destination_reloads_pool_after_successful_save():
    store = LineupStore(complete=True)
    app = app_for(store,mode='pick',position='QB')
    click_once(app,card(app,'QB',1))
    def replacement():
        store.pool_row('pool-0-RB').update(is_visible=False, availability_status='OUT')
        store.pool_row('pool-5-RB')['is_visible'] = True
    store.after_write = replacement
    store.reset_counts()
    click_once(app,button(app,'Next: RB →'))
    assert store.operations.count('lineup_picks.upsert') == 1
    assert store.operations.count('player_pool.select') >= 1
    assert not any('Synthetic 0 RB' in b.label for b in app.button)
    assert any('Synthetic 5 RB' in b.label for b in app.button)
    assert any('Your saved RB pick' in w.value for w in app.warning)


def test_backup_becoming_out_before_next_is_not_saved():
    store = LineupStore(complete=True)
    store.pool_row('pool-0-QB')['availability_status'] = 'QUESTIONABLE'
    app = app_for(store,mode='backup',position='QB',return_mode='review')
    click_once(app,card(app,'QB',1))
    button(app,'Return to Review →').click()
    store.pool_row('pool-1-QB')['availability_status'] = 'OUT'
    store.clear_week_cache()
    store.reset_counts()
    app.run()
    assert not app.exception
    assert store.attempted_writes == 0
    assert button(app,'Return to Review →').disabled
    assert not store.pick('QB')['emergency_pool_player_id']
