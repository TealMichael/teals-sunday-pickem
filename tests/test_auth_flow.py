from datetime import datetime, timezone
import uuid

from auth import login_player, register_player, restore_from_cookie
from security import session_token_hash
from store import NicknameTaken


class MemoryStore:
    def __init__(self):
        self.players = {}
        self.sessions = {}
        self.failures = []

    def nickname_exists(self, key):
        return key in self.players

    def create_player(self, **row):
        if row["nickname_key"] in self.players:
            raise NicknameTaken("That nickname is already taken.")
        out = {"id": str(uuid.uuid4()), **row}
        self.players[row["nickname_key"]] = out
        return out

    def get_player_by_nickname_key(self, key):
        return self.players.get(key)

    def get_player_by_id(self, pid):
        for p in self.players.values():
            if p["id"] == pid:
                return {k:v for k,v in p.items() if k not in {"pin_hash","pin_salt"}}
        return None

    def ensure_login_allowed(self, key):
        return None

    def record_login_attempt(self, key, success):
        self.failures.append((key, success))

    def touch_player(self, pid):
        return None

    def create_session(self, *, player_id, token_hash, expires_at):
        sid = str(uuid.uuid4())
        self.sessions[sid] = {"id":sid,"player_id":player_id,"token_hash":token_hash,"expires_at":expires_at.isoformat(),"revoked_at":None,"last_used_at":datetime.now(timezone.utc).isoformat()}
        return sid

    def get_session(self, sid):
        return self.sessions.get(sid)

    def touch_session(self, sid):
        return None


def test_register_login_and_restore_cookie():
    store = MemoryStore()
    r = register_player(store, nickname="TealDuck", emoji="🦆", pin="1234", pin_confirm="1234", pin_pepper="pinpep", session_pepper="sesspep", remember=True)
    assert r.ok and r.cookie_value
    assert login_player(store, nickname="tealduck", pin="1234", pin_pepper="pinpep", session_pepper="sesspep", remember=False).ok
    restored = restore_from_cookie(store, r.cookie_value, session_pepper="sesspep")
    assert restored.ok
    assert restored.player["nickname"] == "TealDuck"


def test_duplicate_nickname_is_case_insensitive():
    store = MemoryStore()
    a = register_player(store, nickname="TealDuck", emoji="🦆", pin="1234", pin_confirm="1234", pin_pepper="p", session_pepper="s", remember=False)
    b = register_player(store, nickname="tealduck", emoji="🏈", pin="4321", pin_confirm="4321", pin_pepper="p", session_pepper="s", remember=False)
    assert a.ok
    assert not b.ok


def test_wrong_pin_fails():
    store = MemoryStore()
    register_player(store, nickname="TealDuck", emoji="🦆", pin="1234", pin_confirm="1234", pin_pepper="p", session_pepper="s", remember=False)
    result = login_player(store, nickname="TealDuck", pin="9999", pin_pepper="p", session_pepper="s", remember=False)
    assert not result.ok
