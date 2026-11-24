"""Turkey Bowl tile-picker regression: staging only, separate from Sunday, safe saves."""
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def columns(self, *args, **kwargs):
        return self, self

    def segmented_control(self, label, options, *, default=None, key=None):
        return self.session_state.get(key, default)

    def button(self, label, *args, **kwargs):
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

    def pool(self, event_id, *, visible_only=False):
        return [r for r in self.rows if r["is_visible"]] if visible_only else list(self.rows)

    def lineup(self, event_id, player_id):
        return ({"id": "fake-lineup", "confirmed_at": None} if self.picks else None, list(self.picks))

    def save_pick(self, event, player_id, pos, starter, backup):
        self.saves.append((pos, starter, backup))
        self.picks = [p for p in self.picks if p["position"] != pos] + [
            {"position": pos, "pool_player_id": starter, "emergency_pool_player_id": backup}]

    def confirm(self, event, player_id):
        self.confirmations.append(player_id)


def test_new_starter_clears_previous_backup_without_touching_sunday(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(holiday, "st", fake)
    saved = {"pool_player_id": "QB-0", "emergency_pool_player_id": "QB-1"}
    candidates = {f"QB-{i}": {} for i in range(5)}
    assert holiday._draft_selection("holiday", "user", "QB", saved, candidates) == ("QB-0", "QB-1")
    holiday._stage_starter("holiday", "user", "QB", "QB-2")
    assert holiday._draft_selection("holiday", "user", "QB", saved, candidates) == ("QB-2", "")
    holiday._stage_backup("holiday", "user", "QB", "QB-3")
    assert holiday._draft_selection("holiday", "user", "QB", saved, candidates) == ("QB-2", "QB-3")
    holiday._stage_backup("holiday", "user", "QB", "")
    assert holiday._draft_selection("holiday", "user", "QB", saved, candidates) == ("QB-2", "")
    assert all(key.startswith("turkey_draft::") for key in fake.session_state)
    holiday._clear_draft("holiday", "user", "QB")
    assert fake.session_state == {}


def test_tile_stage_then_explicit_position_save_and_advance(monkeypatch):
    fake = FakeStreamlit()
    fake.session_state["turkey_edit_position"] = "QB"
    service = FakeService()
    monkeypatch.setattr(holiday, "st", fake)
    monkeypatch.setattr(holiday, "_turkey_player_tile", lambda row, **kw: fake.tiles.append((row, kw)))
    import weekly_ui
    monkeypatch.setattr(weekly_ui, "_stable_order", lambda pid, eid, pos, rows: rows)
    event, player = {"id": "event-2026"}, {"id": "player-1"}

    # Render shows exactly five real tile positions; no database writes.
    holiday._lineup_picker(service, event, player)
    assert len(fake.tiles) == 5 and len(service.saves) == 0
    holiday._stage_starter("event-2026", "player-1", "QB", "QB-0")
    fake.click = "Next: Emergency Backup →"
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Expected rerun into the backup tile step")
    assert len(service.saves) == 0

    fake.click = ""
    fake.tiles.clear()
    holiday._lineup_picker(service, event, player)
    assert len(fake.tiles) == 4  # four alternate backup tiles
    assert all(kw["as_backup"] for _, kw in fake.tiles)
    holiday._stage_backup("event-2026", "player-1", "QB", "QB-1")
    fake.click = "Save QB · Next: RB →"
    try:
        holiday._lineup_picker(service, event, player)
    except Rerun:
        pass
    else:
        raise AssertionError("Expected rerun after save")
    assert service.saves == [("QB", "QB-0", "QB-1")]
    assert fake.session_state["turkey_next_position"] == "RB"

    fake.click = ""
    holiday._lineup_picker(service, event, player)
    assert fake.session_state["turkey_edit_position"] == "RB"
    assert len(service.saves) == 1


def test_save_unchanged_pick_does_not_write_or_invalidate_confirmation(monkeypatch):
    fake = FakeStreamlit(click="Save QB · Next: RB →")
    fake.session_state["turkey_edit_position"] = "QB"
    fake.session_state[holiday._draft_key("event-2026", "player-1", "QB", "step")] = "backup"
    service = FakeService()
    service.picks = [{"position": "QB", "pool_player_id": "QB-0", "emergency_pool_player_id": "QB-1"}]
    monkeypatch.setattr(holiday, "st", fake)
    monkeypatch.setattr(holiday, "_turkey_player_tile", lambda row, **kwargs: None)
    import weekly_ui
    monkeypatch.setattr(weekly_ui, "_stable_order", lambda pid, eid, pos, rows: rows)
    try:
        holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Expected navigation rerun")
    assert not service.saves


def test_reuses_sunday_native_tile_helper_and_no_player_dropdown():
    tile_source = inspect.getsource(holiday._turkey_player_tile)
    picker_source = inspect.getsource(holiday._lineup_picker)
    assert "from weekly_ui import _render_player_card_button" in tile_source
    assert "_render_player_card_button(" in tile_source
    assert "st.selectbox(" not in picker_source
    assert "service.save_pick(" in picker_source
    assert "service.confirm(" in picker_source


def test_confirm_complete_lineup_without_overwriting_picks(monkeypatch):
    fake = FakeStreamlit(click="✅ Confirm my Turkey Bowl lineup")
    fake.session_state["turkey_edit_position"] = "K"
    service = FakeService()
    service.picks = [dict(position=pos, pool_player_id=f"{pos}-0", emergency_pool_player_id=None)
                     for pos in ("QB", "RB", "WR", "TE", "K")]
    monkeypatch.setattr(holiday, "st", fake)
    monkeypatch.setattr(holiday, "_turkey_player_tile", lambda row, **kwargs: None)
    import weekly_ui
    monkeypatch.setattr(weekly_ui, "_stable_order", lambda pid, eid, pos, rows: rows)
    try:
        holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    except Rerun:
        pass
    else:
        raise AssertionError("Expected confirmation rerun")
    assert service.confirmations == ["player-1"]
    assert not service.saves


def test_out_visible_player_stays_visible_but_is_not_eligible(monkeypatch):
    fake = FakeStreamlit(click="Next: Emergency Backup →")
    fake.session_state["turkey_edit_position"] = "QB"
    service = FakeService()
    service.rows[0]["availability_status"] = "OUT"
    monkeypatch.setattr(holiday, "st", fake)
    monkeypatch.setattr(holiday, "_turkey_player_tile", lambda row, **kw: fake.tiles.append((row, kw)))
    import weekly_ui
    monkeypatch.setattr(weekly_ui, "_stable_order", lambda pid, eid, pos, rows: rows)
    holiday._lineup_picker(service, {"id": "event-2026"}, {"id": "player-1"})
    assert len(fake.tiles) == 5
    assert sum(row["availability_status"] == "OUT" for row, kw in fake.tiles) == 1
    assert not service.saves  # Missing starter cannot advance or create a pick
