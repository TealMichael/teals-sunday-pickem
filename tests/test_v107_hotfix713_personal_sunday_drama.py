"""Hotfix 7.13: factual, personalized Sunday drama without extra calls/writes."""
from __future__ import annotations

import ast
from contextlib import nullcontext
from copy import deepcopy
from html import escape
from pathlib import Path
from typing import Any

import gate4
import sunday_drama

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def _bundle():
    pool = []
    picks = []
    for i, (position, points, team) in enumerate(
        (("QB", 10.0, "BUF"), ("RB", 3.0, "PHI"), ("WR", 2.0, "MIN"),
         ("TE", 0.0, "KC"), ("K", 0.0, "DAL")), start=1
    ):
        pool.append({"id": f"pick{i}", "position": position, "team_abbr": team,
                     "player_name": f"{position} Hero", "score_total": points})
        pool.append({"id": f"rival{i}", "position": position, "team_abbr": team,
                     "player_name": f"{position} Rival", "score_total": points + (1 if position == "QB" else 0)})
        for lid, picked_id in (("l-mike", f"pick{i}"), ("l-jenny", f"rival{i}"), ("l-alan", f"pick{i}")):
            picks.append({"lineup_id": lid, "position": position,
                          "pool_player_id": picked_id, "emergency_pool_player_id": "SECRET-BACKUP"})
    # Alan is tied with Mike, while Jenny has one more point.
    pool[0]["score_total"] = 10.0
    pool.append({"id": "SECRET-BACKUP", "position": "QB", "player_name": "Secret Backup",
                 "team_abbr": "NE", "score_total": 500.0})
    return {
        "pool": pool,
        "players": [
            {"id": "p-mike", "nickname": "Mike", "emoji": "🏈"},
            {"id": "p-jenny", "nickname": "Jenny", "emoji": "🏈"},
            {"id": "p-alan", "nickname": "Alan", "emoji": "🏈"},
        ],
        "lineups": [
            {"id": "l-mike", "player_id": "p-mike", "confirmed_at": "yes"},
            {"id": "l-jenny", "player_id": "p-jenny", "confirmed_at": "yes"},
            {"id": "l-alan", "player_id": "p-alan", "confirmed_at": "yes"},
        ],
        "picks": picks,
        "games": [
            {"home_team": "BUF", "away_team": "NE", "game_status": "LIVE"},
            {"home_team": "PHI", "away_team": "DAL", "game_status": "SCHEDULED"},
            {"home_team": "MIN", "away_team": "GB", "game_status": "FINAL", "completed": True},
            {"home_team": "KC", "away_team": "LV", "game_status": "LIVE"},
        ],
    }


def _build():
    bundle = _bundle()
    return bundle, gate4.build_weekly_leaderboard(bundle)


def _ui_function(name: str, streamlit, phase="locked"):
    tree = ast.parse((ROOT / "gate4_ui.py").read_text())
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {"st": streamlit, "week_phase": lambda _: phase,
                 "build_personal_sunday_drama": sunday_drama.build_personal_sunday_drama,
                 "escape": escape, "_ordinal": lambda rank: f"{rank}th", "Any": Any}
    exec(compile(ast.Module(body=[func], type_ignores=[]), "gate4_ui.py", "exec"), namespace)
    return namespace[name]


class FakeStreamlit:
    def __init__(self):
        self.rendered = []

    def markdown(self, value, **kwargs):
        self.rendered.append(value)


def test_personal_chase_current_score_gap_and_top_player_are_grounded():
    bundle, leaderboard = _build()
    original = deepcopy(bundle)
    own = sunday_drama.build_personal_sunday_drama(bundle, leaderboard, "p-mike")
    assert own["score"] == 15.0 and own["rank"] == 2 and own["total_lineups"] == 3
    assert own["chasing"] == {"names": ["Jenny"], "rank": 1, "gap": 1.0}
    assert own["holding_off"] is None  # Alan has *the exact same* saved picks / score
    assert own["tied_with"] == ["Alan"]
    assert own["top_scorer"] == {"name": "QB Hero", "position": "QB", "points": 10.0}
    assert own["rival_games"]["name"] == "Jenny"
    assert own["rival_games"]["games"]["live"] == 2
    assert own["games"] == {"live": 2, "scheduled": 2, "final": 1, "unknown": 0, "known_players": 5}
    assert bundle == original
    assert "SECRET-BACKUP" not in str(own) and "Secret Backup" not in str(own)


def test_nearest_distinct_scores_handle_ties_and_stable_name_order():
    leaderboard = [
        {"player_id": "me", "nickname": "Me", "score": 17.0, "rank": 3, "roster": []},
        {"player_id": "a", "nickname": "Zoë", "score": 20.0, "rank": 1},
        {"player_id": "b", "nickname": "Amy", "score": 20.0, "rank": 1},
        {"player_id": "c", "nickname": "Sam", "score": 17.0, "rank": 3},
        {"player_id": "d", "nickname": "Eli", "score": 10.0, "rank": 5},
        {"player_id": "e", "nickname": "Lou", "score": 13.0, "rank": 4},
    ]
    actual = sunday_drama.build_personal_sunday_drama({"games": []}, leaderboard, "me")
    assert actual["tied_with"] == ["Sam"]
    assert actual["chasing"] == {"names": ["Amy", "Zoë"], "rank": 1, "gap": 3.0}
    assert actual["holding_off"] == {"names": ["Lou"], "rank": 4, "gap": 4.0}
    assert actual["top_scorer"] is None
    assert actual["rival_games"] is None  # tied nearest competitors are not arbitrarily selected


