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

    def pool(self, event_id, *, visible_only=False):
        return [r for r in self.rows if r["is_visible"]] if visible_only else list(self.rows)

    def lineup(self, event_id, player_id):
        return ({"id": "fake-lineup", "confirmed_at": None} if self.picks else None, list(self.picks))

    def save_pick(self, event, player_id, pos, starter):
        self.saves.append((pos, starter))
        self.picks = [p for p in self.picks if p["position"] != pos] + [
            {"position": pos, "pool_player_id": starter}]

    def confirm(self, event, player_id):
        self.confirmations.append(player_id)


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
