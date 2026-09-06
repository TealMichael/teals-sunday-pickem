from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config import REMEMBER_DAYS
from security import hash_pin, new_session_secret, session_token_hash, verify_pin
from validation import nickname_key, normalize_nickname, validate_nickname, validate_player_pin, validate_single_emoji

UTC = timezone.utc


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    message: str
    player: dict | None = None
    cookie_value: str | None = None


def register_player(store, *, nickname: str, emoji: str, pin: str, pin_confirm: str, pin_pepper: str, session_pepper: str, remember: bool) -> AuthResult:
    nickname = normalize_nickname(nickname)
    ok, msg = validate_nickname(nickname)
    if not ok:
        return AuthResult(False, msg)
    ok, msg = validate_single_emoji(emoji)
    if not ok:
        return AuthResult(False, msg)
    ok, msg = validate_player_pin(pin)
    if not ok:
        return AuthResult(False, msg)
    if pin != pin_confirm:
        return AuthResult(False, "Those PINs do not match.")

    digest = hash_pin(pin, pin_pepper)
    try:
        player = store.create_player(
            nickname=nickname,
            nickname_key=nickname_key(nickname),
            emoji=emoji,
            pin_salt=digest.salt_b64,
            pin_hash=digest.hash_b64,
        )
    except Exception as exc:
        message = str(exc) or "Could not create player."
        return AuthResult(False, message)

    cookie = _new_cookie(store, str(player["id"]), session_pepper) if remember else None
    return AuthResult(True, "Welcome to Teal's Sunday Pick'em!", player=player, cookie_value=cookie)


def login_player(store, *, nickname: str, pin: str, pin_pepper: str, session_pepper: str, remember: bool) -> AuthResult:
    key = nickname_key(nickname)
    if not key:
        return AuthResult(False, "Enter your nickname and PIN.")
    try:
        store.ensure_login_allowed(key)
    except Exception as exc:
        message = str(exc)
        if "Too many attempts" in message:
            return AuthResult(False, message)
        return AuthResult(False, "Sign in is temporarily unavailable. Try again.")
    except Exception:
        return AuthResult(False, "Sign in is temporarily unavailable. Try again.")

    try:
        player = store.get_player_by_nickname_key(key)
    except Exception:
        return AuthResult(False, "Sign in is temporarily unavailable. Try again.")

    valid = bool(player) and verify_pin(pin, pin_pepper, player["pin_salt"], player["pin_hash"])
    try:
        store.record_login_attempt(key, valid)
    except Exception:
        pass  # auth should not fail because diagnostic logging failed

    if not valid:
        return AuthResult(False, "Nickname or PIN is incorrect.")

    try:
        store.touch_player(str(player["id"]))
    except Exception:
        pass
    cookie = _new_cookie(store, str(player["id"]), session_pepper) if remember else None
    return AuthResult(True, "Signed in.", player=player, cookie_value=cookie)


def _new_cookie(store, player_id: str, session_pepper: str) -> str:
    secret = new_session_secret()
    token_hash = session_token_hash(secret, session_pepper)
    expires_at = datetime.now(UTC) + timedelta(days=REMEMBER_DAYS)
    session_id = store.create_session(player_id=player_id, token_hash=token_hash, expires_at=expires_at)
    return f"{session_id}.{secret}"


def restore_from_cookie(store, cookie_value: str, *, session_pepper: str) -> AuthResult:
    try:
        session_id, secret = cookie_value.split(".", 1)
    except ValueError:
        return AuthResult(False, "Invalid remembered session.")

    try:
        session = store.get_session(session_id)
    except Exception:
        # Important resilience behavior: caller should keep the cookie on transient DB failure.
        return AuthResult(False, "TEMPORARY_SESSION_CHECK_FAILURE")

    if not session or session.get("revoked_at"):
        return AuthResult(False, "Remembered session expired.")

    try:
        expires_at = datetime.fromisoformat(str(session["expires_at"]).replace("Z", "+00:00"))
    except Exception:
        return AuthResult(False, "Remembered session expired.")
    if expires_at <= datetime.now(UTC):
        return AuthResult(False, "Remembered session expired.")

    expected_hash = session_token_hash(secret, session_pepper)
    import hmac
    if not hmac.compare_digest(expected_hash, str(session["token_hash"])):
        return AuthResult(False, "Remembered session expired.")

    try:
        player = store.get_player_by_id(str(session["player_id"]))
    except Exception:
        return AuthResult(False, "TEMPORARY_SESSION_CHECK_FAILURE")
    if not player:
        return AuthResult(False, "Remembered session expired.")

    try:
        store.touch_session(session_id)
        store.touch_player(str(player["id"]))
    except Exception:
        pass
    return AuthResult(True, "Welcome back.", player=player, cookie_value=cookie_value)


def revoke_cookie_session(store, cookie_value: str | None) -> None:
    if not cookie_value:
        return
    try:
        session_id = cookie_value.split(".", 1)[0]
        store.revoke_session(session_id)
    except Exception:
        pass
