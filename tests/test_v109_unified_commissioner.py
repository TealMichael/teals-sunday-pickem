"""v1.0.9 regression checks for unified player/Commissioner access."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from uuid import uuid4

from commissioner_access import (
    OWNER_META_KEY,
    TRUST_META_PREFIX,
    approve_commissioner_device,
    commissioner_device_trusted,
    commissioner_tab_available,
)
from security import session_token_hash


ROOT = Path(__file__).resolve().parents[1]
PEPPER = "test-only-session-pepper"
ADMIN_PIN = "008741"


class FakeStore:
    def __init__(self):
        self.meta = {}
        self.sessions = {}
        self.attempts = []

    def get_app_meta(self, key):
        return {"key": key, "value": self.meta[key]} if key in self.meta else None

    def set_app_meta(self, key, value):
        self.meta[key] = dict(value)
        return self.get_app_meta(key)

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def ensure_login_allowed(self, nickname_key):
        if sum(1 for key, success in self.attempts if key == nickname_key and not success) >= 8:
            raise RuntimeError("rate limited")

    def record_login_attempt(self, nickname_key, success):
        self.attempts.append((nickname_key, bool(success)))

    def add_session(self, player, *, days=2):
        session_id = str(uuid4())
        bearer = "random-session-secret-" + str(uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "player_id": player["id"],
            "token_hash": session_token_hash(bearer, PEPPER),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
            "revoked_at": None,
        }
        return f"{session_id}.{bearer}"


class UnifiedCommissionerAccessTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.mike = {"id": str(uuid4()), "nickname": "Mike T."}
        self.other = {"id": str(uuid4()), "nickname": "Jenny"}
        self.token = self.store.add_session(self.mike)

    def approve(self, token=None, pin=ADMIN_PIN, player=None):
        return approve_commissioner_device(
            self.store,
            self.mike if player is None else player,
            entered_pin=pin,
            expected_pin=ADMIN_PIN,
            token=self.token if token is None else token,
            session_pepper=PEPPER,
        )

    def trusted(self, token=None, player=None):
        return commissioner_device_trusted(
            self.store,
            self.mike if player is None else player,
            token=self.token if token is None else token,
            session_pepper=PEPPER,
        )

    def test_only_mike_t_can_initially_see_tab(self):
        self.assertTrue(commissioner_tab_available(self.store, self.mike))
        self.assertFalse(commissioner_tab_available(self.store, self.other))
        self.assertFalse(commissioner_tab_available(self.store, {"nickname": "Mike T."}))

    def test_wrong_pin_does_not_link_or_trust(self):
        self.assertFalse(self.approve(pin="000000"))
        self.assertNotIn(OWNER_META_KEY, self.store.meta)
        self.assertFalse(self.trusted())
        self.assertEqual(len(self.store.attempts), 1)

    def test_correct_pin_links_by_immutable_id_and_trusts_only_this_device(self):
        self.assertTrue(self.approve())
        self.assertEqual(self.store.meta[OWNER_META_KEY]["player_id"], self.mike["id"])
        self.assertTrue(self.trusted())

        second_token = self.store.add_session(self.mike)
        self.assertFalse(self.trusted(token=second_token))
        self.assertTrue(self.approve(token=second_token))
        self.assertTrue(self.trusted(token=second_token))
        self.assertIn(TRUST_META_PREFIX + second_token.split(".")[0], self.store.meta)

        # No player with a lookalike nickname can inherit the linked ID.
        impostor = {"id": self.other["id"], "nickname": "Mike T."}
        self.assertFalse(commissioner_tab_available(self.store, impostor))
        self.assertFalse(self.approve(player=impostor))

    def test_expired_revoked_and_modified_sessions_are_denied(self):
        self.assertTrue(self.approve())
        session_id = self.token.split(".")[0]
        self.assertFalse(self.trusted(token=self.token + "modified"))
        self.store.sessions[session_id]["revoked_at"] = datetime.now(timezone.utc).isoformat()
        self.assertFalse(self.trusted())
        self.store.sessions[session_id]["revoked_at"] = None
        self.store.sessions[session_id]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        self.assertFalse(self.trusted())

    def test_invalid_session_never_links_even_with_correct_admin_pin(self):
        self.assertFalse(self.approve(token="invalid-session-token"))
        self.assertNotIn(OWNER_META_KEY, self.store.meta)

    def test_unremembered_player_can_verify_for_current_session_only(self):
        self.assertTrue(self.approve(token=""))
        self.assertFalse(self.trusted(token=""))

    def test_malformed_owner_record_fails_closed(self):
        self.store.meta[OWNER_META_KEY] = {"player_id": "not-a-uuid"}
        with self.assertRaises(ValueError):
            commissioner_tab_available(self.store, self.mike)

    def test_eight_bad_pins_are_throttled(self):
        for _ in range(8):
            self.assertFalse(self.approve(pin="111111"))
        with self.assertRaises(RuntimeError):
            self.approve(pin=ADMIN_PIN)

    def test_navigation_and_all_six_existing_sections_remain_available(self):
        nav = (ROOT / "gate4_ui.py").read_text("utf-8")
        game = (ROOT / "weekly_ui.py").read_text("utf-8")
        app = (ROOT / "app.py").read_text("utf-8")
        dashboard = (ROOT / "gate5_ui.py").read_text("utf-8")
        self.assertIn('options.append("🛡️ Commissioner")', nav)
        self.assertIn('render_nav(include_commissioner=commissioner_available)', game)
        self.assertIn('on_commissioner=_render_linked_commissioner if eligible else None', app)
        self.assertIn('commissioner_device_trusted(', app)
        self.assertIn('commissioner_tools = ["Week", "Newsletter", "Players", "Corrections", "Clock", "Diagnostics"]', dashboard)
        for function in (
            "_render_week_overview", "_render_newsletter", "_render_players",
            "_render_corrections", "_render_clock", "_render_diagnostics",
        ):
            self.assertIn(function + "(store, week", dashboard)


if __name__ == "__main__":
    unittest.main()
