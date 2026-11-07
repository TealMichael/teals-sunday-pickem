"""Regression checks for the three-phase, privacy-safe Clock Schedule Manager."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from clock_schedule import DEFAULT_SLOTS, LIVE_CATEGORIES, PHASES, SAFE_PRELOCK, slot_label, validate_slots


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/017_clock_schedule_manager.sql").read_text("utf-8")
OLD_SQL = (ROOT / "db/016_clock_standings_shift_caleb_watch.sql").read_text("utf-8")


class ClockScheduleManagerTests(unittest.TestCase):
    def test_python_and_sql_defaults_match_existing_v117_rotation(self):
        for phase, config in PHASES.items():
            column = config["column"]
            match = re.search(
                rf"add column if not exists {column} jsonb not null\s+default '([^']+)'::jsonb",
                SQL,
            )
            self.assertIsNotNone(match, column)
            self.assertEqual(json.loads(match.group(1)), list(DEFAULT_SLOTS[phase]))
            self.assertEqual(len(DEFAULT_SLOTS[phase]), 60 // config["minutes"])
            self.assertEqual(slot_label(phase, 0), ":00")
            self.assertEqual(slot_label(phase, len(DEFAULT_SLOTS[phase]) - 1),
                             ":45" if phase == "saturday" else ":55")

        self.assertEqual(DEFAULT_SLOTS["live"][8], "caleb")  # :40
        self.assertEqual([i * 5 for i, category in enumerate(DEFAULT_SLOTS["live"])
                          if category == "weekly"], [5, 20, 35, 50])
        self.assertEqual([i * 5 for i, category in enumerate(DEFAULT_SLOTS["live"])
                          if category == "live_games"], [0, 15, 30, 45])

    def test_python_prelock_privacy_validation(self):
        for phase in ("saturday", "pregame"):
            self.assertEqual(validate_slots(phase, DEFAULT_SLOTS[phase]), list(DEFAULT_SLOTS[phase]))
            for private in ("weekly", "player", "pulse", "live_games"):
                invalid = list(DEFAULT_SLOTS[phase])
                invalid[0] = private
                with self.subTest(phase=phase, private=private), self.assertRaises(ValueError):
                    validate_slots(phase, invalid)
            self.assertEqual(set(PHASES[phase]["allowed"]), set(SAFE_PRELOCK))

    def test_validates_unknown_categories_and_slot_lengths(self):
        for phase, current in DEFAULT_SLOTS.items():
            with self.subTest(phase=phase):
                self.assertEqual(validate_slots(phase, current), list(current))
                for invalid in ([], list(current)[:-1], list(current) + ["off"]):
                    with self.assertRaises(ValueError):
                        validate_slots(phase, invalid)
                with self.assertRaises(ValueError):
                    validate_slots(phase, ["arbitrary"] + list(current)[1:])
        with self.assertRaises(ValueError):
            validate_slots("unknown", ["preview"])
        self.assertIn("weekly", LIVE_CATEGORIES)

    def test_database_constraints_reject_invalid_or_private_entries(self):
        for phase, config in PHASES.items():
            column = config["column"]
            check = re.search(rf"constraint clock_{column}_valid\s+check \((.*?)\);", SQL, re.S)
            self.assertIsNotNone(check, column)
            constraint = check.group(1)
            allowed = re.search(r"<@ '([^']+)'::jsonb", constraint)
            self.assertIsNotNone(allowed, column)
            self.assertEqual(set(json.loads(allowed.group(1))), set(config["allowed"]))
            self.assertIn(f"jsonb_array_length({column}) = {len(DEFAULT_SLOTS[phase])}", constraint)
            self.assertIn(f"jsonb_typeof({column}) = 'array'", constraint)

    def test_feed_blocks_private_prelock_categories_and_silences_off(self):
        saturday = SQL.split("if extract(dow from v_local)::integer = 6 then", 1)[1].split(
            "-- Sunday broadcast: begin", 1
        )[0]
        pregame = SQL.split("if now() < v_week.locks_at then", 1)[1].split(
            "else\n    -- Post-lock", 1
        )[0]
        for phase_sql in (saturday, pregame):
            self.assertIn("v_category not in ('preview', 'manual', 'readiness', 'season', 'caleb', 'off')", phase_sql)
            self.assertIn("if v_category = 'off' then", phase_sql)
            self.assertNotIn("v_payload->>'weekly'", phase_sql)
            self.assertNotIn("v_payload->'player_updates'", phase_sql)
        self.assertIn("v_control.saturday_slots", saturday)
        self.assertIn("v_control.pregame_slots", pregame)
        self.assertIn("v_control.live_slots", SQL)

    def test_device_token_and_test_clock_protections_unchanged(self):
        start = "begin\n  if coalesce(length(p_token), 0) < 20 then"
        end = "\n  v_local := timezone('America/New_York', now());"
        self.assertEqual(SQL.split(start, 1)[1].split(end, 1)[0],
                         OLD_SQL.split(start, 1)[1].split(end, 1)[0])
        self.assertIn("v_slot::text || ':saturday'", SQL)
        self.assertIn("case when now() < v_week.locks_at then 'pregame' else 'live' end", SQL)

    def test_commissioner_editor_only_and_no_new_nfl_refresh(self):
        ui = (ROOT / "gate5_ui.py").read_text("utf-8")
        store = (ROOT / "store.py").read_text("utf-8")
        self.assertIn("_render_clock_schedule_editor(store)", ui)
        self.assertIn('st.checkbox("Open Schedule Manager"', ui)
        self.assertIn("store.get_clock_schedules()", ui)
        self.assertIn("store.save_clock_schedule(phase, selections)", ui)
        self.assertIn("validate_slots(phase, slots)", store)
        self.assertIn('.eq("singleton", True)', store)
        self.assertNotIn("requests.", ui.split("def _render_clock_schedule_editor", 1)[1]
                         .split("def _render_clock", 1)[0])


if __name__ == "__main__":
    unittest.main()
