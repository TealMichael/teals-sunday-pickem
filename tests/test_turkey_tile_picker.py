"""Thanksgiving starter-only tile picker: no emergency choices, no Sunday changes."""
from __future__ import annotations

import inspect

import turkey_bowl_ui as holiday


class Rerun(BaseException):
    pass


class FakeStreamlit:
    def __init__(self, click=""):
        self.session_state = {}
        self.click = click
        self.tiles = []
        self.messages = []
        self.buttons = []

    def segmented_control(self, label, options, *, default=None, key=None):
        return self.session_state.get(key, default)

    def button(self, label, *args, **kwargs):
        self.buttons.append((label, kwargs))
        return label == self.click and not kwargs.get("disabled", False)

    def rerun(self):
        raise Rerun()

    def __getattr__(self, name):
        if name in {"caption", "markdown", "success", "warning", "info", "error", "toast"}:
            return lambda *args, **kwargs: self.messages.append((name, args))
        raise AttributeError(name)


class FakeService:
    def __init__(self):
        self.rows = [dict(id=f"{pos}-{i}", position=pos, slot_rank=i + 1,
                          is_visible=True, player_name=f"{pos} {i}",
                          team_abbr="CHI", opponent_abbr="DET",
                          availability_status="HEALTHY")
                     for pos in ("QB", "RB", "WR", "TE", "K") for i in range(5)]
        self.picks = []
        self.saves = []
        self.confirmations = []
        self.confirmed_at = None
        self.ignore_confirm_write = False
        self.raise_on_confirm = False

    def pool(self, event_id, *, visible_only=False):
        return [r for r in self.rows if r["is_visible"]] if visible_only else list(self.rows)

    def lineup(self, event_id, player_id):
        return ({"id": "fake-lineup", "confirmed_at": self.confirmed_at} if self.picks else None, list(self.picks))

    def save_pick(self, event, player_id, pos, starter):
        self.saves.append((pos, starter))
        self.confirmed_at = None
        self.picks = [p for p in self.picks if p["position"] != pos] + [
            {"position": pos, "pool_player_id": starter}]

    def confirm(self, event, player_id):
        self.confirmations.append(player_id)
        if self.raise_on_confirm:
            raise ValueError("Database write failed")
        if not self.ignore_confirm_write:
            self.confirmed_at = "2026-11-24T20:00:00Z"


def prepare(monkeypatch, fake):
    monkeypatch.setattr(holiday, "st", fake)
    monkeypatch.setattr(holiday, "_turkey_player_tile", lambda row, **kw: fake.tiles.append((row, kw)))
    import weekly_ui
    monkeypatch.setattr(weekly_ui, "_stable_order", lambda pid, eid, pos, rows: rows)


