"""Hotfix 7.12: 1 PM lineup reveal stays read-only and locked-gated."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ast
from html import escape
from typing import Any
import lineup_reveal

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def _reveal_renderer(fake_st, phase="locked"):
    """Exercise the real UI function without importing unavailable Streamlit."""
    source = (ROOT / "gate4_ui.py").read_text()
    tree = ast.parse(source)
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "_render_lineup_reveal")
    namespace = {"st": fake_st, "week_phase": lambda week: phase,
                 "build_lineup_reveal": lineup_reveal.build_lineup_reveal,
                 "escape": escape, "Any": Any}
    exec(compile(ast.Module(body=[func], type_ignores=[]), "gate4_ui.py", "exec"), namespace)
    return namespace["_render_lineup_reveal"]


def sample_bundle():
    pool = [
        {"id": "q1", "player_name": "Josh Allen", "position": "QB"},
        {"id": "q2", "player_name": "Lamar Jackson", "position": "QB"},
        {"id": "r1", "player_name": "Saquon Barkley", "position": "RB"},
        {"id": "w1", "player_name": "Justin Jefferson", "position": "WR"},
        {"id": "t1", "player_name": "Travis Kelce", "position": "TE"},
        {"id": "k1", "player_name": "Brandon Aubrey", "position": "K"},
        {"id": "b-private", "player_name": "PRIVATE BACKUP", "position": "QB"},
    ]
    picks = []
    for lineup_id, qb in (("l1", "q1"), ("l2", "q1"), ("l3", "q2")):
        for pos, pid in zip(POSITIONS, (qb, "r1", "w1", "t1", "k1")):
            picks.append({"lineup_id": lineup_id, "position": pos,
                          "pool_player_id": pid, "emergency_pool_player_id": "b-private"})
    return {
        "pool": pool,
        "lineups": [{"id": f"l{i}", "player_id": f"p{i}", "confirmed_at": "yes"} for i in (1, 2, 3)]
                   + [{"id": "empty", "player_id": "p4"}],
        "players": [{"id": f"p{i}", "nickname": name} for i, name in
                    enumerate(("", "Mike", "Jenny", "Cassidy", "No picks")) if i],
        "picks": picks,
    }


def test_reveal_counts_popularity_and_only_identical_complete_starters():
    data = sample_bundle()
    original = deepcopy(data)
    result = lineup_reveal.build_lineup_reveal(data)
    assert result["lineup_count"] == result["complete_count"] == 3
    assert result["most_popular"]["player_name"] == "Saquon Barkley"
    assert result["most_popular"]["count"] == 3
    qb = result["positions"][0]
    assert qb["position"] == "QB" and qb["picks_count"] == 3
    assert [(r["player_name"], r["count"]) for r in qb["choices"]] == [
        ("Josh Allen", 2), ("Lamar Jackson", 1)
    ]
    assert qb["choices"][0]["owners"] == ["Jenny", "Mike"]
    assert result["solo_picks"] == [{"position": "QB", "player_name": "Lamar Jackson", "nickname": "Cassidy"}]
    assert result["same_brain"] == [["Jenny", "Mike"]]
    assert data == original  # no writes/mutations
    assert "PRIVATE BACKUP" not in str(result) and "b-private" not in str(result)


def test_missing_saved_pool_row_keeps_count_without_exposing_internal_id():
    data = sample_bundle()
    data["pool"] = [row for row in data["pool"] if row["id"] != "q2"]
    reveal = lineup_reveal.build_lineup_reveal(data)
    assert reveal["lineup_count"] == 3
    assert reveal["positions"][0]["choices"][1]["player_name"] == "Player unavailable"
    assert "q2" not in str(reveal)


def test_incomplete_picks_are_counted_but_do_not_create_false_same_brain():
    data = sample_bundle()
    data["picks"] = [p for p in data["picks"] if p["position"] != "K" or p["lineup_id"] == "l1"]
    data["picks"].append({"lineup_id": "orphan", "position": "QB", "pool_player_id": "q1"})
    reveal = lineup_reveal.build_lineup_reveal(data)
    assert reveal["lineup_count"] == 3
    assert reveal["complete_count"] == 1
    assert reveal["same_brain"] == []
    assert reveal["positions"][4]["picks_count"] == 1


def test_picks_at_1259_are_private_and_post_lock_reveal_is_available(monkeypatch):
    data = sample_bundle()
    rendered = []

    class FakeStreamlit:
        def markdown(self, text, **kwargs):
            rendered.append(text)
        def caption(self, text, **kwargs):
            rendered.append(text)
        def expander(self, text, **kwargs):
            rendered.append(text)
            from contextlib import nullcontext
            return nullcontext()

    render_open = _reveal_renderer(FakeStreamlit(), "open")
    render_open({"id": "w2"}, data)
    assert rendered == []
    render_locked = _reveal_renderer(FakeStreamlit())
    render_locked({"id": "w2", "is_demo": True}, data)
    assert rendered == []
    render_locked({"id": "w2", "is_demo": False}, data)
    output = " ".join(rendered)
    assert "THE 1 PM LINEUP REVEAL" in output
    assert "Josh Allen" in output and "Cassidy went alone" in output
    assert "Jenny, Mike" in output  # reveal who actually chose the shared QB
    assert "PRIVATE BACKUP" not in output and "b-private" not in output


def test_user_supplied_nicknames_and_player_names_are_html_escaped(monkeypatch):
    data = sample_bundle()
    data["players"][2]["nickname"] = '<img src=x onerror=alert(1)>'
    data["pool"][1]["player_name"] = '<script>alert(1)</script>'
    captured = []

    class FakeStreamlit:
        def markdown(self, text, **kwargs):
            captured.append(text)
        def caption(self, text, **kwargs):
            captured.append(text)
        def expander(self, text, **kwargs):
            from contextlib import nullcontext
            return nullcontext()

    _reveal_renderer(FakeStreamlit())({"id": "w2"}, data)
    rendered = " ".join(captured)
    assert '<script>' not in rendered and '<img src=' not in rendered
    assert '&lt;script&gt;' in rendered and '&lt;img src=' in rendered


def test_live_integration_keeps_reveal_after_lock_and_before_standings():
    ui_source = (ROOT / "gate4_ui.py").read_text()
    start = ui_source.index("def render_live_sunday(")
    end = ui_source.index("def _render_season_rows", start)
    live = ui_source[start:end]
    assert live.index('_render_lineup_reveal(fresh_week, bundle)') < live.index('st.markdown("### Standings")')
    assert 'if show_storylines and data_status != "FINAL":' in live
    assert 'if week_phase(week) != "locked" or bool(week.get("is_demo")):' in ui_source
    assert 'getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 7' in (ROOT / "app.py").read_text()
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.12"' in (ROOT / "config.py").read_text()
