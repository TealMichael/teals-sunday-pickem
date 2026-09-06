from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from config import LOGIN_WINDOW_MINUTES, MAX_FAILED_LOGINS_PER_WINDOW


UTC = timezone.utc
PICKEM_SCHEMA = "pickem"


class StoreError(RuntimeError):
    pass


class NicknameTaken(StoreError):
    pass


class LoginRateLimited(StoreError):
    pass


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


class SupabaseStore:
    def __init__(self, url: str, service_key: str):
        from supabase import create_client
        from supabase.client import ClientOptions

        # Keep the base client on public and choose the Pick'em schema explicitly
        # per query. This follows the current supabase-py custom-schema API and
        # avoids malformed PostgREST routing on shared projects.
        self.client = create_client(
            url,
            service_key,
            options=ClientOptions(
                postgrest_client_timeout=8,
                storage_client_timeout=8,
                auto_refresh_token=False,
                persist_session=False,
            ),
        )

    def _table(self, name: str):
        return self.client.schema(PICKEM_SCHEMA).table(name)

    def healthcheck(self) -> bool:
        try:
            self._table("app_meta").select("key").limit(1).execute()
            return True
        except Exception:
            return False

    def nickname_exists(self, nickname_key: str) -> bool:
        try:
            res = (
                self._table("players")
                .select("id")
                .eq("nickname_key", nickname_key)
                .limit(1)
                .execute()
            )
            return bool(res.data)
        except Exception as exc:
            raise StoreError("Player accounts are temporarily unavailable. Try again.") from exc

    def create_player(self, *, nickname: str, nickname_key: str, emoji: str, pin_salt: str, pin_hash: str) -> dict[str, Any]:
        if self.nickname_exists(nickname_key):
            raise NicknameTaken("That nickname is already taken.")
        try:
            res = self._table("players").insert({
                "nickname": nickname,
                "nickname_key": nickname_key,
                "emoji": emoji,
                "pin_salt": pin_salt,
                "pin_hash": pin_hash,
            }).execute()
            return res.data[0]
        except Exception as exc:
            # The DB unique constraint is authoritative for race conditions.
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                raise NicknameTaken("That nickname is already taken.") from exc
            raise StoreError("Could not create player. Try again.") from exc

    def get_player_by_nickname_key(self, nickname_key: str) -> dict[str, Any] | None:
        res = (
            self._table("players")
            .select("id,nickname,nickname_key,emoji,pin_salt,pin_hash,created_at,last_seen_at")
            .eq("nickname_key", nickname_key)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_player_by_id(self, player_id: str) -> dict[str, Any] | None:
        try:
            UUID(str(player_id))
        except Exception:
            return None
        res = (
            self._table("players")
            .select("id,nickname,nickname_key,emoji,created_at,last_seen_at")
            .eq("id", str(player_id))
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def touch_player(self, player_id: str) -> None:
        self._table("players").update({"last_seen_at": _iso(datetime.now(UTC))}).eq("id", player_id).execute()

    def failed_attempts_in_window(self, nickname_key: str) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=LOGIN_WINDOW_MINUTES)
        res = (
            self._table("login_attempts")
            .select("id", count="exact")
            .eq("nickname_key", nickname_key)
            .eq("success", False)
            .gte("attempted_at", _iso(cutoff))
            .execute()
        )
        return int(res.count or 0)

    def ensure_login_allowed(self, nickname_key: str) -> None:
        if self.failed_attempts_in_window(nickname_key) >= MAX_FAILED_LOGINS_PER_WINDOW:
            raise LoginRateLimited("Too many attempts. Try again in a few minutes.")

    def record_login_attempt(self, nickname_key: str, success: bool) -> None:
        self._table("login_attempts").insert({
            "nickname_key": nickname_key,
            "success": bool(success),
        }).execute()

    def create_session(self, *, player_id: str, token_hash: str, expires_at: datetime) -> str:
        res = self._table("player_sessions").insert({
            "player_id": player_id,
            "token_hash": token_hash,
            "expires_at": _iso(expires_at),
        }).execute()
        return str(res.data[0]["id"])

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        try:
            UUID(str(session_id))
        except Exception:
            return None
        res = (
            self._table("player_sessions")
            .select("id,player_id,token_hash,expires_at,revoked_at,last_used_at")
            .eq("id", str(session_id))
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def touch_session(self, session_id: str) -> None:
        self._table("player_sessions").update({"last_used_at": _iso(datetime.now(UTC))}).eq("id", session_id).execute()

    def revoke_session(self, session_id: str) -> None:
        self._table("player_sessions").update({"revoked_at": _iso(datetime.now(UTC))}).eq("id", session_id).execute()

    def cleanup_old_login_attempts(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=2)
        self._table("login_attempts").delete().lt("attempted_at", _iso(cutoff)).execute()