def test_leader_and_last_have_no_fictitious_rival_or_prediction():
    _, leaderboard = _build()
    leader = sunday_drama.build_personal_sunday_drama({}, leaderboard, "p-jenny")
    assert leader["chasing"] is None
    assert leader["holding_off"]["gap"] == 1.0
    assert sunday_drama.build_personal_sunday_drama({}, leaderboard, "non-member") is None
    assert sunday_drama.build_personal_sunday_drama({}, [], "p-mike") is None


def test_no_game_rows_means_unavailable_not_false_completed_or_live():
    bundle, leaderboard = _build()
    bundle["games"] = []
    drama = sunday_drama.build_personal_sunday_drama(bundle, leaderboard, "p-mike")
    assert drama["games"]["unknown"] == 5
    assert drama["games"]["live"] == drama["games"]["final"] == 0
    # An incomplete/missing pick must not become a fictitious player.
    leaderboard[1]["roster"] = [{"position": "QB", "missing": True, "points": 0}]
    assert sunday_drama.build_personal_sunday_drama(bundle, leaderboard, "p-mike") is not None


def test_emergency_activation_uses_existing_scoring_roster_not_unactivated_backup():
    bundle, _ = _build()
    bundle["pool"][-1]["availability_status"] = "HEALTHY"
    bundle["pool"][0]["availability_status"] = "OUT"
    # Existing scoring logic activates a backup only on OUT and eligible.
    leaderboard = gate4.build_weekly_leaderboard(bundle)
    result = sunday_drama.build_personal_sunday_drama(bundle, leaderboard, "p-mike")
    assert result["top_scorer"]["name"] == "Secret Backup"
    assert result["games"]["live"] == 2  # active NE in the BUF/NE game
    assert "SECRET-BACKUP" not in str(result)  # no private IDs disclosed


def test_ui_protects_open_weeks_demo_and_missing_player():
    bundle, leaderboard = _build()
    for phase, week in (("open", {"id": "w"}), ("locked", {"id": "w", "is_demo": True})):
        fake = FakeStreamlit()
        _ui_function("_render_personal_sunday_drama", fake, phase)(week, bundle, leaderboard, "p-mike")
        assert fake.rendered == []
    fake = FakeStreamlit()
    _ui_function("_render_personal_sunday_drama", fake)({"id": "w"}, bundle, leaderboard, "not-here")
    assert fake.rendered == []


def test_ui_is_compact_and_html_escapes_all_names_and_stats():
    bundle, leaderboard = _build()
    me = next(row for row in leaderboard if row["player_id"] == "p-mike")
    opponent = next(row for row in leaderboard if row["player_id"] == "p-jenny")
    opponent["nickname"] = '<img src=x onerror=alert(1)>'
    me["roster"][0]["player"]["player_name"] = '<script>bad()</script>'
    fake = FakeStreamlit()
    _ui_function("_render_personal_sunday_drama", fake)({"id": "w"}, bundle, leaderboard, "p-mike")
    output = " ".join(fake.rendered)
    assert "YOUR SUNDAY RACE" in output and "15.0 pts" in output
    assert "&lt;script&gt;bad()&lt;/script&gt;" in output
    assert "<script>" not in output and "<img src=" not in output
    assert "SECRET-BACKUP" not in output and "Secret Backup" not in output
    assert "pts behind" in output and "Level with" in output
    assert "Jenny at last NFL update: 2 live" not in output  # malicious name is escaped
    assert "&lt;img src=x onerror=alert(1)&gt; at last NFL update: 2 live" in output


def test_ui_empty_games_do_not_claim_all_finished():
    bundle, leaderboard = _build()
    bundle["games"] = []
    fake = FakeStreamlit()
    _ui_function("_render_personal_sunday_drama", fake)({"id": "w"}, bundle, leaderboard, "p-mike")
    text = " ".join(fake.rendered)
    assert "status unavailable" in text
    assert "All your players' games are final" not in text


def test_ui_all_final_only_when_all_selected_players_have_confirmed_final_games():
    bundle, leaderboard = _build()
    bundle["games"] = [
        {"home_team": "BUF", "away_team": "NE", "game_status": "FINAL"},
        {"home_team": "PHI", "away_team": "DAL", "game_status": "FINAL"},
        {"home_team": "MIN", "away_team": "GB", "game_status": "FINAL"},
        {"home_team": "KC", "away_team": "LV", "game_status": "FINAL"},
    ]
    fake = FakeStreamlit()
    _ui_function("_render_personal_sunday_drama", fake)({"id": "w"}, bundle, leaderboard, "p-mike")
    assert "All your players&#x27; games are final" in " ".join(fake.rendered)


def test_integration_after_reveal_before_general_storylines_and_no_mutations():
    source = (ROOT / "gate4_ui.py").read_text()
    live = source.split("def render_live_sunday(", 1)[1].split("def _render_season_rows", 1)[0]
    assert live.index("_render_lineup_reveal(fresh_week, bundle)") < live.index("_render_personal_sunday_drama(")
    assert live.index("_render_personal_sunday_drama(") < live.index("_storylines(bundle, leaderboard)")
    assert 'if show_storylines and data_status != "FINAL":' in live
    assert 'if week_phase(week) != "locked" or bool(week.get("is_demo")):' in source
    assert "get_week_public_bundle" in live
    assert 'getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 8' in (ROOT / "app.py").read_text()
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.13"' in (ROOT / "config.py").read_text()
    assert "SUNDAY_DRAMA_SCHEMA_VERSION = 1" in (ROOT / "sunday_drama.py").read_text()
    assert "LIVE_APP_DISPLAY_REFRESH_SECONDS = 15" in (ROOT / "config.py").read_text()
    assert "save_pick" not in (ROOT / "sunday_drama.py").read_text()
