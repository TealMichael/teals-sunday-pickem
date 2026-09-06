from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from config import LOGIN_WINDOW_MINUTES, MAX_FAILED_LOGINS_PER_WINDOW
from weekly import POSITIONS, parse_timestamp, safe_status


UTC = timezone.utc
PICKEM_SCHEMA = "pickem"


class StoreError(RuntimeError):
    pass


class NicknameTaken(StoreError):
    pass


class LoginRateLimited(StoreError):
    pass


class PicksLocked(StoreError):
    pass


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


class SupabaseStore:
    def __init__(self, url: str, service_key: str):
        from supabase import create_client
        from supabase.client import ClientOptions

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

    # -------------------------
    # Gate 1 player/auth data
    # -------------------------
    def nickname_exists(self, nickname_key: str) -> bool:
        try:
            res = self._table("players").select("id").eq("nickname_key", nickname_key).limit(1).execute()
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
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                raise NicknameTaken("That nickname is already taken.") from exc
            raise StoreError("Could not create player. Try again.") from exc

    def get_player_by_nickname_key(self, nickname_key: str) -> dict[str, Any] | None:
        res = (
            self._table("players")
            .select("id,nickname,nickname_key,emoji,pin_salt,pin_hash,created_at,last_seen_at,onboarding_completed_at")
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
            .select("id,nickname,nickname_key,emoji,created_at,last_seen_at,onboarding_completed_at")
            .eq("id", str(player_id))
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def touch_player(self, player_id: str) -> None:
        self._table("players").update({"last_seen_at": _iso(datetime.now(UTC))}).eq("id", player_id).execute()

    def complete_onboarding(self, player_id: str) -> dict[str, Any] | None:
        stamp = _iso(datetime.now(UTC))
        self._table("players").update({"onboarding_completed_at": stamp}).eq("id", player_id).execute()
        return self.get_player_by_id(player_id)

    def update_player_emoji(self, player_id: str, emoji: str) -> dict[str, Any] | None:
        self._table("players").update({"emoji": emoji}).eq("id", player_id).execute()
        return self.get_player_by_id(player_id)

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
        self._table("login_attempts").insert({"nickname_key": nickname_key, "success": bool(success)}).execute()

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

    # -------------------------
    # Gate 2 weekly game data
    # -------------------------
    def get_real_week(self) -> dict[str, Any] | None:
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo")
            .eq("is_demo", False)
            .order("season", desc=True)
            .order("nfl_week", desc=False)
            .execute()
        )
        rows = list(res.data or [])
        if not rows:
            return None
        now = datetime.now(UTC)
        current_or_future = [r for r in rows if (parse_timestamp(r.get("locks_at")) or now) >= now]
        return (current_or_future or rows[-1:])[0]

    def get_demo_week(self) -> dict[str, Any] | None:
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo")
            .eq("is_demo", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_week(self, week_id: str) -> dict[str, Any] | None:
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo")
            .eq("id", week_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_week_pool(self, week_id: str) -> list[dict[str, Any]]:
        res = (
            self._table("player_pool")
            .select("id,week_id,position,slot_rank,player_name,team_abbr,opponent_abbr,kickoff_at,is_visible,availability_status")
            .eq("week_id", week_id)
            .order("position")
            .order("slot_rank")
            .execute()
        )
        return list(res.data or [])

    def get_lineup(self, week_id: str, player_id: str) -> dict[str, Any] | None:
        res = (
            self._table("lineups")
            .select("id,week_id,player_id,confirmed_at,created_at,updated_at")
            .eq("week_id", week_id)
            .eq("player_id", player_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_lineup_picks(self, lineup_id: str | None) -> list[dict[str, Any]]:
        if not lineup_id:
            return []
        res = (
            self._table("lineup_picks")
            .select("id,lineup_id,position,pool_player_id,emergency_pool_player_id,updated_at")
            .eq("lineup_id", lineup_id)
            .execute()
        )
        return list(res.data or [])

    def ensure_lineup(self, week_id: str, player_id: str) -> dict[str, Any]:
        existing = self.get_lineup(week_id, player_id)
        if existing:
            return existing
        try:
            res = self._table("lineups").insert({"week_id": week_id, "player_id": player_id}).execute()
            return res.data[0]
        except Exception:
            # If two taps raced, re-read the authoritative unique row.
            existing = self.get_lineup(week_id, player_id)
            if existing:
                return existing
            raise

    def _assert_week_open_for_picks(self, week_id: str) -> dict[str, Any]:
        week = self.get_week(week_id)
        if not week:
            raise StoreError("This week is unavailable.")
        locks_at = parse_timestamp(week.get("locks_at"))
        if locks_at and datetime.now(UTC) >= locks_at:
            raise PicksLocked("Picks are locked for this week.")
        opens_at = parse_timestamp(week.get("opens_at"))
        if opens_at and datetime.now(UTC) < opens_at and not bool(week.get("is_demo")):
            raise StoreError("Picks are not open yet.")
        return week

    def save_pick(
        self,
        *,
        week_id: str,
        player_id: str,
        position: str,
        pool_player_id: str,
        emergency_pool_player_id: str | None = None,
    ) -> dict[str, Any]:
        if position not in POSITIONS:
            raise StoreError("Invalid lineup position.")
        self._assert_week_open_for_picks(week_id)

        pool = self.get_week_pool(week_id)
        by_id = {str(row["id"]): row for row in pool}
        starter = by_id.get(str(pool_player_id))
        if not starter or starter.get("position") != position or not bool(starter.get("is_visible")):
            raise StoreError("That player is not available for this position.")
        if safe_status(starter.get("availability_status")) == "OUT":
            raise StoreError("That player is OUT. Choose someone else.")

        emergency = None
        if emergency_pool_player_id:
            emergency = by_id.get(str(emergency_pool_player_id))
            if not emergency or emergency.get("position") != position or not bool(emergency.get("is_visible")):
                raise StoreError("That emergency backup is not available.")
            if str(emergency.get("id")) == str(starter.get("id")):
                raise StoreError("Your emergency backup must be a different player.")
            if safe_status(emergency.get("availability_status")) == "OUT":
                raise StoreError("That emergency backup is OUT. Choose someone else.")

        lineup = self.ensure_lineup(week_id, player_id)
        payload = {
            "lineup_id": str(lineup["id"]),
            "position": position,
            "pool_player_id": str(starter["id"]),
            "emergency_pool_player_id": str(emergency["id"]) if emergency else None,
            "updated_at": _iso(datetime.now(UTC)),
        }
        res = self._table("lineup_picks").upsert(payload, on_conflict="lineup_id,position").execute()
        return res.data[0]

    def set_emergency_backup(
        self,
        *,
        week_id: str,
        player_id: str,
        position: str,
        emergency_pool_player_id: str,
    ) -> dict[str, Any]:
        lineup = self.get_lineup(week_id, player_id)
        if not lineup:
            raise StoreError("Choose your starter first.")
        picks = self.get_lineup_picks(str(lineup["id"]))
        current = next((p for p in picks if p.get("position") == position), None)
        if not current:
            raise StoreError("Choose your starter first.")
        return self.save_pick(
            week_id=week_id,
            player_id=player_id,
            position=position,
            pool_player_id=str(current["pool_player_id"]),
            emergency_pool_player_id=emergency_pool_player_id,
        )

    def confirm_lineup(self, week_id: str, player_id: str) -> dict[str, Any]:
        self._assert_week_open_for_picks(week_id)
        lineup = self.ensure_lineup(week_id, player_id)
        stamp = _iso(datetime.now(UTC))
        res = (
            self._table("lineups")
            .update({"confirmed_at": stamp, "updated_at": stamp})
            .eq("id", str(lineup["id"]))
            .execute()
        )
        return res.data[0]
