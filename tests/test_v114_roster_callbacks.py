"""Real Streamlit roster clicks, current-account privacy, and warm deployment."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

BOARD = [
    {'player_id':f'p{i}','lineup_id':f'l{i}','nickname':f'Person {i}','emoji':'🏈','rank':i+1,'score':10,
     'roster':[
         {'position':'QB','player':{'player_name':f'Starter {i}'},'starter':{'player_name':f'Starter {i}'},
          'backup':{'player_name':f'Private backup {i}'},'points':10},
         {'position':'RB','missing':True}
     ]} for i in range(3)
]

def app_for(*,detail=True):
    app=AppTest.from_string('''import streamlit as st
from gate4_ui import _leaderboard_rows
st.session_state.runs = st.session_state.get('runs',0) + 1
if st.session_state.authenticated:
    _leaderboard_rows(st.session_state.board, st.session_state.current_player, detail=st.session_state.detail)
else:
    st.write('Sign in')
''')
    for k,v in dict(board=deepcopy(BOARD),current_player='p0',detail=detail,authenticated=True).items():
        app.session_state[k]=v
    app.run(); assert not app.exception
    return app

def text(app): return '\n'.join(m.value for m in app.markdown)

def click(app,index):
    before=app.session_state['runs']
    app.button[index].click().run()
    assert not app.exception and app.session_state['runs']==before+1


def test_open_switch_and_close_keep_buttons_and_inline_detail_in_one_run():
    app=app_for(); labels=[b.label for b in app.button]
    click(app,0)
    assert app.session_state['gate4_detail_player_id']=='p0'
    assert 'Private backup 0' in text(app) and 'Missing position' in text(app)
    assert [b.label for b in app.button]==labels
    click(app,1)
    assert app.session_state['gate4_detail_player_id']=='p1'
    assert 'Starter 1' in text(app) and 'Private backup' not in text(app)
    click(app,2)
    assert app.session_state['gate4_detail_player_id']=='p2'
    assert 'Starter 2' in text(app) and 'Starter 1' not in text(app)
    click(app,2)
    assert 'gate4_detail_player_id' not in app.session_state.filtered_state
    assert 'Starter 2' not in text(app)
    assert app.session_state['board']==BOARD


def test_detail_false_click_never_changes_selection_or_renders_roster():
    app=app_for(detail=False)
    app.session_state['gate4_detail_player_id']='p2'
    click(app,0)
    assert app.session_state['gate4_detail_player_id']=='p2'
    assert 'Starter' not in text(app) and 'Private backup' not in text(app)

@pytest.mark.parametrize('change',['account','logout','removed_row'])
def test_callback_uses_current_render_privacy_after_session_change(change):
    app=app_for(); app.button[0].click()
    if change=='account': app.session_state['current_player']='p1'
    elif change=='logout': app.session_state['authenticated']=False
    else: app.session_state['board']=deepcopy(BOARD[1:])
    app.run()
    assert not app.exception
    assert 'Private backup 0' not in text(app)
    if change!='account': assert 'Starter 0' not in text(app)


def test_activated_backup_stays_public_and_inactive_backup_stays_private():
    app=app_for()
    row=app.session_state['board'][1]['roster'][0]
    row.update(emergency_activated=True,player={'player_name':'Activated backup'})
    click(app,1)
    assert 'Activated backup' in text(app) and 'Emergency activated for Starter 1' in text(app)
    assert 'Private backup' not in text(app)


def test_v113_warm_worker_rebinds_store_gate4_and_weekly_consumers():
    root=Path(__file__).resolve().parents[1]
    script='''import socket
socket.socket.connect = lambda *a,**k: (_ for _ in ()).throw(AssertionError('No network'))
import config, store, gate4_ui, weekly_ui
config.APP_BUILD_VERSION='1.0.13-performance4'
store.STORE_SCHEMA_VERSION=8
gate4_ui.GATE4_UI_SCHEMA_VERSION=12
old_store=store.SupabaseStore
old_live=gate4_ui.render_live_sunday
old_weekly=weekly_ui.render_player_game
from pathlib import Path
scope={'__name__':'warm_v114'}
exec(compile(Path('app.py').read_text().split('\\npage_config()',1)[0],'app.py','exec'),scope)
assert scope['APP_BUILD_VERSION']=='1.0.14-performance5'
assert store.STORE_SCHEMA_VERSION==9 and gate4_ui.GATE4_UI_SCHEMA_VERSION==13
assert store.SupabaseStore is not old_store and scope['SupabaseStore'] is store.SupabaseStore
assert gate4_ui.render_live_sunday is not old_live
assert weekly_ui.render_player_game is not old_weekly
assert weekly_ui.render_live_sunday is gate4_ui.render_live_sunday
assert scope['render_player_game'] is weekly_ui.render_player_game
'''
    result=subprocess.run([sys.executable,'-c',script],cwd=root,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
