"""Regression checks for the Friday pregame Pulse location.

Runs the actual ``_open_home`` function with a small Streamlit stand-in so
placement and eligibility are tested without requiring a live Supabase or
Streamlit session.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def render_order(*, chosen=5, needs=None, unavailable=None, demo=False):
    source = ast.parse((ROOT / "weekly_ui.py").read_text(encoding="utf-8"))
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "_open_home")
    code = compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), "weekly_ui.py", "exec")
    events = []
    needs = list(needs or [])
    unavailable = list(unavailable or [])
    st = SimpleNamespace(
        session_state={},
        success=lambda message: events.append("success"),
        markdown=lambda message, **kwargs: events.append("lineup-heading" if "YOUR FIVE ARE READY" in message else "lineup-content"),
        button=lambda label, **kwargs: (events.append("edit-button" if label == "EDIT LINEUP" else "build-button"), False)[1],
    )
    symbols = {
        "st": st,
        "_load_lineup": lambda *args: (None, ["picks"], [], {}),
        "lineup_progress": lambda picks: (chosen, 5),
        "required_backup_positions": lambda *args: needs,
        "unavailable_starter_positions": lambda *args: unavailable,
        "_render_live_prelock_status": lambda *args: events.append("sunday-status"),
        "render_pregame_pulse": lambda *args: events.append("pulse"),
        "_summary_rows": lambda *args: "<div>Five picks</div>",
        "_render_pool_change_disclaimer": lambda: events.append("disclaimer"),
        "first_incomplete_position": lambda *args: "QB",
        "POSITIONS": ["QB", "RB", "WR", "TE", "K"],
    }
    exec(code, symbols)
    symbols["_open_home"](object(), {"id": "week", "is_demo": demo}, {"id": "player"}, [])
    return events


def test_pulse_directly_after_sunday_status_before_five_player_list():
    events = render_order()
    assert events[:3] == ["sunday-status", "pulse", "lineup-heading"]
    assert events.count("pulse") == 1
    assert events.index("pulse") < events.index("disclaimer") < events.index("edit-button")


def test_pulse_not_shown_for_unfinished_or_injury_affected_lineups():
    for options in ({"chosen": 4}, {"needs": ["WR"]}, {"unavailable": ["QB"]}):
        events = render_order(**options)
        assert events[0] == "sunday-status"
        assert "pulse" not in events
        assert "build-button" in events


def test_demo_week_has_no_pulse():
    events = render_order(demo=True)
    assert "pulse" not in events
    assert "sunday-status" not in events
    assert "lineup-heading" in events


def test_warm_deploy_has_fresh_version_and_ui_reload_marker():
    weekly = (ROOT / "weekly_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    config = (ROOT / "config.py").read_text(encoding="utf-8")
    assert 'WEEKLY_UI_SCHEMA_VERSION = 14' in weekly
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 14' in app
    assert 'APP_BUILD_VERSION = "1.0.8-hotfix8.1"' in config
    assert 'getattr(_config, "APP_BUILD_VERSION", "") != "1.0.8-hotfix8.1"' in app
