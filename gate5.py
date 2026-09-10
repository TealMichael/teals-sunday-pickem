from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gate4_results import archive_week_results
from nfl_sync import publish_week_pool, reconcile_final, refresh_injuries, refresh_live_scores, sync_players, sync_schedule
from security import hash_pin
from validation import validate_player_pin
from weekly import parse_timestamp

UTC = timezone.utc


class CommissionerError(RuntimeError):
    pass


def _refresh_clock_best_effort(store, week: dict[str, Any]) -> None:
    try:
        from clock_broadcast import refresh_clock_snapshot
        refreshed = store.get_week(str(week["id"])) or week
        refresh_clock_snapshot(store, refreshed)
    except Exception:
        pass


def _now() -> datetime:
    return datetime.now(UTC)


def _locked(week: dict[str, Any], now: datetime | None = None) -> bool:
    lock = parse_timestamp(week.get("locks_at"))
    return bool(lock and (now or _now()) >= lock)


def _open_for_generation(week: dict[str, Any], now: datetime | None = None) -> bool:
    opens = parse_timestamp(week.get("opens_at"))
    return bool(opens and (now or _now()) >= opens)


def reset_player_pin(store, *, player_id: str, new_pin: str, pin_confirm: str, pin_pepper: str) -> dict[str, Any]:
    ok, message = validate_player_pin(new_pin)
    if not ok:
        raise CommissionerError(message)
    if new_pin != pin_confirm:
        raise CommissionerError("Those replacement PINs do not match.")
    player = store.get_player_by_id(str(player_id))
    if not player:
        raise CommissionerError("That player could not be found.")

    digest = hash_pin(new_pin, pin_pepper)
    store.reset_player_pin(
        str(player_id),
        pin_salt=digest.salt_b64,
        pin_hash=digest.hash_b64,
        revoke_sessions=True,
    )
    store.record_commissioner_action(
        "pin_reset",
        player_id=str(player_id),
        message=f"Reset PIN for {player.get('nickname') or 'player'} and revoked remembered-device sessions.",
    )
    return player


def week_snapshot(store, week: dict[str, Any]) -> dict[str, Any]:
    players = store.get_registered_players()
    statuses = store.get_week_lineup_admin(str(week["id"]))
    ready = [row for row in statuses if bool(row.get("confirmed")) and int(row.get("pick_count") or 0) == 5]
    incomplete = [row for row in statuses if row not in ready]
    not_started = [row for row in statuses if int(row.get("pick_count") or 0) == 0]
    started = [row for row in statuses if int(row.get("pick_count") or 0) > 0 and row not in ready]
    return {
        "players": players,
        "statuses": statuses,
        "registered": len(players),
        "ready": len(ready),
        "incomplete": len(incomplete),
        "not_started": len(not_started),
        "started": len(started),
        "needs_attention": incomplete,
    }


def refresh_nfl_now(store, week: dict[str, Any]) -> dict[str, Any]:
    """Run the useful production refresh steps for the current moment.

    Before publication this refreshes schedule/player caches only. Once a pool
    exists it also refreshes injuries/schedule eligibility. After lock it also
    performs the live-score refresh. All provider writes continue through the
    same Gate 3 methods used by the unattended worker.
    """
    result: dict[str, Any] = {"schedule_games": 0, "player_positions": 0, "injury": None, "scores": None}
    if week.get("published_at"):
        result["injury"] = refresh_injuries(store, week)
        refreshed_week = store.get_week(str(week["id"])) or week
        if _locked(refreshed_week):
            result["scores"] = refresh_live_scores(store, refreshed_week)
    else:
        games = sync_schedule(store, week)
        players = sync_players(store)
        result["schedule_games"] = len(games)
        result["player_positions"] = len(players)
        store.update_week_data_state(str(week["id"]), last_data_refresh_at=_now().isoformat())

    store.record_commissioner_action(
        "nfl_refresh_now",
        week_id=str(week["id"]),
        message="Commissioner manually refreshed NFL data.",
        metadata={
            "published": bool(week.get("published_at")),
            "after_lock": _locked(week),
        },
    )
    _refresh_clock_best_effort(store, week)
    return result


