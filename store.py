from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
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

        self._public_cache: dict[tuple, tuple[float, Any]] = {}
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

    def _cache_get(self, key: tuple) -> Any | None:
        cache = getattr(self, "_public_cache", None)
        if not cache:
            return None
        item = cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.monotonic() >= expires_at:
            cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: tuple, value: Any, ttl_seconds: float) -> Any:
        cache = getattr(self, "_public_cache", None)
        if cache is None:
            cache = {}
            self._public_cache = cache
        cache[key] = (time.monotonic() + ttl_seconds, value)
        return value

    def clear_week_cache(self, week_id: str | None = None) -> None:
        cache = getattr(self, "_public_cache", None)
        if not cache:
            return
        if week_id is None:
            cache.clear()
            return
        week_id = str(week_id)
        for key in list(cache):
            if week_id in {str(part) for part in key}:
                cache.pop(key, None)

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
            self._public_cache.pop(("registered_players",), None)
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
        self._public_cache.pop(("registered_players",), None)
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
        cache_key = ("real_week",)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo,data_status,last_data_refresh_at,finalized_at,data_message,results_archived_at,rosters_purged_at")
            .eq("is_demo", False)
            .order("season", desc=True)
            .order("nfl_week", desc=False)
            .execute()
        )
        rows = list(res.data or [])
        if not rows:
            return self._cache_set(cache_key, None, 15)
        now = datetime.now(UTC)
        # Keep the just-finished Sunday as the current app week through Monday.
        # The next shell may already exist, but it should not take over until
        # its Tuesday-noon open time actually arrives.
        opened = [r for r in rows if (parse_timestamp(r.get("opens_at")) or now) <= now]
        if opened:
            value = sorted(opened, key=lambda r: (int(r.get("season") or 0), int(r.get("nfl_week") or 0)))[-1]
        else:
            value = sorted(rows, key=lambda r: (parse_timestamp(r.get("opens_at")) or now))[0]
        return self._cache_set(cache_key, value, 30)

    def get_demo_week(self) -> dict[str, Any] | None:
        cache_key = ("demo_week",)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo,data_status,last_data_refresh_at,finalized_at,data_message,results_archived_at,rosters_purged_at")
            .eq("is_demo", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        value = res.data[0] if res.data else None
        return self._cache_set(cache_key, value, 60)

    def get_week(self, week_id: str) -> dict[str, Any] | None:
        cache_key = ("week", str(week_id))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo,data_status,last_data_refresh_at,finalized_at,data_message,results_archived_at,rosters_purged_at")
            .eq("id", week_id)
            .limit(1)
            .execute()
        )
        value = res.data[0] if res.data else None
        return self._cache_set(cache_key, value, 30)

    def get_week_pool(self, week_id: str, *, visible_only: bool = True) -> list[dict[str, Any]]:
        cache_key = ("week_pool", str(week_id), bool(visible_only))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return list(cached)
        query = (
            self._table("player_pool")
            .select("id,week_id,position,slot_rank,player_name,team_abbr,opponent_abbr,kickoff_at,is_visible,availability_status")
            .eq("week_id", week_id)
        )
        if visible_only:
            query = query.eq("is_visible", True)
        res = query.order("position").order("slot_rank").execute()
        rows = list(res.data or [])
        self._cache_set(cache_key, rows, 20)
        return list(rows)

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

    def get_lineup_state(self, week_id: str, player_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Fetch a player's lineup and all five picks in one PostgREST round trip."""
        res = (
            self._table("lineups")
            .select(
                "id,week_id,player_id,confirmed_at,created_at,updated_at,"
                "lineup_picks(id,lineup_id,position,pool_player_id,emergency_pool_player_id,updated_at)"
            )
            .eq("week_id", week_id)
            .eq("player_id", player_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None, []
        row = dict(res.data[0])
        picks = list(row.pop("lineup_picks", []) or [])
        return row, picks

    def ensure_lineup(self, week_id: str, player_id: str) -> dict[str, Any]:
        # Normal UI calls pass an existing lineup id after the first pick. Avoid a
        # preflight SELECT on the first pick: try the insert and only re-read if
        # another device/session created the unique row first.
        try:
            res = self._table("lineups").insert({"week_id": week_id, "player_id": player_id}).execute()
            return res.data[0]
        except Exception:
            existing = self.get_lineup(week_id, player_id)
            if existing:
                return existing
            raise

    def _assert_week_value_open_for_picks(self, week: dict[str, Any] | None) -> dict[str, Any]:
        if not week:
            raise StoreError("This week is unavailable.")
        locks_at = parse_timestamp(week.get("locks_at"))
        if locks_at and datetime.now(UTC) >= locks_at:
            raise PicksLocked("Picks are locked for this week.")
        opens_at = parse_timestamp(week.get("opens_at"))
        if opens_at and datetime.now(UTC) < opens_at and not bool(week.get("is_demo")):
            raise StoreError("Picks are not open yet.")
        return week

    def _assert_week_open_for_picks(self, week_id: str) -> dict[str, Any]:
        return self._assert_week_value_open_for_picks(self.get_week(week_id))

    def save_pick(
        self,
        *,
        week_id: str,
        player_id: str,
        position: str,
        pool_player_id: str,
        emergency_pool_player_id: str | None = None,
        lineup_id: str | None = None,
        known_week: dict[str, Any] | None = None,
        known_pool: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if position not in POSITIONS:
            raise StoreError("Invalid lineup position.")
        week = self._assert_week_value_open_for_picks(known_week) if known_week is not None else self._assert_week_open_for_picks(week_id)

        # UI callers already have the current weekly pool. Reuse it instead of
        # downloading the same 25 visible player rows again on every tap. The
        # database trigger remains the authoritative guard for lock, position,
        # visibility, week membership, and OUT status.
        pool = known_pool if known_pool is not None else self.get_week_pool(week_id)
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

        if lineup_id:
            resolved_lineup_id = str(lineup_id)
        else:
            lineup = self.ensure_lineup(week_id, player_id)
            resolved_lineup_id = str(lineup["id"])

        payload = {
            "lineup_id": resolved_lineup_id,
            "position": position,
            "pool_player_id": str(starter["id"]),
            "emergency_pool_player_id": str(emergency["id"]) if emergency else None,
            "updated_at": _iso(datetime.now(UTC)),
        }
        res = self._table("lineup_picks").upsert(payload, on_conflict="lineup_id,position").execute()
        self.clear_week_cache(str(week_id))
        return res.data[0]

    def set_emergency_backup(
        self,
        *,
        week_id: str,
        player_id: str,
        position: str,
        emergency_pool_player_id: str,
        starter_pool_player_id: str | None = None,
        lineup_id: str | None = None,
        known_week: dict[str, Any] | None = None,
        known_pool: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if starter_pool_player_id and lineup_id:
            return self.save_pick(
                week_id=week_id,
                player_id=player_id,
                position=position,
                pool_player_id=str(starter_pool_player_id),
                emergency_pool_player_id=emergency_pool_player_id,
                lineup_id=str(lineup_id),
                known_week=known_week,
                known_pool=known_pool,
            )

        # Compatibility fallback for non-UI callers.
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
            lineup_id=str(lineup["id"]),
            known_week=known_week,
            known_pool=known_pool,
        )

    def confirm_lineup(
        self,
        week_id: str,
        player_id: str,
        *,
        lineup_id: str | None = None,
        known_week: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if known_week is not None:
            self._assert_week_value_open_for_picks(known_week)
        else:
            self._assert_week_open_for_picks(week_id)
        if lineup_id:
            resolved_lineup_id = str(lineup_id)
        else:
            lineup = self.ensure_lineup(week_id, player_id)
            resolved_lineup_id = str(lineup["id"])
        stamp = _iso(datetime.now(UTC))
        res = (
            self._table("lineups")
            .update({"confirmed_at": stamp, "updated_at": stamp})
            .eq("id", resolved_lineup_id)
            .execute()
        )
        self.clear_week_cache(str(week_id))
        return res.data[0]


    # -------------------------
    # Gate 3 NFL data / scheduler
    # -------------------------
    def get_week_by_season_week(self, season: int, nfl_week: int, *, is_demo: bool = False) -> dict[str, Any] | None:
        res = (
            self._table("weeks")
            .select("id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo,data_status,last_data_refresh_at,finalized_at,data_message,results_archived_at,rosters_purged_at")
            .eq("season", int(season))
            .eq("nfl_week", int(nfl_week))
            .eq("is_demo", bool(is_demo))
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def update_week_data_state(self, week_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"published_at", "data_status", "last_data_refresh_at", "finalized_at", "data_message", "results_archived_at", "rosters_purged_at"}
        payload = {key: value for key, value in fields.items() if key in allowed}
        if not payload:
            return self.get_week(str(week_id))
        res = self._table("weeks").update(payload).eq("id", str(week_id)).execute()
        self.clear_week_cache(str(week_id))
        return res.data[0] if res.data else None

    def upsert_nfl_games(self, week_id: str, games: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not games:
            return []
        stamp = _iso(datetime.now(UTC))
        payload = []
        for game in games:
            row = dict(game)
            row["week_id"] = str(week_id)
            row["provider_updated_at"] = stamp
            payload.append(row)
        res = self._table("nfl_games").upsert(payload, on_conflict="week_id,provider_event_id").execute()
        return list(res.data or [])

    def get_nfl_games(self, week_id: str, *, eligible_only: bool = False) -> list[dict[str, Any]]:
        query = (
            self._table("nfl_games")
            .select("id,week_id,provider_event_id,home_team,away_team,kickoff_at,is_eligible,game_status,period,game_clock,home_score,away_score,completed,over_under,spread,favored_team,provider_updated_at")
            .eq("week_id", str(week_id))
        )
        if eligible_only:
            query = query.eq("is_eligible", True)
        return list(query.order("kickoff_at").execute().data or [])

    def upsert_nfl_players(self, players: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not players:
            return []
        stamp = _iso(datetime.now(UTC))
        payload = []
        for player in players:
            if not player.get("sleeper_player_id"):
                continue
            row = dict(player)
            row["last_synced_at"] = stamp
            payload.append(row)
        if not payload:
            return []
        res = self._table("nfl_players").upsert(payload, on_conflict="sleeper_player_id").execute()
        return list(res.data or [])

    def get_nfl_players(self, position: str | None = None) -> list[dict[str, Any]]:
        query = self._table("nfl_players").select(
            "id,sleeper_player_id,canonical_key,full_name,position,team_abbr,active,injury_status,availability_status,depth_order,metadata,last_synced_at"
        )
        if position:
            query = query.eq("position", position)
        return list(query.execute().data or [])

    def get_full_week_pool(self, week_id: str) -> list[dict[str, Any]]:
        return list(
            self._table("player_pool")
            .select(
                "id,week_id,position,slot_rank,player_name,nfl_player_id,sleeper_player_id,espn_player_id,team_abbr,opponent_abbr,kickoff_at,is_visible,availability_status,raw_injury_status,schedule_eligible,schedule_note,score_total,score_status,score_breakdown,game_status,score_updated_at,manual_score_override,manual_override_at,manual_override_note,provider_updated_at"
            )
            .eq("week_id", str(week_id))
            .order("position")
            .order("slot_rank")
            .execute()
            .data
            or []
        )

    def publish_ranked_pool(self, week: dict[str, Any], ranked: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        from weekly import HIDDEN_RANKING_SIZE

        for position in POSITIONS:
            rows = list(ranked.get(position) or [])
            if len(rows) != HIDDEN_RANKING_SIZE:
                raise StoreError(f"Refusing to publish: {position} has {len(rows)} of {HIDDEN_RANKING_SIZE} ranked players.")
            if [int(row.get("slot_rank") or 0) for row in rows] != list(range(1, HIDDEN_RANKING_SIZE + 1)):
                raise StoreError(f"Refusing to publish: {position} ranking is incomplete or duplicated.")

        stamp = _iso(datetime.now(UTC))
        payload: list[dict[str, Any]] = []
        for position in POSITIONS:
            for row in ranked[position]:
                item = dict(row)
                item["week_id"] = str(week["id"])
                item["provider_updated_at"] = stamp
                # Scoring starts clean on publication. Existing manual override
                # columns are not included, so a retry cannot erase one.
                item.setdefault("score_status", "SCHEDULED")
                item.setdefault("score_breakdown", {})
                payload.append(item)
        res = self._table("player_pool").upsert(payload, on_conflict="week_id,position,slot_rank").execute()
        self.update_week_data_state(
            str(week["id"]),
            published_at=stamp,
            data_status="POOL_READY",
            last_data_refresh_at=stamp,
            data_message="Week player pool published.",
        )
        self.clear_week_cache(str(week["id"]))
        return list(res.data or [])

    def sync_pool_injury_status(self, week_id: str, cached_players: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {str(p.get("sleeper_player_id")): p for p in cached_players if p.get("sleeper_player_id")}
        pool = self.get_full_week_pool(str(week_id))
        stamp = _iso(datetime.now(UTC))
        updated: list[dict[str, Any]] = []
        for row in pool:
            player = by_id.get(str(row.get("sleeper_player_id") or row.get("nfl_player_id") or ""))
            if not player:
                continue
            availability = str(player.get("availability_status") or "HEALTHY")
            raw = player.get("injury_status")
            if availability == row.get("availability_status") and raw == row.get("raw_injury_status"):
                continue
            res = (
                self._table("player_pool")
                .update({
                    "availability_status": availability,
                    "raw_injury_status": raw,
                    "provider_updated_at": stamp,
                })
                .eq("id", str(row["id"]))
                .execute()
            )
            updated.extend(res.data or [])
        if updated:
            self.clear_week_cache(str(week_id))
        return updated

    def promote_replacements_for_out_players(self, week: dict[str, Any]) -> list[dict[str, Any]]:
        """Before the Saturday cutoff, keep exactly five visible healthy/Q choices.

        A selected starter who is removed from the visible pool is deleted from
        that lineup so the player is clearly incomplete and must choose again.
        OUT emergency backups are simply cleared.
        """
        pool = self.get_full_week_pool(str(week["id"]))
        changes: list[dict[str, Any]] = []
        for position in POSITIONS:
            pos_rows = sorted([r for r in pool if r.get("position") == position], key=lambda r: int(r.get("slot_rank") or 999))
            visible_out = [r for r in pos_rows if r.get("is_visible") and r.get("availability_status") == "OUT"]
            for out_row in visible_out:
                replacement = next((r for r in pos_rows if not r.get("is_visible") and r.get("availability_status") != "OUT"), None)
                if not replacement:
                    raise StoreError(f"No healthy hidden replacement remains for {position}.")

                # Invalidate any lineups that used the removed starter.
                selected = (
                    self._table("lineup_picks")
                    .select("id,lineup_id")
                    .eq("pool_player_id", str(out_row["id"]))
                    .execute()
                    .data
                    or []
                )
                if selected:
                    lineup_ids = [str(row["lineup_id"]) for row in selected]
                    self._table("lineup_picks").delete().eq("pool_player_id", str(out_row["id"])).execute()
                    self._table("lineups").update({"confirmed_at": None, "updated_at": _iso(datetime.now(UTC))}).in_("id", lineup_ids).execute()

                # A removed player can no longer remain as an emergency backup.
                self._table("lineup_picks").update({"emergency_pool_player_id": None, "updated_at": _iso(datetime.now(UTC))}).eq(
                    "emergency_pool_player_id", str(out_row["id"])
                ).execute()

                self._table("player_pool").update({"is_visible": False}).eq("id", str(out_row["id"])).execute()
                self._table("player_pool").update({"is_visible": True}).eq("id", str(replacement["id"])).execute()
                changes.append({
                    "position": position,
                    "out": out_row.get("player_name"),
                    "replacement": replacement.get("player_name"),
                })
                out_row["is_visible"] = False
                replacement["is_visible"] = True
        if changes:
            self.clear_week_cache(str(week["id"]))
        return changes

    def upsert_player_week_stats(self, week_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        stamp = _iso(datetime.now(UTC))
        payload = []
        for row in rows:
            item = dict(row)
            item["week_id"] = str(week_id)
            item["updated_at"] = stamp
            payload.append(item)
        res = self._table("player_week_stats").upsert(payload, on_conflict="week_id,pool_player_id").execute()
        return list(res.data or [])

    def apply_pool_scores(self, week: dict[str, Any], score_rows: list[dict[str, Any]], *, score_status: str) -> list[dict[str, Any]]:
        if not score_rows:
            return []
        current = {str(r["id"]): r for r in self.get_full_week_pool(str(week["id"]))}
        stamp = _iso(datetime.now(UTC))
        payload: list[dict[str, Any]] = []
        for score in score_rows:
            pool_id = str(score["pool_player_id"])
            existing = current.get(pool_id)
            if not existing:
                continue
            row = dict(existing)
            manual = row.get("manual_score_override")
            row["score_total"] = float(manual) if manual is not None else float(score.get("points") or 0)
            row["score_status"] = score_status
            row["score_breakdown"] = score.get("breakdown") or {}
            row["game_status"] = score.get("game_status")
            row["espn_player_id"] = score.get("source_player_id") or row.get("espn_player_id")
            row["score_updated_at"] = stamp
            row["provider_updated_at"] = stamp
            payload.append(row)
        if not payload:
            return []
        res = self._table("player_pool").upsert(payload, on_conflict="id").execute()
        self.update_week_data_state(
            str(week["id"]),
            data_status=("LIVE" if score_status == "LIVE" else score_status),
            last_data_refresh_at=stamp,
            data_message=f"{score_status.title()} score refresh complete.",
        )
        self.clear_week_cache(str(week["id"]))
        return list(res.data or [])

    def get_player_week_stats(self, week_id: str, pool_player_ids: list[str] | None = None) -> list[dict[str, Any]]:
        query = (
            self._table("player_week_stats")
            .select("id,week_id,pool_player_id,source,source_player_id,raw_stats,points,breakdown,game_status,updated_at")
            .eq("week_id", str(week_id))
        )
        if pool_player_ids:
            query = query.in_("pool_player_id", [str(value) for value in pool_player_ids])
        return list(query.execute().data or [])

    def get_pool_score_state(self, pool_player_ids: list[str]) -> list[dict[str, Any]]:
        if not pool_player_ids:
            return []
        return list(
            self._table("player_pool")
            .select("id,score_total,score_status,score_breakdown,game_status,score_updated_at,espn_player_id,provider_updated_at")
            .in_("id", [str(value) for value in pool_player_ids])
            .execute()
            .data
            or []
        )

    def restore_pool_score_state(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            pool_id = str(row.get("id") or "")
            if not pool_id:
                continue
            payload = {
                key: row.get(key)
                for key in (
                    "score_total",
                    "score_status",
                    "score_breakdown",
                    "game_status",
                    "score_updated_at",
                    "espn_player_id",
                    "provider_updated_at",
                )
            }
            self._table("player_pool").update(payload).eq("id", pool_id).execute()
        self.clear_week_cache()

    def restore_player_week_stats(
        self,
        week_id: str,
        tested_pool_player_ids: list[str],
        original_rows: list[dict[str, Any]],
    ) -> None:
        ids = [str(value) for value in tested_pool_player_ids if value]
        if ids:
            self._table("player_week_stats").delete().eq("week_id", str(week_id)).in_("pool_player_id", ids).execute()
        if original_rows:
            self._table("player_week_stats").upsert(original_rows, on_conflict="week_id,pool_player_id").execute()

    def scoring_fingerprint(self, week_id: str) -> dict[str, Any]:
        pool = list(
            self._table("player_pool")
            .select("id,score_total,score_status,score_breakdown,game_status,score_updated_at,manual_score_override,manual_override_at")
            .eq("week_id", str(week_id))
            .order("id")
            .execute()
            .data
            or []
        )
        stats = list(
            self._table("player_week_stats")
            .select("id,week_id,pool_player_id,source,source_player_id,raw_stats,points,breakdown,game_status,updated_at")
            .eq("week_id", str(week_id))
            .order("pool_player_id")
            .execute()
            .data
            or []
        )
        return {"pool": pool, "stats": stats}

    def start_data_run(self, run_type: str, *, week_id: str | None = None, provider: str | None = None, metadata: dict | None = None) -> str:
        res = self._table("data_runs").insert({
            "week_id": str(week_id) if week_id else None,
            "run_type": run_type,
            "provider": provider,
            "metadata": metadata or {},
        }).execute()
        return str(res.data[0]["id"])

    def finish_data_run(self, run_id: str, *, success: bool, message: str = "", metadata: dict | None = None) -> None:
        payload: dict[str, Any] = {
            "completed_at": _iso(datetime.now(UTC)),
            "success": bool(success),
            "message": message,
        }
        if metadata is not None:
            payload["metadata"] = metadata
        self._table("data_runs").update(payload).eq("id", str(run_id)).execute()

    def last_successful_run(self, run_type: str, *, week_id: str | None = None) -> dict[str, Any] | None:
        query = (
            self._table("data_runs")
            .select("id,week_id,run_type,provider,started_at,completed_at,success,message,metadata")
            .eq("run_type", run_type)
            .eq("success", True)
        )
        if week_id:
            query = query.eq("week_id", str(week_id))
        rows = query.order("started_at", desc=True).limit(1).execute().data or []
        return rows[0] if rows else None

    def ensure_real_week_shell(self, *, season: int, nfl_week: int, label: str, opens_at: str, locks_at: str) -> dict[str, Any]:
        payload = {
            "season": int(season),
            "nfl_week": int(nfl_week),
            "label": label,
            "opens_at": opens_at,
            "locks_at": locks_at,
            "is_demo": False,
        }
        res = self._table("weeks").upsert(payload, on_conflict="season,nfl_week,is_demo").execute()
        self.clear_week_cache()
        return res.data[0]

    def reconcile_pool_schedule(self, week: dict[str, Any], games: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply schedule changes to a published pool.

        A game that remains on Sunday simply updates opponent/kickoff. If a
        team's game moves outside the Sunday 1 PM-or-later eligibility window
        before lock, that team's pool entries become ineligible and visible
        entries are replaced from hidden ranks. This schedule rule overrides
        the normal Saturday-night injury freeze.
        """
        if not week.get("published_at"):
            return []
        team_game: dict[str, dict[str, Any]] = {}
        for game in games:
            for team in (game.get("home_team"), game.get("away_team")):
                if team:
                    team_game[str(team)] = game
        pool = self.get_full_week_pool(str(week["id"]))
        stamp = _iso(datetime.now(UTC))

        # First make every row's current schedule eligibility explicit.
        for row in pool:
            team = str(row.get("team_abbr") or "")
            game = team_game.get(team)
            eligible = bool(game and game.get("is_eligible"))
            payload: dict[str, Any] = {
                "schedule_eligible": eligible,
                "schedule_note": None if eligible else "Game is no longer an eligible Sunday 1:00 PM ET-or-later game.",
                "provider_updated_at": stamp,
            }
            if game:
                is_home = team == str(game.get("home_team") or "")
                payload["opponent_abbr"] = str(game.get("away_team") if is_home else game.get("home_team"))
                payload["kickoff_at"] = game.get("kickoff_at")
            self._table("player_pool").update(payload).eq("id", str(row["id"])).execute()
            row.update(payload)

        changes: list[dict[str, Any]] = []
        for position in POSITIONS:
            pos_rows = sorted([r for r in pool if r.get("position") == position], key=lambda r: int(r.get("slot_rank") or 999))
            invalid_visible = [r for r in pos_rows if r.get("is_visible") and not r.get("schedule_eligible")]
            for invalid in invalid_visible:
                replacement = next(
                    (
                        r for r in pos_rows
                        if not r.get("is_visible")
                        and r.get("schedule_eligible")
                        and r.get("availability_status") != "OUT"
                    ),
                    None,
                )
                if not replacement:
                    raise StoreError(f"No eligible hidden schedule replacement remains for {position}.")

                selected = (
                    self._table("lineup_picks")
                    .select("id,lineup_id")
                    .eq("pool_player_id", str(invalid["id"]))
                    .execute()
                    .data
                    or []
                )
                if selected:
                    lineup_ids = [str(row["lineup_id"]) for row in selected]
                    self._table("lineup_picks").delete().eq("pool_player_id", str(invalid["id"])).execute()
                    self._table("lineups").update({"confirmed_at": None, "updated_at": stamp}).in_("id", lineup_ids).execute()
                self._table("lineup_picks").update({"emergency_pool_player_id": None, "updated_at": stamp}).eq(
                    "emergency_pool_player_id", str(invalid["id"])
                ).execute()
                self._table("player_pool").update({"is_visible": False}).eq("id", str(invalid["id"])).execute()
                self._table("player_pool").update({"is_visible": True}).eq("id", str(replacement["id"])).execute()
                invalid["is_visible"] = False
                replacement["is_visible"] = True
                changes.append({"position": position, "removed": invalid.get("player_name"), "replacement": replacement.get("player_name"), "reason": "schedule"})
        self.clear_week_cache(str(week["id"]))
        return changes

    # -------------------------
    # Gate 5 Commissioner controls
    # -------------------------
    def reset_player_pin(self, player_id: str, *, pin_salt: str, pin_hash: str, revoke_sessions: bool = True) -> None:
        self._table("players").update({"pin_salt": pin_salt, "pin_hash": pin_hash}).eq("id", str(player_id)).execute()
        if revoke_sessions:
            stamp = _iso(datetime.now(UTC))
            self._table("player_sessions").update({"revoked_at": stamp}).eq("player_id", str(player_id)).execute()
        self._public_cache.pop(("registered_players",), None)

    def get_week_lineup_admin(self, week_id: str) -> list[dict[str, Any]]:
        players = self.get_registered_players()
        lineups = list(
            self._table("lineups")
            .select("id,player_id,confirmed_at,updated_at")
            .eq("week_id", str(week_id))
            .execute()
            .data
            or []
        )
        lineup_by_player = {str(row["player_id"]): row for row in lineups}
        lineup_ids = [str(row["id"]) for row in lineups]
        pick_counts: dict[str, int] = {}
        if lineup_ids:
            picks = list(
                self._table("lineup_picks")
                .select("lineup_id,position")
                .in_("lineup_id", lineup_ids)
                .execute()
                .data
                or []
            )
            for pick in picks:
                lid = str(pick.get("lineup_id") or "")
                pick_counts[lid] = pick_counts.get(lid, 0) + 1

        rows: list[dict[str, Any]] = []
        for player in players:
            player_id = str(player["id"])
            lineup = lineup_by_player.get(player_id)
            lineup_id = str(lineup.get("id")) if lineup else ""
            count = int(pick_counts.get(lineup_id, 0)) if lineup_id else 0
            rows.append({
                **player,
                "lineup_id": lineup_id or None,
                "pick_count": count,
                "confirmed": bool(lineup and lineup.get("confirmed_at")),
                "lineup_updated_at": lineup.get("updated_at") if lineup else None,
            })
        return rows

    def get_pool_usage(self, week_id: str, pool_player_id: str) -> dict[str, Any]:
        starter_rows = list(
            self._table("lineup_picks")
            .select("lineup_id")
            .eq("pool_player_id", str(pool_player_id))
            .execute()
            .data
            or []
        )
        backup_rows = list(
            self._table("lineup_picks")
            .select("lineup_id")
            .eq("emergency_pool_player_id", str(pool_player_id))
            .execute()
            .data
            or []
        )
        lineup_ids = sorted({str(row["lineup_id"]) for row in starter_rows + backup_rows if row.get("lineup_id")})
        names: list[str] = []
        if lineup_ids:
            lineups = list(
                self._table("lineups")
                .select("id,player_id")
                .eq("week_id", str(week_id))
                .in_("id", lineup_ids)
                .execute()
                .data
                or []
            )
            player_ids = [str(row["player_id"]) for row in lineups if row.get("player_id")]
            if player_ids:
                players = list(
                    self._table("players")
                    .select("id,nickname")
                    .in_("id", player_ids)
                    .execute()
                    .data
                    or []
                )
                names = sorted([str(row.get("nickname") or "Player") for row in players], key=str.casefold)
        return {
            "starter_count": len(starter_rows),
            "backup_count": len(backup_rows),
            "affected_lineups": len(lineup_ids),
            "affected_nicknames": names,
        }

    def replace_visible_pool_player(
        self,
        week_id: str,
        *,
        outgoing_pool_id: str,
        replacement_pool_id: str,
        reason: str,
    ) -> dict[str, Any]:
        week = self.get_week(str(week_id))
        if not week:
            raise StoreError("Week not found.")
        locks_at = parse_timestamp(week.get("locks_at"))
        if locks_at and datetime.now(UTC) >= locks_at:
            raise PicksLocked("Player-pool overrides are disabled after the universal lock.")

        pool = {str(row["id"]): row for row in self.get_full_week_pool(str(week_id))}
        outgoing = pool.get(str(outgoing_pool_id))
        replacement = pool.get(str(replacement_pool_id))
        if not outgoing or not replacement:
            raise StoreError("One of those pool players is no longer available.")
        if not outgoing.get("is_visible"):
            raise StoreError("The player being replaced is not currently visible.")
        if replacement.get("is_visible"):
            raise StoreError("The replacement is already visible.")
        if str(outgoing.get("position")) != str(replacement.get("position")):
            raise StoreError("A replacement must come from the same position.")
        if str(replacement.get("availability_status") or "HEALTHY").upper() == "OUT":
            raise StoreError("An OUT player cannot be promoted into the weekly pool.")
        if not bool(replacement.get("schedule_eligible", True)):
            raise StoreError("That replacement no longer has an eligible Sunday game.")

        impact = self.get_pool_usage(str(week_id), str(outgoing_pool_id))
        stamp = _iso(datetime.now(UTC))
        starter_rows = list(
            self._table("lineup_picks")
            .select("id,lineup_id")
            .eq("pool_player_id", str(outgoing_pool_id))
            .execute()
            .data
            or []
        )
        if starter_rows:
            lineup_ids = [str(row["lineup_id"]) for row in starter_rows]
            self._table("lineup_picks").delete().eq("pool_player_id", str(outgoing_pool_id)).execute()
            self._table("lineups").update({"confirmed_at": None, "updated_at": stamp}).in_("id", lineup_ids).execute()
        self._table("lineup_picks").update({"emergency_pool_player_id": None, "updated_at": stamp}).eq(
            "emergency_pool_player_id", str(outgoing_pool_id)
        ).execute()

        self._table("player_pool").update({
            "is_visible": False,
            "schedule_note": f"Commissioner override: {reason}",
            "provider_updated_at": stamp,
        }).eq("id", str(outgoing_pool_id)).execute()
        self._table("player_pool").update({
            "is_visible": True,
            "schedule_note": f"Commissioner override replacement: {reason}",
            "provider_updated_at": stamp,
        }).eq("id", str(replacement_pool_id)).execute()
        self.clear_week_cache(str(week_id))
        return {
            "position": str(outgoing.get("position")),
            "outgoing_id": str(outgoing_pool_id),
            "outgoing_name": str(outgoing.get("player_name") or "Player"),
            "replacement_id": str(replacement_pool_id),
            "replacement_name": str(replacement.get("player_name") or "Player"),
            "reason": reason,
            **impact,
        }

    def set_manual_score_override(self, week_id: str, pool_player_id: str, score: float, note: str) -> dict[str, Any]:
        stamp = _iso(datetime.now(UTC))
        res = (
            self._table("player_pool")
            .update({
                "manual_score_override": float(score),
                "manual_override_at": stamp,
                "manual_override_note": note,
                "score_total": float(score),
                "score_updated_at": stamp,
            })
            .eq("week_id", str(week_id))
            .eq("id", str(pool_player_id))
            .execute()
        )
        if not res.data:
            raise StoreError("That pool player could not be found.")
        self.clear_week_cache(str(week_id))
        return dict(res.data[0])

    def clear_manual_score_override(self, week_id: str, pool_player_id: str) -> dict[str, Any]:
        stat_rows = list(
            self._table("player_week_stats")
            .select("points")
            .eq("week_id", str(week_id))
            .eq("pool_player_id", str(pool_player_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        provider_score = float(stat_rows[0].get("points") or 0) if stat_rows else None
        stamp = _iso(datetime.now(UTC))
        res = (
            self._table("player_pool")
            .update({
                "manual_score_override": None,
                "manual_override_at": None,
                "manual_override_note": None,
                "score_total": provider_score,
                "score_updated_at": stamp,
            })
            .eq("week_id", str(week_id))
            .eq("id", str(pool_player_id))
            .execute()
        )
        if not res.data:
            raise StoreError("That pool player could not be found.")
        self.clear_week_cache(str(week_id))
        return dict(res.data[0])

    def get_recent_data_runs(self, *, week_id: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        query = self._table("data_runs").select(
            "id,week_id,run_type,provider,started_at,completed_at,success,message,metadata"
        )
        if week_id:
            query = query.eq("week_id", str(week_id))
        return list(query.order("started_at", desc=True).limit(int(limit)).execute().data or [])

    def record_commissioner_action(
        self,
        action: str,
        *,
        week_id: str | None = None,
        player_id: str | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        data = dict(metadata or {})
        if player_id:
            data["player_id"] = str(player_id)
        run_id = self.start_data_run(f"commissioner_{action}", week_id=week_id, provider="commissioner", metadata=data)
        self.finish_data_run(run_id, success=True, message=message, metadata=data)
        return run_id

    # -------------------------
    # Gate 4 live Sunday / season data
    # -------------------------
    def get_registered_players(self) -> list[dict[str, Any]]:
        cache_key = ("registered_players",)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return list(cached)
        rows = list(
            self._table("players")
            .select("id,nickname,emoji,created_at,last_seen_at")
            .order("nickname")
            .execute()
            .data
            or []
        )
        return list(self._cache_set(cache_key, rows, 20))

    def get_week_public_bundle(self, week_id: str, *, ttl_seconds: float = 8.0) -> dict[str, Any]:
        cache_key = ("gate4_bundle", str(week_id))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return dict(cached)
        lineups = list(
            self._table("lineups")
            .select("id,week_id,player_id,confirmed_at,created_at,updated_at")
            .eq("week_id", str(week_id))
            .execute()
            .data
            or []
        )
        lineup_ids = [str(row["id"]) for row in lineups]
        picks: list[dict[str, Any]] = []
        if lineup_ids:
            picks = list(
                self._table("lineup_picks")
                .select("id,lineup_id,position,pool_player_id,emergency_pool_player_id,updated_at")
                .in_("lineup_id", lineup_ids)
                .execute()
                .data
                or []
            )
        player_ids = [str(row["player_id"]) for row in lineups]
        players: list[dict[str, Any]] = []
        if player_ids:
            players = list(
                self._table("players")
                .select("id,nickname,emoji")
                .in_("id", player_ids)
                .execute()
                .data
                or []
            )
        value = {
            "lineups": lineups,
            "picks": picks,
            "players": players,
            "pool": self.get_full_week_pool(str(week_id)),
            "games": self.get_nfl_games(str(week_id), eligible_only=False),
        }
        return dict(self._cache_set(cache_key, value, ttl_seconds))

    def get_weekly_results(
        self,
        *,
        season: int | None = None,
        week_id: str | None = None,
        player_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = self._table("weekly_results").select(
            "id,week_id,season,nfl_week,player_id,nickname_snapshot,emoji_snapshot,weekly_score,finish_rank,season_points,is_champion,finalized_at"
        )
        if season is not None:
            query = query.eq("season", int(season))
        if week_id is not None:
            query = query.eq("week_id", str(week_id))
        if player_id is not None:
            query = query.eq("player_id", str(player_id))
        return list(query.order("nfl_week", desc=True).order("finish_rank").execute().data or [])

    def upsert_weekly_results(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        res = self._table("weekly_results").upsert(rows, on_conflict="week_id,player_id").execute()
        self._public_cache.pop(("weekly_results",), None)
        return list(res.data or [])

    def get_season_champions(self, season: int | None = None) -> list[dict[str, Any]]:
        query = self._table("season_champions").select(
            "id,season,player_id,nickname_snapshot,emoji_snapshot,season_points,total_fantasy_points,awarded_at"
        )
        if season is not None:
            query = query.eq("season", int(season))
        return list(query.order("season", desc=True).order("nickname_snapshot").execute().data or [])

    def upsert_season_champions(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        return list(self._table("season_champions").upsert(rows, on_conflict="season,player_id").execute().data or [])

    def purge_prior_week_rosters(self, *, season: int, before_nfl_week: int) -> list[int]:
        candidates = list(
            self._table("weeks")
            .select("id,nfl_week,finalized_at,rosters_purged_at")
            .eq("season", int(season))
            .eq("is_demo", False)
            .lt("nfl_week", int(before_nfl_week))
            .order("nfl_week")
            .execute()
            .data
            or []
        )
        weeks = [row for row in candidates if row.get("finalized_at") and not row.get("rosters_purged_at")]
        purged: list[int] = []
        stamp = _iso(datetime.now(UTC))
        for week in weeks:
            # lineup_picks cascade from lineups; weekly_results preserve history.
            self._table("lineups").delete().eq("week_id", str(week["id"])).execute()
            self._table("weeks").update({"rosters_purged_at": stamp}).eq("id", str(week["id"])).execute()
            purged.append(int(week["nfl_week"]))
            self.clear_week_cache(str(week["id"]))
        return purged

