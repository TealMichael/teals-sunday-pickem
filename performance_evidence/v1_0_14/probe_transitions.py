"""Whole-app phase/account/week changes after a roster click, before rendering."""
from pathlib import Path
fixture_source=Path(__file__).with_name('probe_live_bundle.py').read_text().split("measure('live_cold_15_players')",1)[0]
exec(compile(fixture_source,str(Path(__file__).with_name('probe_live_bundle.py')),'exec'),globals())
measure('initial_live')

def phase_change():
    next(b for b in app.button if '← YOU' in b.label).click()
    fs.update_week_data_state(WEEK_ID,data_status='PROVISIONAL')
measure('tap_then_provisional',phase_change)

def final_change():
    next(b for b in app.button if '← YOU' in b.label).click()
    fs.update_week_data_state(WEEK_ID,data_status='FINAL',finalized_at=fixed_now.isoformat())
measure('tap_then_final',final_change)

def account_change():
    next(b for b in app.button if '← YOU' in b.label).click()
    app.session_state['player']=deepcopy(next(p for p in fs.tables['players'] if p['id']!=PLAYER_ID))
measure('tap_then_account_change',account_change)

app.session_state['player']=deepcopy(fs.player)
if app.button_group: app.button_group[0].set_value('🏈 Sunday')
measure('restore_owner_live')

def upcoming_week():
    next(b for b in app.button if '← YOU' in b.label).click()
    fs.week.update(id='next-week',nfl_week=9,label='Week 9',opens_at='2026-10-27T16:00:00+00:00',locks_at='2026-11-01T18:00:00+00:00',data_status='WAITING',finalized_at=None)
    fs.clear_week_cache();fs._invalidate_real_week_alias()
measure('tap_then_next_week',upcoming_week)
assert not blocked_attempts
output.write_text(json.dumps({'results':results,'blocked_network_attempts':len(blocked_attempts)},indent=2,ensure_ascii=False)+'\n')
