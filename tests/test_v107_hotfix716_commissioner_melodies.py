"""Hotfix 7.16: sound is optional, week-scoped, and cannot interrupt Sunday text."""
from __future__ import annotations

from pathlib import Path
import re

import pytest

from clock_melodies import (
    MELODY_CHOICES, MELODY_TARGETS, get_week_melody, save_week_melody,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, store):
        self.store = store
        self.week = None
        self.payload = None

    def select(self, columns):
        assert columns == "week_id,enabled,target,tune"
        return self

    def eq(self, field, value):
        assert field == "week_id"
        self.week = value
        return self

    def limit(self, number):
        assert number == 1
        return self

    def upsert(self, payload, on_conflict):
        assert on_conflict == "week_id"
        self.payload = payload
        return self

    def execute(self):
        if self.store.unavailable:
            raise RuntimeError("optional melody table not installed")
        if self.payload is not None:
            self.store.rows[self.payload["week_id"]] = self.payload.copy()
            return _FakeResult([self.payload.copy()] if self.store.confirm else [])
        return _FakeResult([self.store.rows[self.week].copy()] if self.week in self.store.rows else [])


class _FakeStore:
    def __init__(self):
        self.rows = {}
        self.unavailable = False
        self.confirm = True
        self.tables = []

    def _table(self, name):
        self.tables.append(name)
        assert name == "clock_message_melodies"
        return _FakeQuery(self)


def test_new_weeks_default_off_and_happy_birthday_is_preloaded():
    store = _FakeStore()
    assert get_week_melody(store, "week-a") == {
        "week_id": "week-a", "enabled": False,
        "target": "welcome", "tune": "happy_birthday",
    }
    assert "Happy Birthday" == MELODY_CHOICES["happy_birthday"]
    assert set(MELODY_CHOICES) == {
        "happy_birthday", "jingle_bells", "twinkle_twinkle", "ode_to_joy", "celebration_chime",
    }
    assert set(MELODY_TARGETS) == {"welcome", "party", "custom"}
    assert store.tables == ["clock_message_melodies"]


def test_save_and_read_isolated_per_week_and_disabled_is_persisted():
    store = _FakeStore()
    save_week_melody(store, "week-a", enabled=True, target="custom", tune="ode_to_joy")
    save_week_melody(store, "week-b", enabled=True, target="welcome", tune="happy_birthday")
    assert get_week_melody(store, "week-a")["tune"] == "ode_to_joy"
    assert get_week_melody(store, "week-b")["target"] == "welcome"
    save_week_melody(store, "week-a", enabled=False, target="custom", tune="ode_to_joy")
    assert get_week_melody(store, "week-a")["enabled"] is False
    assert get_week_melody(store, "week-b")["enabled"] is True
    assert "updated_at" in store.rows["week-a"]
    assert set(store.tables) == {"clock_message_melodies"}


def test_absent_music_table_never_crashes_ordinary_commissioner_form():
    store = _FakeStore()
    store.unavailable = True
    assert get_week_melody(store, "week-a") is None


@pytest.mark.parametrize("target,tune", [
    ("scoreboard", "happy_birthday"),
    ("welcome", "custom-code"),
    ("", "happy_birthday"),
    ("custom", ""),
])
def test_only_allowlisted_choices_can_be_saved(target, tune):
    store = _FakeStore()
    with pytest.raises(ValueError):
        save_week_melody(store, "week-a", enabled=True, target=target, tune=tune)
    assert not store.tables


def test_database_must_confirm_write():
    store = _FakeStore()
    store.confirm = False
    with pytest.raises(RuntimeError, match="not confirmed"):
        save_week_melody(store, "week-a", enabled=True, target="welcome", tune="happy_birthday")


def test_bad_saved_values_cannot_break_form_options():
    store = _FakeStore()
    store.rows["w"] = {"week_id":"w", "enabled": True, "target": "invalid", "tune": "nonexistent"}
    result = get_week_melody(store, "w")
    assert result["target"] == "welcome" and result["tune"] == "happy_birthday"


