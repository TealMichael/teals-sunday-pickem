"""Achievements + season story: use ONLY finalized archives, no mutable lineups."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from copy import deepcopy
from html import escape
from pathlib import Path
from typing import Any

import personal_season_story

ROOT = Path(__file__).resolve().parents[1]


def row(week, player, rank, score, points, season=2026):
    return {
        "season": season, "nfl_week": week, "player_id": player,
        "nickname_snapshot": player, "emoji_snapshot": "🏈",
        "finish_rank": rank, "weekly_score": score, "season_points": points,
        "finalized_at": "2026-09-14T13:00:00+00:00",
    }


def awards(story):
    return {item["code"]: item for item in story["awards"]}


def test_empty_newcomer_and_empty_id_have_no_awards_or_fake_stats():
    for results, player in (([], "me"), ([row(1, "other", 1, 123, 12)], "me"), ([row(1, "me", 1, 123, 12)], "")):
        assert personal_season_story.build_personal_season_story(results, player) == {
            "weeks": [], "awards": [], "summary": None,
        }


def test_first_week_is_real_and_history_is_not_mutated():
    archive = [row(1, "me", 2, 98.4, 9), row(1, "other", 1, 110.1, 12)]
    before = deepcopy(archive)
    story = personal_season_story.build_personal_season_story(archive, "me")
    assert archive == before
    assert story["summary"]["season_rank"] == 2
    assert story["summary"]["weeks_played"] == 1
    assert story["summary"]["best_score"] == 98.4
    assert story["weeks"][0]["rank_move"] is None
    assert set(awards(story)) == {"first_podium", "first_week"}
    assert story["weeks"][0]["earned_points"] == 9


def test_first_victory_century_club_and_podium_hat_trick_are_earned_once():
    archive = [
        row(1, "me", 2, 98, 9), row(1, "other", 1, 110, 12),
        row(2, "me", 1, 120, 12), row(2, "other", 2, 80, 9),
        row(3, "me", 3, 105, 7), row(3, "other", 1, 125, 12),
        row(4, "me", 1, 130, 12), row(4, "other", 2, 99, 9),
    ]
    story = personal_season_story.build_personal_season_story(archive, "me")
    got = awards(story)
    assert got["first_win"]["week"] == 2
    assert got["century"]["week"] == 2
    assert got["hat_trick"]["week"] == 3
    assert got["season_lead"]["week"] == 2
    assert story["summary"]["best_score"] == 130.0
    assert story["summary"]["best_week"] == 4
    assert story["summary"]["longest_podium_streak"] == 4
    assert len([a for a in story["awards"] if a["code"] == "first_win"]) == 1
    assert story["weeks"][0]["week"] == 4


def test_missing_calendar_week_breaks_consecutive_podium_and_does_not_create_zero_finish():
    archive = [
        row(1, "me", 3, 80, 7), row(1, "other", 1, 100, 12),
        row(2, "me", 2, 90, 9), row(2, "other", 1, 101, 12),
        row(3, "other", 1, 102, 12),  # Me did not play.
        row(4, "me", 1, 112, 12), row(4, "other", 2, 95, 9),
    ]
    story = personal_season_story.build_personal_season_story(archive, "me")
    assert "hat_trick" not in awards(story)
    assert [entry["week"] for entry in story["weeks"]] == [4, 2, 1]
    assert story["summary"]["weeks_played"] == 3
    assert story["summary"]["finalized_weeks"] == 4
    assert story["summary"]["longest_podium_streak"] == 2


def test_rank_movement_uses_group_standings_tiebreak_and_not_weekly_finishes():
    archive = [
        row(1, "me", 4, 50, 6), row(1, "a", 1, 110, 12),
        row(1, "b", 2, 90, 9), row(1, "c", 3, 70, 7),
        row(2, "me", 1, 150, 12), row(2, "a", 4, 40, 6),
        row(2, "b", 3, 75, 7), row(2, "c", 2, 100, 9),
    ]
    story = personal_season_story.build_personal_season_story(archive, "me")
    # Week 2 me: 18 season points / 200 fantasy, a: 18 / 150,
    # b: 16, c: 16; this is a genuine move from 4th -> 1st.
    assert story["weeks"][0]["season_rank"] == 1
    assert story["weeks"][0]["rank_move"] == 3
    assert story["summary"]["best_climb"] == 3
    assert awards(story)["climber"]["week"] == 2
    assert story["weeks"][0]["season_points"] == 18


def test_equal_points_and_fantasy_are_true_competition_ties():
    archive = [row(1, "me", 1, 105, 12), row(1, "other", 1, 105, 12)]
    story = personal_season_story.build_personal_season_story(archive, "me")
    assert story["summary"]["season_rank"] == 1
    assert "season_lead" in awards(story)
    assert "first_win" in awards(story)


def test_missed_latest_week_uses_current_rank_but_does_not_invent_a_played_week():
    archive = [
        row(1, "me", 1, 111, 12), row(1, "a", 2, 90, 9),
        row(2, "a", 1, 150, 12), row(2, "b", 2, 100, 9),
    ]
    story = personal_season_story.build_personal_season_story(archive, "me")
    assert story["summary"]["latest_finalized_week"] == 2
    assert story["summary"]["latest_played_week"] == 1
    assert story["summary"]["season_rank"] == 2
    assert len(story["weeks"]) == 1


def test_archive_scope_does_not_mix_two_seasons():
    archive = [row(1, "me", 1, 105, 12, 2025), row(1, "me", 2, 70, 9, 2026)]
    story = personal_season_story.build_personal_season_story(archive, "me")
    assert story["summary"]["season_points"] == 9
    assert "first_win" not in awards(story)


class FakeStreamlit:
    def __init__(self):
        self.markdowns = []
        self.captions = []
        self.expanders = []

    def markdown(self, value, **kwargs):
        self.markdowns.append(value)

    def caption(self, value, **kwargs):
        self.captions.append(value)

    @contextmanager
    def expander(self, label, **kwargs):
        self.expanders.append(label)
        yield


def _isolated_ui(name, fake):
    source = ast.parse((ROOT / "gate4_ui.py").read_text())
    funcs = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in {name, "_story_week_row"}]
    namespace = {"st": fake, "escape": escape, "Any": Any, "_ordinal": lambda n: f"{n}th"}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), "gate4_ui.py", "exec"), namespace)
    return namespace[name]


def test_ui_is_read_only_compact_escaped_and_shows_earlier_weeks():
    archive = [row(w, "me", 2 if w % 2 else 1, 80+w, 9 if w % 2 else 12) for w in range(1, 6)]
    archive += [row(w, "other", 1 if w % 2 else 2, 100, 12 if w % 2 else 9) for w in range(1, 6)]
    story = personal_season_story.build_personal_season_story(archive, "me")
    story["awards"][0]["title"] = '<script>alert(1)</script>'
    fake = FakeStreamlit()
    _isolated_ui("_render_personal_season_story", fake)(story)
    rendered = "\n".join(fake.markdowns)
    assert "YOUR SEASON SO FAR" in rendered and "My Achievements" in rendered
    assert "See 2 earlier weeks" in fake.expanders
    assert 'Week 5' in rendered and 'Week 1' in rendered
    assert '<script>' not in rendered and '&lt;script&gt;' in rendered
    assert not hasattr(fake, "write_to_database")


def test_ui_newcomer_stays_safe_and_no_provisional_awards():
    fake = FakeStreamlit()
    _isolated_ui("_render_personal_season_story", fake)({"weeks": [], "awards": [], "summary": None})
    assert "first finalized Sunday" in " ".join(fake.captions)
    assert not any("100-Point Club" in text for text in fake.markdowns)


def test_integration_one_cached_archive_read_no_mutation_no_nfl_calls():
    ui = (ROOT / "gate4_ui.py").read_text()
    profile = ui.split("def render_profile(", 1)[1].split("def maybe_render_final_celebration(", 1)[0]
    assert profile.count("get_weekly_results(") == 1
    assert "build_personal_season_story(archived, player_id)" in profile
    assert "_render_personal_season_story" in profile
    helper = (ROOT / "personal_season_story.py").read_text()
    for forbidden in ("save_pick(", "get_week_public_bundle(", "upsert(", "requests.get(", "nfl_sync", "emergency_pool_player_id"):
        assert forbidden not in helper
    assert 'GATE4_UI_SCHEMA_VERSION = 9' in ui
    assert 'getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 9' in (ROOT / "app.py").read_text()
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.14"' in (ROOT / "config.py").read_text()