def test_staging_only_one_starter_and_never_uses_sunday_keys(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(holiday, "st", fake)
    saved = {"pool_player_id": "QB-0", "emergency_pool_player_id": "QB-1"}
    assert holiday._draft_selection("holiday", "user", "QB", saved) == "QB-0"
    holiday._stage_starter("holiday", "user", "QB", "QB-2")
    assert holiday._draft_selection("holiday", "user", "QB", saved) == "QB-2"
    assert all(k.startswith("turkey_draft::") for k in fake.session_state)
    holiday._clear_draft("holiday", "user", "QB")
    assert fake.session_state == {}


def test_tile_stage_then_save_directly_advances_without_backup(monkeypatch):
    fake = FakeStreamlit()
    fake.session_state["turkey_edit_position"] = "QB"
    service = FakeService()
    prepare(monkeypatch, fake)
    event, player = {"id": "event-2026"}, {"id": "player-1"}

    holiday._lineup_picker(service, event, player)
    assert len(fake.tiles) == 5 and not service.saves
    assert not any("Backup" in label or "backup" in label for label, _ in fake.buttons)

    holiday._stage_starter("event-2026", "player-1", "QB", "QB-0")
    fake.click = "Save QB · Next: RB →"
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Expected rerun after direct save")
    assert service.saves == [("QB", "QB-0")]
    assert fake.session_state["turkey_next_position"] == "RB"
    assert "turkey_draft::event-2026::player-1::QB::starter" not in fake.session_state

    fake.click = ""
    holiday._lineup_picker(service, event, player)
    assert fake.session_state["turkey_edit_position"] == "RB"
    assert len(service.saves) == 1


def test_unchanged_starter_does_not_write_or_invalidate_confirmation(monkeypatch):
    fake = FakeStreamlit(click="Save QB · Next: RB →")
    fake.session_state["turkey_edit_position"] = "QB"
    service = FakeService()
    # A legacy saved backup is deliberately ignored, not treated as a pending change.
    service.picks = [{"position": "QB", "pool_player_id": "QB-0", "emergency_pool_player_id": "QB-1"}]
    prepare(monkeypatch, fake)
    try:
        holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Expected navigation rerun")
    assert not service.saves


def test_reuses_sunday_tiles_but_no_backup_controls():
    tile_source = inspect.getsource(holiday._turkey_player_tile)
    picker_source = inspect.getsource(holiday._lineup_picker)
    assert "from weekly_ui import _render_player_card_button" in tile_source
    assert "_render_player_card_button(" in tile_source
    assert "st.selectbox(" not in picker_source
    assert "service.save_pick(" in picker_source
    assert "service.confirm(" in picker_source
    assert "Next: Emergency Backup" not in picker_source
    assert "_stage_backup" not in picker_source
    assert "as_backup" not in tile_source


def test_confirm_complete_lineup_with_legacy_backups(monkeypatch):
    fake = FakeStreamlit(click="✅ Confirm my Turkey Bowl lineup")
    fake.session_state["turkey_edit_position"] = "K"
    service = FakeService()
    service.picks = [dict(position=pos, pool_player_id=f"{pos}-0", emergency_pool_player_id=f"{pos}-1")
                     for pos in ("QB", "RB", "WR", "TE", "K")]
    prepare(monkeypatch, fake)
    try:
        holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Expected confirmation rerun")
    assert service.confirmations == ["player-1"]
    assert not service.saves
    assert all("Backup:" not in str(args) for _, args in fake.messages)


def test_out_tile_stays_visible_but_cannot_be_saved(monkeypatch):
    fake = FakeStreamlit(click="Save QB · Next: RB →")
    fake.session_state["turkey_edit_position"] = "QB"
    service = FakeService()
    service.rows[0]["availability_status"] = "OUT"
    prepare(monkeypatch, fake)
    holiday._stage_starter("event-2026", "player-1", "QB", "QB-0")
    holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    assert len(fake.tiles) == 5
    assert sum(row["availability_status"] == "OUT" for row, _ in fake.tiles) == 1
    assert not service.saves
    assert any(label.startswith("Save QB") and options.get("disabled") for label, options in fake.buttons)


def test_questionable_starter_warning_but_no_backup_required(monkeypatch):
    fake = FakeStreamlit(click="Save QB · Next: RB →")
    fake.session_state["turkey_edit_position"] = "QB"
    service = FakeService()
    service.rows[0]["availability_status"] = "QUESTIONABLE"
    prepare(monkeypatch, fake)
    holiday._stage_starter("event-2026", "player-1", "QB", "QB-0")
    try:
        holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Expected save rerun")
    assert service.saves == [("QB", "QB-0")]
    assert any("QUESTIONABLE" in str(args) for key, args in fake.messages if key == "warning")


def test_locked_turkey_lineup_hides_any_legacy_backup(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(holiday, 'st', fake)
    monkeypatch.setattr(holiday, '_live_scores', lambda *a, **k: None)
    service = FakeService()
    service.picks=[dict(position='QB',pool_player_id='QB-0',emergency_pool_player_id='QB-1')]
    holiday._locked_view(service, {'id':'event-2026','refreshed_at':None}, {'id':'player-1'})
    rendered=' '.join(str(args) for _,args in fake.messages)
    assert 'QB 0' in rendered
    assert 'QB 1' not in rendered
    assert 'backup:' not in rendered.lower()


def test_saving_final_k_opens_review_instead_of_staying_on_picker(monkeypatch):
    fake = FakeStreamlit(click="Save K · Review my five →")
    fake.session_state["turkey_edit_position"] = "K"
    service = FakeService()
    service.picks = [dict(position=p, pool_player_id=f"{p}-0")
                     for p in ("QB", "RB", "WR", "TE")]
    prepare(monkeypatch, fake)
    event, player = {"id": "event-2026"}, {"id": "player-1"}
    holiday._stage_starter("event-2026", "player-1", "K", "K-0")
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Saving K should transition to review")
    assert service.saves == [("K", "K-0")]
    assert fake.session_state[holiday._view_key("event-2026", "player-1")] == "review"
    fake.click = ""
    fake.buttons.clear()
    fake.tiles.clear()
    holiday._lineup_picker(service, event, player)
    assert len(fake.tiles) == 0
    assert any("Review your Thanksgiving five" in str(args) for _, args in fake.messages)
    assert any(label == "✅ Confirm my Turkey Bowl lineup" for label, _ in fake.buttons)


def test_existing_confirmed_lineup_stays_on_success_not_repeated_confirm(monkeypatch):
    fake = FakeStreamlit()
    service = FakeService()
    service.picks = [dict(position=p, pool_player_id=f"{p}-0")
                     for p in ("QB", "RB", "WR", "TE", "K")]
    service.confirmed_at = "2026-11-24T20:00:00Z"
    prepare(monkeypatch, fake)
    holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    assert len(fake.tiles) == 0
    assert any(label == "Edit my picks" for label, _ in fake.buttons)
    assert not any("Confirm my Turkey Bowl lineup" in label for label, _ in fake.buttons)
    assert any("You're in the Turkey Bowl!" in str(args) for key,args in fake.messages if key == "success")
    assert sum('tb-summary-row' in str(args) for key,args in fake.messages if key == "markdown") == 1


def test_editing_confirmed_starter_requires_reconfirmation(monkeypatch):
    fake = FakeStreamlit(click="Edit my picks")
    service = FakeService()
    service.picks = [dict(position=p, pool_player_id=f"{p}-0")
                     for p in ("QB", "RB", "WR", "TE", "K")]
    service.confirmed_at = "2026-11-24T20:00:00Z"
    prepare(monkeypatch, fake)
    event, player = {"id": "event-2026"}, {"id": "player-1"}
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Edit should navigate")
    assert fake.session_state[holiday._view_key("event-2026", "player-1")] == "edit"
    fake.click = "Save QB · Review my five →"
    fake.session_state['turkey_edit_position'] = "QB"
    holiday._stage_starter("event-2026", "player-1", "QB", "QB-1")
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Saving changed starter should navigate")
    assert service.confirmed_at is None
    assert service.saves == [("QB", "QB-1")]
    fake.click = ""
    fake.buttons.clear()
    holiday._lineup_picker(service, event, player)
    assert any(label == "✅ Confirm my Turkey Bowl lineup" for label, _ in fake.buttons)
    assert not any(label == "Edit my picks" for label, _ in fake.buttons)


def test_confirmation_readback_failure_never_claims_success(monkeypatch):
    fake = FakeStreamlit(click="✅ Confirm my Turkey Bowl lineup")
    service = FakeService()
    service.picks = [dict(position=p, pool_player_id=f"{p}-0")
                     for p in ("QB", "RB", "WR", "TE", "K")]
    service.ignore_confirm_write = True
    prepare(monkeypatch, fake)
    holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    assert service.confirmations == ["player-1"]
    assert service.confirmed_at is None
    assert any("could not be verified" in str(args) for key,args in fake.messages if key == "error")
    assert fake.session_state.get(holiday._view_key("event-2026", "player-1")) != "confirmed"


def test_confirmation_write_error_never_claims_success(monkeypatch):
    fake = FakeStreamlit(click="✅ Confirm my Turkey Bowl lineup")
    service = FakeService()
    service.picks = [dict(position=p, pool_player_id=f"{p}-0")
                     for p in ("QB", "RB", "WR", "TE", "K")]
    service.raise_on_confirm = True
    prepare(monkeypatch, fake)
    holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    assert any("Database write failed" in str(args) for key,args in fake.messages if key == "error")
    assert not any(key == "success" for key,args in fake.messages)


def test_mobile_css_scoped_and_sunday_ui_untouched():
    source = inspect.getsource(holiday._turkey_mobile_styles)
    assert ".tb-title" in source
    assert ".tb-bottom-clearance" in source
    assert "stAppViewBlockContainer" not in source
    assert "weekly_ui" not in source
    assert holiday.TURKEY_BOWL_UI_SCHEMA_VERSION >= 4


def test_review_escapes_dynamic_player_names(monkeypatch):
    fake=FakeStreamlit()
    monkeypatch.setattr(holiday, 'st', fake)
    holiday._lineup_summary({'QB': {'pool_player_id': 'injected'}},
                            {'injected': {'player_name': '<script>alert(1)</script>', 'team_abbr': 'CHI'}})
    text = ' '.join(str(args) for key,args in fake.messages if key=='markdown')
    assert '&lt;script&gt;' in text
    assert '<script>' not in text


def test_confirmation_readback_then_success_screen(monkeypatch):
    fake = FakeStreamlit(click="✅ Confirm my Turkey Bowl lineup")
    service = FakeService()
    service.picks = [dict(position=pos, pool_player_id=f"{pos}-0")
                     for pos in ("QB", "RB", "WR", "TE", "K")]
    prepare(monkeypatch, fake)
    event, player = {"id": "event-2026"}, {"id": "player-1"}
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Successful verification must navigate to success")
    assert bool(service.confirmed_at)
    assert fake.session_state[holiday._view_key("event-2026", "player-1")] == "confirmed"
    fake.click = ""
    fake.buttons.clear()
    fake.messages.clear()
    holiday._lineup_picker(service, event, player)
    assert any("You're in the Turkey Bowl" in str(args)
               for kind,args in fake.messages if kind == "success")
    assert [label for label, _ in fake.buttons] == ["Edit my picks"]


def test_finishing_position_out_of_order_navigates_to_missing_one(monkeypatch):
    fake = FakeStreamlit(click="Save K · Next: QB →")
    fake.session_state["turkey_edit_position"] = "K"
    service = FakeService()
    service.picks = [dict(position=p, pool_player_id=f"{p}-0")
                     for p in ("RB", "WR", "TE")]
    prepare(monkeypatch, fake)
    holiday._stage_starter("event-2026", "player-1", "K", "K-0")
    try:
        holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Saving K should advance to unsaved QB")
    assert service.saves == [("K", "K-0")]
    assert fake.session_state["turkey_next_position"] == "QB"
    assert fake.session_state.get(holiday._view_key("event-2026", "player-1")) != "review"


def test_review_view_is_scoped_to_correct_player(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(holiday, 'st', fake)
    holiday._set_view("event-2026", "player-A", "edit")
    assert holiday._current_view("event-2026", "player-A", complete=True, confirmed=True) == "edit"
    assert holiday._current_view("event-2026", "player-B", complete=True, confirmed=True) == "confirmed"
    assert holiday._current_view("event-2027", "player-A", complete=True, confirmed=True) == "confirmed"


def test_returning_to_sunday_clears_editing_state(monkeypatch):
    fake = FakeStreamlit(click="← Back to Sunday Pick’em")
    fake.session_state["turkey_bowl_open"] = True
    fake.session_state[holiday._view_key("event-2026", "player-1")] = "edit"
    monkeypatch.setattr(holiday, 'st', fake)
    monkeypatch.setattr(holiday, 'render_turkey_bowl', lambda *_:None)
    class Service:
        def __init__(self, store): pass
    monkeypatch.setattr(holiday, 'TurkeyBowlService', Service)
    event = {"id": "event-2026", "game_date": "2026-11-26"}
    try:
        holiday.render_home_card(object(), event, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Back button should navigate")
    assert fake.session_state["turkey_bowl_open"] is False
    assert holiday._view_key("event-2026", "player-1") not in fake.session_state


def test_home_button_turns_into_live_standings_at_lock_and_final_after_awards(monkeypatch):
    """The single Sunday-card button must reflect the Thursday event's own lock."""
    from datetime import datetime as RealDateTime
    fake = FakeStreamlit()
    monkeypatch.setattr(holiday, 'st', fake)

    class ThanksgivingClock(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            return RealDateTime(2026, 11, 26, 12, 59, tzinfo=tz)

    class Service:
        def __init__(self, store):
            pass

    monkeypatch.setattr(holiday, 'datetime', ThanksgivingClock)
    monkeypatch.setattr(holiday, 'TurkeyBowlService', Service)
    monkeypatch.setattr(holiday, 'is_locked', lambda event: bool(event.get('_locked')))
    monkeypatch.setattr(holiday, 'is_open', lambda event: True)
    # The card's divider is an existing Streamlit control, not a database write.
    fake.divider = lambda: None
    event = {'id': 'holiday', 'game_date': '2026-11-26',
             'locks_at': '2026-11-26T13:00:00-05:00'}

    assert holiday.render_home_card(object(), event, {'id': 'player'}) is False
    assert fake.buttons[-1][0] == '🦃 Open Turkey Bowl'
    assert fake.buttons[-1][1]['type'] == 'primary'
    assert fake.buttons[-1][1]['key'] == 'turkey_open_from_sunday'

    fake.buttons.clear()
    event['_locked'] = True
    assert holiday.render_home_card(object(), event, {'id': 'player'}) is False
    assert fake.buttons[-1][0] == '🦃 Click here for Live Turkey Day standings!'
    assert fake.buttons[-1][1]['type'] == 'primary'
    assert fake.buttons[-1][1]['key'] == 'turkey_open_from_sunday'

    fake.buttons.clear()
    event['finalized_at'] = '2026-11-27T14:01:00Z'
    assert holiday.render_home_card(object(), event, {'id': 'player'}) is False
    assert fake.buttons[-1][0] == '🏆 View final Turkey Bowl standings'


def test_live_button_keeps_existing_sunday_to_turkey_navigation(monkeypatch):
    from datetime import datetime as RealDateTime
    fake = FakeStreamlit(click='🦃 Click here for Live Turkey Day standings!')
    class StreamlitSessionState(dict):
        __setattr__ = dict.__setitem__
    fake.session_state = StreamlitSessionState()
    monkeypatch.setattr(holiday, 'st', fake)

    class ThanksgivingClock(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            return RealDateTime(2026, 11, 26, 13, 1, tzinfo=tz)

    class Service:
        def __init__(self, store):
            pass

    monkeypatch.setattr(holiday, 'datetime', ThanksgivingClock)
    monkeypatch.setattr(holiday, 'TurkeyBowlService', Service)
    monkeypatch.setattr(holiday, 'is_locked', lambda _: True)
    fake.divider = lambda: None
    event = {'id': 'holiday', 'game_date': '2026-11-26',
             'locks_at': '2026-11-26T13:00:00-05:00'}
    try:
        holiday.render_home_card(object(), event, {'id': 'player'})
    except Rerun:
        pass
    else:
        raise AssertionError('Expected the unchanged destination navigation to rerun')
    assert fake.session_state['turkey_bowl_open'] is True


def test_locked_view_puts_standings_above_locked_lineup_without_changing_scoring(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(holiday, 'st', fake)
    service = FakeService()
    service.picks = [dict(position='QB', pool_player_id='QB-0')]
    # Observe render order, without requiring live network or scoring.
    monkeypatch.setattr(
        holiday, '_live_scores',
        lambda *args, **kwargs: fake.messages.append(('standings', ('leaderboard',))))
    holiday._locked_view(service, {'id': 'event-2026', 'refreshed_at': None},
                         {'id': 'player-1'})
    labels = [kind for kind, _ in fake.messages]
    assert labels[0] == 'standings'
    assert any('Your locked Thanksgiving five' in str(args)
               for kind, args in fake.messages if kind == 'markdown')
    assert sum(kind == 'standings' for kind in labels) == 1
    assert any('QB 0' in str(args) for kind, args in fake.messages if kind == 'markdown')
    assert 'emergency' not in str(fake.messages).lower()

# Holiday archive placement: after the Sunday following Thanksgiving, the card
# moves below weekly content but stays available beyond the old December expiry.
def test_turkey_archive_moves_monday_after_thanksgiving():
    from datetime import date
    event = {"game_date": "2026-11-26"}
    assert not holiday.home_card_moves_below_sunday(event, today=date(2026, 11, 26))
    assert not holiday.home_card_moves_below_sunday(event, today=date(2026, 11, 29))
    assert holiday.home_card_moves_below_sunday(event, today=date(2026, 11, 30))
    assert holiday.home_card_moves_below_sunday(event, today=date(2026, 12, 6))


def test_final_turkey_link_still_renders_after_old_expiry(monkeypatch):
    from datetime import datetime

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 12, 10, 12, tzinfo=tz)

    fake = FakeStreamlit()
    fake.divider = lambda: fake.messages.append(("divider", ()))
    monkeypatch.setattr(holiday, "st", fake)
    monkeypatch.setattr(holiday, "datetime", FrozenDatetime)
    monkeypatch.setattr(holiday, "TurkeyBowlService", lambda store: None)
    event = {"id": "holiday", "game_date": "2026-11-26", "locks_at": "2026-11-26T13:00:00-05:00",
             "finalized_at": "2026-11-27T10:00:00-05:00"}
    assert holiday.render_home_card(None, event, {"id": "p1"}) is False
    assert "🏆 View final Turkey Bowl standings" in [label for label, _ in fake.buttons]


def _holiday_placement_screen(monkeypatch, *, archived: bool, phase: str, opening: bool = False):
    """Execute the real Sunday page function with isolated UI/store dependencies."""
    import ast
    from pathlib import Path
    import types

    path = Path(__file__).resolve().parents[1] / "weekly_ui.py"
    module_ast = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(node for node in module_ast.body
                    if isinstance(node, ast.FunctionDef) and node.name == "render_player_game")
    namespace = {}
    calls = []

    class Session(dict):
        def __getattr__(self, key):
            return self[key]
        def __setattr__(self, key, val):
            self[key] = val

    screen = types.SimpleNamespace(
        session_state=Session(turkey_bowl_open=opening),
        markdown=lambda *a, **kw: calls.append("sunday_content"),
        caption=lambda *a, **kw: calls.append("sunday_content"),
        divider=lambda: calls.append("divider"),
        info=lambda *a, **kw: calls.append("sunday_content"),
    )
    monkeypatch.setattr(holiday, "home_card_moves_below_sunday", lambda event: archived)

    def show_holiday(store, event, player):
        calls.append("turkey_card")
        return opening

    monkeypatch.setattr(holiday, "render_home_card", show_holiday)
    import turkey_bowl
    monkeypatch.setattr(turkey_bowl, "TurkeyBowlService", lambda store: types.SimpleNamespace(event=lambda season: {"game_date": "2026-11-26"}))

    namespace.update(
        st=screen,
        _take_lineup_action=lambda player: None,
        _onboarding=lambda *a: False,
        render_gate4_demo=lambda player: None,
        render_nav=lambda **kw: "🏈 Sunday",
        week_phase=lambda week: week["phase"],
        maybe_recover_critical_automation=lambda store, week: (week, None),
        _week_header=lambda week: calls.append("week_header"),
        _countdown=lambda *a: calls.append("sunday_content"),
        et_label=lambda value: str(value),
        render_live_sunday=lambda *a, **kw: calls.append("sunday_live"),
        maybe_render_final_celebration=lambda *a: None,
        _lock_transition_guard=lambda *a: None,
        pool_is_ready=lambda pool: True,
        _open_home=lambda *a: calls.append("sunday_open_home"),
        _locked_home=lambda *a: calls.append("sunday_locked_home"),
        APP_VERSION="1.0.19",
    )
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    store = types.SimpleNamespace(
        get_real_week=lambda: {"id": "week13", "season": 2026, "is_demo": False,
                               "nfl_week": 13, "phase": phase, "label": "Week 13",
                               "opens_at": "2026-12-01", "locks_at": "2026-12-06"},
        get_week_pool=lambda week_id, visible_only=False: [],
    )
    namespace["render_player_game"](store, {"id": "p1"}, skip_onboarding=True)
    return calls


def test_turkey_card_featured_above_sunday_through_november_29(monkeypatch):
    calls = _holiday_placement_screen(monkeypatch, archived=False, phase="upcoming")
    assert calls.index("turkey_card") < calls.index("week_header")
    assert calls.count("turkey_card") == 1


def test_turkey_archive_below_upcoming_week(monkeypatch):
    calls = _holiday_placement_screen(monkeypatch, archived=True, phase="upcoming")
    assert calls.index("turkey_card") > calls.index("sunday_content")
    assert calls.count("turkey_card") == 1


def test_turkey_archive_below_live_sunday_standings(monkeypatch):
    calls = _holiday_placement_screen(monkeypatch, archived=True, phase="locked")
    assert calls.index("turkey_card") > calls.index("sunday_live")
    assert calls.count("turkey_card") == 1


def test_turkey_archive_below_open_sunday_lineup(monkeypatch):
    calls = _holiday_placement_screen(monkeypatch, archived=True, phase="open")
    assert calls.index("turkey_card") > calls.index("sunday_open_home")
    assert calls.count("turkey_card") == 1


def test_turkey_archive_still_opens_standalone_when_tapped(monkeypatch):
    calls = _holiday_placement_screen(monkeypatch, archived=True, phase="upcoming", opening=True)
    assert calls == ["turkey_card"]