def test_ui_only_adds_controls_under_message_form_and_saves_separately():
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")
    form = ui.split('with st.form("g5_clock_messages"):', 1)[1].split('st.markdown("##### Automatic Sunday broadcast")', 1)[0]
    assert '"Play a melody with a Commissioner message"' in form
    assert '"Play with which message?"' in form
    assert '"Choose a melody"' in form
    assert form.index('custom_text = st.text_area(') < form.index('"Play a melody with a Commissioner message"')
    assert 'disabled=not melody_ready' in form
    assert 'disabled=not melody_ready or not melody_enabled' not in form  # form checkboxes do not rerun until Save
    assert 'key=f"g5_clock_melody_enabled_{week[\'id\']}"' in form
    assert form.index('store.save_clock_week_settings(') < form.index('save_week_melody(')
    assert 'melody was NOT saved' in form
    assert 'if melody_ready:' in form
    assert 'refresh_clock_snapshot(store, week)' in form


def test_sql_is_additive_and_original_feed_is_called_first_without_mutation():
    sql = (ROOT / "db/011_optional_commissioner_melodies.sql").read_text("utf-8")
    assert "create table if not exists pickem.clock_message_melodies" in sql
    assert "on delete cascade" in sql
    assert "enable row level security" in sql
    assert "revoke all on table pickem.clock_message_melodies from public, anon, authenticated" in sql
    assert "grant all on table pickem.clock_message_melodies to service_role" in sql
    assert "create or replace function public.pickem_clock_feed(p_token text)" in sql
    assert "v_feed := pickem.clock_feed(p_token);" in sql
    assert "create or replace function pickem.clock_feed" not in sql
    assert "create or replace function public.pickem_clock_ack" not in sql
    assert "coalesce(v_feed->>'category', '') <> 'manual'" in sql
    assert "coalesce(v_feed->>'test', '') = 'true'" in sql
    assert "m.week_id = v_week::uuid" in sql
    assert "m.enabled = true" in sql and "m.target = v_target" in sql
    assert "return v_feed || jsonb_build_object('rtttl', v_rtttl);" in sql
    assert "exception when others then" in sql.lower()
    assert "return v_feed;" in sql
    assert sql.strip().endswith("notify pgrst, 'reload schema';")
    for forbidden in ("update pickem.lineups", "update pickem.players", "create or replace function pickem.clock_feed", "delete from pickem"):
        assert forbidden not in sql.lower()


def test_every_preset_is_rtttl_and_parser_compatible():
    sql = (ROOT / "db/011_optional_commissioner_melodies.sql").read_text("utf-8")
    sounds = re.findall(r"'([A-Za-z0-9]+:d=\d+,o=\d+,b=\d+:[a-gp0-9#.,]+)'", sql)
    assert len(sounds) == len(MELODY_CHOICES) == 5, sounds
    assert all(len(sound) < 240 for sound in sounds)
    for sound in sounds:
        title, defaults, notes = sound.split(":")
        assert 1 <= len(title) <= 10
        assert len(notes.split(",")) >= 6
        assert all(re.fullmatch(r"(?:1|2|4|8|16|32)?(?:[a-g](?:#)?|p)(?:[4-7])?\.?", note) for note in notes.split(","))


def test_berry_music_has_rich_first_and_silent_fallback_for_invalid_melody():
    ax = (ROOT / "awtrix/PickemSunday.ax").read_text("utf-8")
    assert '# @headless true' in ax
    assert '/rest/v1/rpc/pickem_clock_feed' in ax
    assert '/rest/v1/rpc/pickem_clock_ack' in ax
    assert 'data.find("category") == "manual" && data.find("test") != true' in ax
    assert ax.count('"soundRtttl": str(melody)') == 3
    rich = ax.split('if rich != nil', 1)[1].split('if !accepted\n      if color', 1)[0]
    assert rich.index('"soundRtttl": str(melody)') < rich.index('accepted = notify({"text": rich, "repeat": 1, "stack": true, "wakeup": true})')
    assert '"soundLoop"' not in ax
    assert '"loopSound"' not in ax
    assert 'self.last_event = event_id' in ax and 'self.ack(str(event_id))' in ax


def test_no_core_code_or_original_sql_migrations_touched_for_melody():
    # Distinct optional module/table and PUBLIC wrapper only; no league data path.
    for filename in ["nfl_scoring.py", "nfl_sync.py", "weekly.py", "weekly_ui.py", "clock_broadcast.py", "automation_recovery.py"]:
        assert "clock_melodies" not in (ROOT / filename).read_text("utf-8")
    sql = (ROOT / "db/011_optional_commissioner_melodies.sql").read_text("utf-8")
    assert '"p_token":' not in sql
    assert "token_hash" not in sql