def generate_pool_again(store, week: dict[str, Any]) -> dict[str, Any]:
    if week.get("published_at"):
        raise CommissionerError("This week is already published. Use Emergency Player Pool Override instead of regenerating a live pool.")
    if not _open_for_generation(week):
        raise CommissionerError("The player pool cannot be published before the scheduled Tuesday opening time.")
    result = publish_week_pool(store, week, force=True)
    store.record_commissioner_action(
        "generate_pool_again",
        week_id=str(week["id"]),
        message="Commissioner manually regenerated and published the weekly pool.",
    )
    _refresh_clock_best_effort(store, week)
    return result


def pool_override_preview(store, week: dict[str, Any], outgoing_pool_id: str) -> dict[str, Any]:
    pool = {str(row["id"]): row for row in store.get_full_week_pool(str(week["id"]))}
    outgoing = pool.get(str(outgoing_pool_id))
    if not outgoing:
        raise CommissionerError("The selected current player is no longer in this week's pool.")
    impact = store.get_pool_usage(str(week["id"]), str(outgoing_pool_id))
    return {"outgoing": outgoing, **impact}


def replace_pool_player(
    store,
    week: dict[str, Any],
    *,
    outgoing_pool_id: str,
    replacement_pool_id: str,
    reason: str,
) -> dict[str, Any]:
    if _locked(week):
        raise CommissionerError("Player-pool overrides are disabled after the universal 1:00 PM ET lock.")
    if not week.get("published_at"):
        raise CommissionerError("There is no published weekly pool to override yet.")
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise CommissionerError("Add a short reason for the emergency pool override.")
    result = store.replace_visible_pool_player(
        str(week["id"]),
        outgoing_pool_id=str(outgoing_pool_id),
        replacement_pool_id=str(replacement_pool_id),
        reason=reason,
    )
    store.record_commissioner_action(
        "pool_override",
        week_id=str(week["id"]),
        message=f"Replaced {result.get('outgoing_name')} with {result.get('replacement_name')} in {result.get('position')}.",
        metadata=result,
    )
    _refresh_clock_best_effort(store, week)
    return result


def set_score_override(
    store,
    week: dict[str, Any],
    *,
    pool_player_id: str,
    score: float,
    note: str,
) -> dict[str, Any]:
    if not week.get("published_at"):
        raise CommissionerError("The weekly player pool has not been published yet.")
    if not _locked(week):
        raise CommissionerError("Manual score corrections are only available after the 1:00 PM ET lock.")
    note = str(note or "").strip()
    if len(note) < 3:
        raise CommissionerError("Add a short note explaining the score correction.")
    if not -100.0 <= float(score) <= 250.0:
        raise CommissionerError("That score is outside the allowed correction range.")

    row = store.set_manual_score_override(str(week["id"]), str(pool_player_id), float(score), note)
    if str(week.get("data_status") or "").upper() == "FINAL":
        archive_week_results(store, store.get_week(str(week["id"])) or week)
    store.record_commissioner_action(
        "score_override",
        week_id=str(week["id"]),
        message=f"Manual score override applied to {row.get('player_name') or 'pool player'}: {float(score):.2f}.",
        metadata={"pool_player_id": str(pool_player_id), "score": float(score), "note": note},
    )
    _refresh_clock_best_effort(store, week)
    return row


def clear_score_override(store, week: dict[str, Any], *, pool_player_id: str) -> dict[str, Any]:
    if not _locked(week):
        raise CommissionerError("Manual score corrections are only available after the 1:00 PM ET lock.")
    row = store.clear_manual_score_override(str(week["id"]), str(pool_player_id))
    if str(week.get("data_status") or "").upper() == "FINAL":
        archive_week_results(store, store.get_week(str(week["id"])) or week)
    store.record_commissioner_action(
        "score_override_cleared",
        week_id=str(week["id"]),
        message=f"Cleared manual score override for {row.get('player_name') or 'pool player'}.",
        metadata={"pool_player_id": str(pool_player_id)},
    )
    _refresh_clock_best_effort(store, week)
    return row


def finalize_week_now(store, week: dict[str, Any]) -> dict[str, Any]:
    if not _locked(week):
        raise CommissionerError("Week finalization is unavailable before the universal 1:00 PM ET lock.")
    result = reconcile_final(store, week)
    store.record_commissioner_action(
        "finalize_week_now",
        week_id=str(week["id"]),
        message="Commissioner manually requested final reconciliation.",
        metadata=result,
    )
    _refresh_clock_best_effort(store, week)
    return result
