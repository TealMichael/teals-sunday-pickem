from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIVE_MINUTE_CRON = '2,7,12,17,22,27,32,37,42,47,52,57'


def test_hotfix78_build_and_shared_live_cadence():
    config = (ROOT / 'config.py').read_text('utf-8')
    workflow = (ROOT / '.github/workflows/nfl-refresh.yml').read_text('utf-8')
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.8"' in config
    assert '\nLIVE_SCORE_REFRESH_MINUTES = 5\n' in config
    assert f'- cron: "{FIVE_MINUTE_CRON} 11-23 * * 0"' in workflow
    assert f'- cron: "{FIVE_MINUTE_CRON} 0-1 * * 1"' in workflow


def test_hotfix78_live_app_rereads_every_30_seconds():
    gate4_ui = (ROOT / 'gate4_ui.py').read_text('utf-8')
    assert 'GATE4_UI_SCHEMA_VERSION = 5' in gate4_ui
    assert '@st.fragment(run_every="30s")\ndef render_live_sunday' in gate4_ui


def test_hotfix78_recovery_and_warm_reload_are_hardened():
    app = (ROOT / 'app.py').read_text('utf-8')
    sync = (ROOT / 'nfl_sync.py').read_text('utf-8')
    recovery = (ROOT / 'automation_recovery.py').read_text('utf-8')
    assert 'NFL_SYNC_SCHEMA_VERSION = 3' in sync
    assert 'AUTOMATION_RECOVERY_SCHEMA_VERSION = 4' in recovery
    assert 'SUNDAY_CRITICAL_INJURY_REFRESH_MINUTES = 15' in recovery
    assert 'getattr(_nfl_sync, "NFL_SYNC_SCHEMA_VERSION", 0) < 3' in app
    assert 'getattr(_automation_recovery, "AUTOMATION_RECOVERY_SCHEMA_VERSION", 0) < 4' in app
    assert 'getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 5' in app


def test_hotfix78_keeps_clock_poll_unchanged():
    awtrix = (ROOT / 'awtrix/PickemSunday.ax').read_text('utf-8')
    assert '@config  poll number "Sunday poll" default=15' in awtrix
    assert 'self.ticks = 15' in awtrix
