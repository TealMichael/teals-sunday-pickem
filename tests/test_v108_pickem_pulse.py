"""v1.0.8: factual, minimal UI, and completely isolated engagement storage."""
from __future__ import annotations

import sys
from types import ModuleType

try:
    import streamlit  # noqa: F401
except ImportError:
    sys.modules.setdefault("streamlit", ModuleType("streamlit"))

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
from types import SimpleNamespace

from pickem_pulse import (
    REACTION_OPTIONS, live_pulse, personal_goal, pregame_pulse,
    previous_results, reaction_totals, snapshot_for, goal_progress,
)
from pulse_ui import _pulse_card, _last_checkin, render_reactions
from store import SupabaseStore


def historical():
    return [
        {"player_id":"a", "nickname_snapshot":"Mike", "nfl_week":1, "weekly_score":95, "finish_rank":4},
        {"player_id":"b", "nickname_snapshot":"Jenny", "nfl_week":1, "weekly_score":96, "finish_rank":3},
        {"player_id":"a", "nickname_snapshot":"Mike", "nfl_week":2, "weekly_score":100, "finish_rank":2},
        {"player_id":"b", "nickname_snapshot":"Jenny", "nfl_week":2, "weekly_score":102, "finish_rank":1},
        {"player_id":"c", "nickname_snapshot":"<SCRIPT>alert(1)</SCRIPT>", "nfl_week":2, "weekly_score":104},
        {"player_id":"a", "nickname_snapshot":"Mike", "nfl_week":3, "weekly_score":999}, # current week NOT prior
    ]


def board():
    return [
        {"player_id":"b","nickname":"Jenny", "rank":1, "score":108.1},
        {"player_id":"a","nickname":"Mike", "rank":2, "score":105.9},
        {"player_id":"c","nickname":"Alan", "rank":3, "score":102.7},
    ]


def test_pregame_only_uses_finalized_prior_week_and_not_current_week():
    rows = historical()
    original = deepcopy(rows)
    pulse = pregame_pulse(rows, "a", 3)
    assert "Week 3" in pulse["heading"]
    assert "Jenny" in pulse["detail"] and "2.0 points" in pulse["detail"]
    assert pulse["goal"] == "Beat your 97.5-point season average"
    assert rows == original and "999" not in str(pulse)


def test_first_timer_has_factually_safe_story_and_goal():
    pulse = pregame_pulse(historical(), "newcomer", 5)
    assert pulse["goal"] == "Finish in the Top 5"
    assert "two weeks" not in str(pulse)


def test_one_previous_week_gets_score_goal_not_season_average():
    goal = personal_goal(previous_results(historical(), 2), "a")
    assert goal["kind"] == "personal_best"
    assert goal["threshold"] == 95


def test_final_status_requires_strictly_exceeding_average_or_best():
    goal = {"kind":"average", "threshold":105.9, "label":"Beat your average"}
    assert "not reached" in goal_progress(goal, board()[1], final=True)
    assert "currently" not in goal_progress(goal, board()[1], final=True)
    assert "Your goal" in goal_progress(goal, board()[1], final=False)


def test_top_five_requires_rank_from_actual_standings():
    goal = {"kind":"top_five", "threshold":5,"label":"Finish in the Top 5"}
    assert "Goal achieved" in goal_progress(goal, {"rank":5}, final=True)
    assert "not reached" in goal_progress(goal, {"rank":6}, final=True)


def test_live_pulse_uses_saved_rank_not_false_projected_movement():
    old = {"rank":5,"score":97,"player_count":3}
    result = live_pulse(board(), "a", old, personal_goal([], "a"))
    assert "moved up 3 places" in result["heading"]
    assert "105.9 points" in result["detail"]
    assert "probability" not in str(result)


def test_rank_worsening_vs_increasing_score_is_not_called_a_climb():
    old = {"rank":1, "score":101}
    result = live_pulse(board(), "a", old, personal_goal([], "a"))
    assert "now 2nd" in result["heading"]
    assert "moved up" not in str(result)


def test_live_without_last_checkin_is_neutral_and_grounded():
    pulse = live_pulse(board(), "a", None, personal_goal([], "a"))
    assert "2nd" in pulse["heading"]
    assert "2.2 points behind Jenny" in pulse["detail"]
    assert "since" not in str(pulse)


def test_final_pulse_does_not_claim_provisional_changes():
    pulse = live_pulse(board(), "a", {"rank":9, "score":0}, personal_goal([], "a"), final=True)
    assert pulse["heading"] == "You finished 2nd!"
    assert "final score" in pulse["detail"]


def test_snapshot_is_minimal_and_no_lineup_or_names():
    snapshot = snapshot_for(board(), "a")
    assert snapshot == {"rank":2, "score":105.9, "player_count":3}
    assert snapshot_for(board(), "missing") is None


