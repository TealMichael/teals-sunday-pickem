from pathlib import Path


def test_commissioner_routes_preseason_replay_to_production_worker():
    text = Path("gate5_ui.py").read_text()
    assert 'Open Gate 3.5 Replay Runner' in text
    assert 'Refresh Gate 3.5 Result' in text
    assert 'last_successful_run("preseason_replay")' in text
    assert 'real-box-score result' in text


def test_worker_exposes_preseason_replay_mode():
    worker = Path("scripts/nfl_refresh.py").read_text()
    workflow = Path(".github/workflows/nfl-refresh.yml").read_text()
    assert 'preseason_replay' in worker
    assert 'run_preseason_replay(store)' in worker
    assert 'preseason_replay' in workflow


def test_release_contains_preseason_replay_module():
    assert Path("preseason_replay.py").exists()


def test_espn_scoreboard_accepts_preseason_season_type():
    text = Path("nfl_sources.py").read_text()
    assert 'season_type: int | None = None' in text
    assert 'requested_season_type' in text
    assert '"seasontype": requested_season_type' in text


def test_espn_parser_keeps_player_position_for_replay_mapping():
    text = Path("nfl_sources.py").read_text()
    assert '"position": position or None' in text
    assert 'if position == "PK"' in text
