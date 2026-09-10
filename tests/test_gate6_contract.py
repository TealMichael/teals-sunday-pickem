from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_gate6_files_and_version_present():
    assert (ROOT / "gate6.py").exists()
    assert (ROOT / "gate6_ui.py").exists()
    assert 'APP_VERSION = "1.0.7"' in (ROOT / "config.py").read_text()


def test_commissioner_has_launch_readiness_destination():
    text = (ROOT / "gate5_ui.py").read_text()
    assert 'commissioner_tools = ["Week", "Players", "Corrections", "Clock", "Diagnostics"]' in text
    assert "render_launch_readiness" in text
    assert "Commissioner • Gate 6" not in text
    assert "Launch readiness & full-week checks" in text


def test_player_runtime_errors_are_friendly_not_raw_tracebacks():
    text = (ROOT / "app.py").read_text()
    assert "_friendly_runtime_error" in text
    assert "Your saved lineup and scores are safe" in text
    assert "ui_error" in text
    assert "error_type" in text


def test_future_week_open_copy_is_dynamic():
    text = (ROOT / "weekly_ui.py").read_text()
    assert 'f"### {label} opens Tuesday"' in text
    assert 'st.markdown("### Week 1 opens Tuesday")' not in text


def test_profile_has_optional_home_screen_instructions():
    text = (ROOT / "gate4_ui.py").read_text()
    assert 'with st.expander("Add to Home Screen")' in text
    assert "Notifications are not required for Week 1" in text


def test_nfl_worker_has_heartbeat_and_extended_snf_buffer_schedule():
    sync_text = (ROOT / "nfl_sync.py").read_text()
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text()
    assert '"auto_cycle"' in sync_text
    assert 'provider="github-actions"' in sync_text
    assert 'cron: "7,22,37,52 11-23 * * 0"' in workflow
    assert 'cron: "7,22,37,52 0-1 * * 1"' in workflow
    assert 'cron: "7 9-13 * * 1"' in workflow
    assert 'LIVE_SCORE_REFRESH_MINUTES = 15' in (ROOT / "config.py").read_text()
    assert "concurrency:" in workflow


def test_quality_gate_runs_tests_compile_and_release_guard():
    workflow = (ROOT / ".github/workflows/quality-gate.yml").read_text()
    assert "pytest -q" in workflow
    assert "python -m compileall -q ." in workflow
    assert "python release_guard.py" in workflow


def test_results_reads_are_cached_and_invalidated():
    text = (ROOT / "store.py").read_text()
    assert '("weekly_results", season' in text
    assert 'self._cache_drop_prefix("weekly_results")' in text
    assert '("season_champions", int(season)' in text
    assert 'self._cache_drop_prefix("season_champions")' in text