def test_friendly_reactions_are_single_whitelisted_emojis_without_self_ones():
    eligible = {"a","b","c"}
    rows = [
        {"key":"pickem_pulse_reaction:week:a","value":{"target":"b","emoji":"🔥"}},
        {"key":"pickem_pulse_reaction:week:c","value":{"target":"b","emoji":"👏"}},
        {"key":"pickem_pulse_reaction:week:b","value":{"target":"b","emoji":"😂"}}, # no self
        {"key":"pickem_pulse_reaction:week:fake","value":{"target":"b","emoji":"👀"}}, # unknown
        {"key":"pickem_pulse_reaction:week:x","value":{"target":"b","emoji":"<script>"}},
    ]
    assert reaction_totals(rows, "b", eligible) == {"🔥":1,"👏":1}
    assert len(REACTION_OPTIONS) == 4


class FakeMetaTable:
    def __init__(self):
        self.rows = []
        self.last_payload = None
    def upsert(self, payload, *, on_conflict):
        self.last_payload = payload
        return self
    def execute(self):
        return SimpleNamespace(data=[self.last_payload] if self.last_payload else self.rows)
    def select(self, *args):
        return self
    def like(self, *args):
        return self
    def limit(self, *args):
        return self


def test_store_reaction_does_not_need_a_new_table_or_allow_unsafe_value():
    table = FakeMetaTable()
    store = SupabaseStore.__new__(SupabaseStore)
    store._table = lambda name: table if name == "app_meta" else (_ for _ in ()).throw(AssertionError(name))
    store.save_pulse_reaction("week", "a", "b", "🔥")
    assert table.last_payload["key"] == "pickem_pulse_reaction:week:a"
    assert table.last_payload["value"] == {"target":"b", "emoji":"🔥"}
    store.save_pulse_reaction("week", "a", "b", "")
    assert table.last_payload["value"]["emoji"] == ""
    for target, emoji in (("a", "🔥"),("b", "<html>")):
        try:
            store.save_pulse_reaction("week", "a", target, emoji)
        except ValueError:
            pass
        else:
            assert False, "unsafe reaction must fail"


def test_store_reaction_list_reads_only_app_meta():
    table = FakeMetaTable()
    store = SupabaseStore.__new__(SupabaseStore)
    store._table = lambda name: table if name == "app_meta" else (_ for _ in ()).throw(AssertionError(name))
    assert store.get_pulse_reactions("week") == []


class FakeSession(dict):
    pass


class FakeSt:
    def __init__(self):
        self.session_state = FakeSession()
        self.markup = []
    def markdown(self, text, **kwargs):
        self.markup.append(text)


def test_card_escapes_names_even_if_archived_nicknames_contain_markup(monkeypatch):
    import pulse_ui
    fake = FakeSt()
    monkeypatch.setattr(pulse_ui, "st", fake)
    _pulse_card({"heading":"Hi <script>alert(1)</script>",
                 "detail":"<iframe>", "goal":"Be <first>"})
    output = fake.markup[0]
    assert "&lt;script&gt;" in output and "<script>" not in output
    assert "&lt;iframe&gt;" in output


def test_checkin_read_once_and_write_no_more_than_once_on_fast_rerender(monkeypatch):
    import pulse_ui
    fake = FakeSt()
    monkeypatch.setattr(pulse_ui, "st", fake)
    class Store:
        reads = 0
        saves = 0
        def get_app_meta(self, key):
            self.reads += 1
            return {"value":{"rank":3,"score":99.0}}
        def set_app_meta(self, key, value):
            self.saves += 1
    store = Store()
    assert _last_checkin(store,"w","a",board()) == {"rank":3, "score":99.0}
    assert _last_checkin(store,"w","a",board()) == {"rank":3, "score":99.0}
    assert store.reads == 1 and store.saves == 1


def test_optional_pregame_and_postlock_only(monkeypatch):
    # Structural safety: never add a Pulse to the five-player picker itself.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    weekly = (root / "weekly_ui.py").read_text()
    home = weekly.split("def _open_home(")[1].split("def _locked_home(")[0]
    builder = weekly.split("def _builder(")[1].split("def _open_home(")[0]
    gate4 = (root / "gate4_ui.py").read_text()
    assert "render_pregame_pulse(store, week, player)" in home
    assert "render_pregame_pulse(" not in builder
    assert gate4.count("render_live_pulse(store, fresh_week, player") == 1
    assert gate4.count("render_reactions(store, fresh_week, player") == 1
    assert "st.expander(\"👏 Cheer someone on\", expanded=False)" in (root / "pulse_ui.py").read_text()
    assert "render_reactions" not in weekly


def test_reactions_blocked_before_lock_even_if_directly_invoked(monkeypatch):
    import pulse_ui
    fake = FakeSt()
    monkeypatch.setattr(pulse_ui,"st",fake)
    class Store:
        def get_pulse_reactions(self, _):
            raise AssertionError("No prelock social access")
    now = datetime.now(timezone.utc)
    week = {"id":"w", "opens_at":(now-timedelta(hours=1)).isoformat(),
            "locks_at":(now+timedelta(hours=1)).isoformat()}
    render_reactions(Store(), week, {"id":"a"}, board())
    assert fake.markup == []
