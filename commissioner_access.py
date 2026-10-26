"""Server-side link between Mike T.'s player identity and Commissioner tools.

The owner link and device approvals live in the existing service-role-only
``pickem.app_meta`` table, so this feature requires no new SQL migration.
Each approved browser has its own revocable player session; knowing a nickname
or merely choosing the Commissioner navigation item grants no privileges.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hmac
from uuid import UUID

from config import COMMISH_PIN_LENGTH
from security import safe_secret_match, session_token_hash


UTC = timezone.utc
COMMISSIONER_ACCESS_SCHEMA_VERSION = 1
OWNER_META_KEY = "commissioner_owner:v1"
TRUST_META_PREFIX = "commissioner_device:v1:"
INITIAL_OWNER_NICKNAME = "mike t."


def _player_id(player: dict | None) -> str:
    candidate = str((player or {}).get("id") or "")
    try:
        return str(UUID(candidate))
    except (ValueError, TypeError):
        return ""


def _owner_id(store) -> str:
    row = store.get_app_meta(OWNER_META_KEY)
    if row is None:
        return ""
    value = row.get("value") or {}
    try:
        return str(UUID(str(value.get("player_id") or "")))
    except (ValueError, TypeError, AttributeError) as exc:
        # A malformed existing owner record is not an invitation to relink.
        raise ValueError("Commissioner owner link is invalid") from exc


def commissioner_tab_available(store, player: dict | None) -> bool:
    """Only the linked ID, or Mike T. before first linking, sees the tab."""
    player_id = _player_id(player)
    if not player_id:
        return False
    nickname = str((player or {}).get("nickname") or "").strip().casefold()
    # Nicknames cannot be edited in the current game. Skipping the role lookup
    # for everybody else avoids a new Supabase read on every player rerun.
    if nickname != INITIAL_OWNER_NICKNAME:
        return False
    owner_id = _owner_id(store)
    if owner_id:
        return hmac.compare_digest(owner_id, player_id)
    return True


def _valid_player_session(store, player: dict, token: str, session_pepper: str) -> str:
    """Validate full bearer token, player ownership, revocation and expiry."""
    if not token or not session_pepper:
        return ""
    try:
        session_id, secret = token.split(".", 1)
        session_id = str(UUID(session_id))
    except (ValueError, TypeError):
        return ""
    if not secret or not _player_id(player):
        return ""
    session = store.get_session(session_id)
    if not session or session.get("revoked_at"):
        return ""
    if str(session.get("player_id") or "") != _player_id(player):
        return ""
    try:
        expiry = datetime.fromisoformat(str(session["expires_at"]).replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(UTC):
            return ""
    except (KeyError, ValueError, TypeError):
        return ""
    expected = session_token_hash(secret, session_pepper)
    if not hmac.compare_digest(expected, str(session.get("token_hash") or "")):
        return ""
    return session_id


def commissioner_device_trusted(store, player: dict, *, token: str, session_pepper: str) -> bool:
    """Fail closed if either the owner mapping or remembered session changed."""
    if not _player_id(player) or str(player.get("nickname") or "").strip().casefold() != INITIAL_OWNER_NICKNAME:
        return False
    if _owner_id(store) != _player_id(player):
        return False
    session_id = _valid_player_session(store, player, token, session_pepper)
    if not session_id:
        return False
    record = store.get_app_meta(TRUST_META_PREFIX + session_id) or {}
    trusted = (record.get("value") or {}).get("player_id")
    return str(trusted or "") == _player_id(player)


def approve_commissioner_device(
    store,
    player: dict,
    *,
    entered_pin: str,
    expected_pin: str,
    token: str,
    session_pepper: str,
) -> bool:
    """Verify admin PIN with throttling, link owner, and trust this device.

    For a player who chose not to be remembered, successful verification is
    session-only; the caller can retain it in its Streamlit session state.
    """
    if not commissioner_tab_available(store, player):
        return False
    player_id = _player_id(player)
    attempt_key = f"commissioner_unlock:{player_id}"
    store.ensure_login_allowed(attempt_key)
    pin_valid = (
        len(str(entered_pin)) == COMMISH_PIN_LENGTH
        and str(entered_pin).isascii()
        and str(entered_pin).isdecimal()
        and safe_secret_match(str(entered_pin), str(expected_pin))
    )
    store.record_login_attempt(attempt_key, bool(pin_valid))
    if not pin_valid:
        return False

    session_id = ""
    if token:
        session_id = _valid_player_session(store, player, token, session_pepper)
        if not session_id:
            return False

    # Account selection is deliberately not editable from a profile/nickname.
    # If already linked to anyone else, commissioner_tab_available denied it.
    if not _owner_id(store):
        store.set_app_meta(OWNER_META_KEY, {"player_id": player_id, "linked_at": datetime.now(UTC).isoformat()})
    if _owner_id(store) != player_id:
        return False
    if session_id:
        store.set_app_meta(
            TRUST_META_PREFIX + session_id,
            {"player_id": player_id, "verified_at": datetime.now(UTC).isoformat()},
        )
    return True
