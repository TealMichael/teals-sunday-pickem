from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from typing import Any
from uuid import uuid4

from config import (
    ACTIVE_GAME_STATE_REFRESH_MINUTES,
    ACTIVE_PLAYER_STAT_REFRESH_MINUTES,
    LIVE_SCORE_REFRESH_MINUTES,
)
from nfl_sync import (
    ensure_week_shell_from_scoreboard,
    publish_week_pool,
    reconcile_final,
    refresh_injuries,
    refresh_live_game_state,
    refresh_live_player_stats,
    refresh_live_scores,
)
from weekly import parse_timestamp

UTC = timezone.utc
AUTOMATION_RECOVERY_SCHEMA_VERSION = 5
# Legacy regression marker only: AUTOMATION_RECOVERY_SCHEMA_VERSION = 4
ACTIVE_LIVE_LANE_SCHEMA_VERSION = 1

# GitHub Actions remains the primary scheduler. These thresholds only activate
# the Streamlit-server fallback after the scheduled job has had a small grace
# period to finish. The fallback is intentionally limited to launch-critical
# windows rather than turning ordinary page loads into provider polling.
PUBLISH_RECOVERY_GRACE_MINUTES = 10
CRITICAL_REFRESH_GRACE_MINUTES = 2
SUNDAY_MORNING_REFRESH_MINUTES = 60
SUNDAY_CRITICAL_INJURY_REFRESH_MINUTES = 15
SUNDAY_MORNING_RECOVERY_HOURS_BEFORE_LOCK = 5
# The scheduled Sunday worker intentionally runs at :07/:22/:37/:52 to avoid
# GitHub's top-of-hour congestion. Do not make the first person opening the app
# at exactly 1:00 PM synchronously fetch the entire live slate; give the 1:07
# primary job time to run, then rescue it from an active session if still absent.
INITIAL_LIVE_RECOVERY_DELAY_MINUTES = 10
FAILED_ATTEMPT_COOLDOWN_MINUTES = 5
FINAL_RECOVERY_GRACE_MINUTES = 20
LEASE_TTL_SECONDS = 420


def _age_minutes(value: str | datetime | None, now: datetime) -> float | None:
    stamp = parse_timestamp(value)
    if not stamp:
        return None
    return max(0.0, (now - stamp).total_seconds() / 60.0)


def _latest_attempt_age(store, run_type: str, week_id: str, now: datetime) -> float | None:
    latest = store.latest_data_run(run_type, week_id=week_id)
    if not latest:
        return None
    return _age_minutes(latest.get("completed_at") or latest.get("started_at"), now)


def _successful_age(store, run_type: str, week_id: str, now: datetime) -> float | None:
    latest = store.last_successful_run(run_type, week_id=week_id)
    if not latest:
        return None
    return _age_minutes(latest.get("completed_at") or latest.get("started_at"), now)



ACTIVE_GAME_STATE_FAILED_COOLDOWN_MINUTES = 1
ACTIVE_PLAYER_STAT_FAILED_COOLDOWN_MINUTES = 2
ACTIVE_GAME_STATE_LEASE_TTL_SECONDS = 90
ACTIVE_PLAYER_STAT_LEASE_TTL_SECONDS = 180



# Legacy hook marker only: refresh_clock_snapshot(store, refreshed)
def _refresh_clock_snapshot_best_effort(store, week: dict[str, Any]) -> None:
    try:
        import clock_broadcast as _clock_broadcast
        if getattr(_clock_broadcast, "CLOCK_SNAPSHOT_VERSION", 0) < 4:
            _clock_broadcast = importlib.reload(_clock_broadcast)
        _clock_broadcast.refresh_clock_snapshot(store, week)
    except Exception:
        pass

def _latest_game_state_age(store, week_id: str, now: datetime) -> float | None:
    """Return age of the freshest persisted NFL game row for this week."""
    try:
        games = store.get_nfl_games(week_id)
    except Exception:
        return None
    ages = [
        age
        for age in (_age_minutes(row.get("provider_updated_at"), now) for row in games)
        if age is not None
    ]
    return min(ages) if ages else None


def maybe_refresh_active_live_lane(
    store,
    week: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Use one active Sunday session as a leased faster live-data worker.

    GitHub remains the durable five-minute scheduler. While at least one player
    has the Sunday screen open, this lane can refresh fantasy stats about every
    three minutes and the lighter game clock/score state about every two minutes.
    Supabase leases guarantee that many open phones still produce one shared
    provider refresh rather than one request stream per user.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    if not week or bool(week.get("is_demo")) or not week.get("published_at"):
        return week, None

    week_id = str(week.get("id") or "")
    lock = parse_timestamp(week.get("locks_at"))
    status = str(week.get("data_status") or "").upper()
    if not week_id or not lock or now < lock or now > lock + timedelta(hours=12):
        return week, None
    if status in {"FINAL", "PROVISIONAL"}:
        return week, None

    # Fantasy scoring is the more valuable/heavier lane. If it is due, let it
    # run first; its ESPN summary responses also refresh score/period/clock, so
    # we deliberately skip a redundant scoreboard call in the same fragment.
    score_age = _age_minutes(week.get("last_data_refresh_at"), now)
    if score_age is None or score_age >= ACTIVE_PLAYER_STAT_REFRESH_MINUTES:
        attempt_age = _latest_attempt_age(store, "live_player_stats", week_id, now)
        if attempt_age is None or attempt_age >= ACTIVE_PLAYER_STAT_FAILED_COOLDOWN_MINUTES:
            owner = uuid4().hex
            lease_key = f"week:{week_id}:active-player-stats"
            if store.claim_refresh_lease(lease_key, owner=owner, ttl_seconds=ACTIVE_PLAYER_STAT_LEASE_TTL_SECONDS):
                try:
                    result = refresh_live_player_stats(store, week)
                    store.clear_week_cache(week_id)
                    refreshed = store.get_week(week_id) or week
                    _refresh_clock_snapshot_best_effort(store, refreshed)
                    return refreshed, {"action": "player_stats", "triggered": True, "success": True, "result": result}
                except Exception as exc:
                    return week, {"action": "player_stats", "triggered": True, "success": False, "error_type": type(exc).__name__}
                finally:
                    store.release_refresh_lease(lease_key, owner=owner)
            return week, {"action": "player_stats", "triggered": False, "reason": "lease-busy-or-unavailable"}

    # The game-state lane is one ESPN scoreboard request and does not touch the
    # week-level fantasy-score freshness stamp. A recent heavy stats refresh or
    # GitHub full refresh also updates nfl_games.provider_updated_at, naturally
    # postponing this lightweight call and avoiding duplicate provider traffic.
    state_age = _latest_game_state_age(store, week_id, now)
    if state_age is None or state_age >= ACTIVE_GAME_STATE_REFRESH_MINUTES:
        attempt_age = _latest_attempt_age(store, "live_game_state", week_id, now)
        if attempt_age is None or attempt_age >= ACTIVE_GAME_STATE_FAILED_COOLDOWN_MINUTES:
            owner = uuid4().hex
            lease_key = f"week:{week_id}:active-game-state"
            if store.claim_refresh_lease(lease_key, owner=owner, ttl_seconds=ACTIVE_GAME_STATE_LEASE_TTL_SECONDS):
                try:
                    result = refresh_live_game_state(store, week)
                    store.clear_week_cache(week_id)
                    _refresh_clock_snapshot_best_effort(store, week)
                    return week, {"action": "game_state", "triggered": True, "success": True, "result": result}
                except Exception as exc:
                    return week, {"action": "game_state", "triggered": True, "success": False, "error_type": type(exc).__name__}
                finally:
                    store.release_refresh_lease(lease_key, owner=owner)
            return week, {"action": "game_state", "triggered": False, "reason": "lease-busy-or-unavailable"}

    return week, None

def recovery_action_due(store, week: dict[str, Any], *, now: datetime | None = None) -> str | None:
    """Return the one launch-critical recovery action that is currently due.

    Order matters: publishing precedes injury/live work, and final reconciliation
    takes precedence once Monday's settlement window arrives.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    if not week or bool(week.get("is_demo")):
        return None

    week_id = str(week.get("id") or "")
    if not week_id:
        return None

    opens = parse_timestamp(week.get("opens_at"))
    lock = parse_timestamp(week.get("locks_at"))

    # If Tuesday publication was delayed/dropped, the first active player after
    # a 10-minute grace period can recover it. Provider/pool validation remains
    # identical to the normal publish path.
    if opens and lock and opens <= now < lock and not week.get("published_at"):
        if now >= opens + timedelta(minutes=PUBLISH_RECOVERY_GRACE_MINUTES):
            recent_attempt = _latest_attempt_age(store, "publish_pool", week_id, now)
            if recent_attempt is None or recent_attempt >= FAILED_ATTEMPT_COOLDOWN_MINUTES:
                return "publish"

    if not lock or not week.get("published_at"):
        return None

    # Sunday pre-lock recovery has two safety tiers. Starting five hours before
    # the universal 1 PM ET lock (8 AM ET), an active player may rescue injury
    # data that is more than roughly one hourly cycle stale. Inside the final
    # two hours, the existing 15-minute protection takes over. GitHub remains
    # primary in both windows; the fallback only acts after the shared freshness
    # stamp and run history are both beyond the cadence + grace threshold.
    morning_start = lock - timedelta(hours=SUNDAY_MORNING_RECOVERY_HOURS_BEFORE_LOCK)
    critical_start = lock - timedelta(hours=2)
    if morning_start <= now < lock:
        cadence_minutes = (
            SUNDAY_MORNING_REFRESH_MINUTES
            if now < critical_start
            else SUNDAY_CRITICAL_INJURY_REFRESH_MINUTES
        )
        due_after = cadence_minutes + CRITICAL_REFRESH_GRACE_MINUTES
        # Fast path: the week row is already loaded for the page. Avoid another
        # Supabase round trip on normal fresh page views. Only inspect run history
        # once the shared freshness stamp itself looks overdue.
        shared_age = _age_minutes(week.get("last_data_refresh_at"), now)
        if shared_age is None or shared_age >= due_after:
            success_age = _successful_age(store, "injury_refresh", week_id, now)
            if success_age is None or success_age >= due_after:
                attempt_age = _latest_attempt_age(store, "injury_refresh", week_id, now)
                if attempt_age is None or attempt_age >= FAILED_ATTEMPT_COOLDOWN_MINUTES:
                    return "injury"

    # Sunday live window: keep the public standings recoverable for 12 hours
    # after the universal 1 PM ET lock, including long SNF/overtime games.
    data_status = str(week.get("data_status") or "").upper()
    if lock <= now <= lock + timedelta(hours=12) and data_status != "FINAL":
        if data_status not in {"LIVE", "PROVISIONAL"} and now < lock + timedelta(minutes=INITIAL_LIVE_RECOVERY_DELAY_MINUTES):
            return None
        due_after = LIVE_SCORE_REFRESH_MINUTES + CRITICAL_REFRESH_GRACE_MINUTES
        shared_age = _age_minutes(week.get("last_data_refresh_at"), now)
        # Before the first LIVE write, a recent pre-lock injury refresh must not
        # suppress the initial scoring refresh. After LIVE begins, the week-level
        # stamp provides the no-extra-query fast path for ordinary page loads.
        needs_history_check = data_status not in {"LIVE", "PROVISIONAL"} or shared_age is None or shared_age >= due_after
        if needs_history_check:
            success_age = _successful_age(store, "live_scores", week_id, now)
            if success_age is None or success_age >= due_after:
                attempt_age = _latest_attempt_age(store, "live_scores", week_id, now)
                if attempt_age is None or attempt_age >= FAILED_ATTEMPT_COOLDOWN_MINUTES:
                    return "live"

    # Monday: GitHub retries hourly beginning shortly after 9 AM ET. If those
    # jobs are delayed, an active player may recover final reconciliation after
    # a 20-minute grace period. Failed attempts are throttled to five minutes.
    final_due = lock + timedelta(days=1) - timedelta(hours=4)  # 9 AM ET when lock is Sunday 1 PM ET
    if now >= final_due + timedelta(minutes=FINAL_RECOVERY_GRACE_MINUTES) and str(week.get("data_status") or "").upper() != "FINAL":
        attempt_age = _latest_attempt_age(store, "final_reconcile", week_id, now)
        if attempt_age is None or attempt_age >= FAILED_ATTEMPT_COOLDOWN_MINUTES:
            return "final"

    return None


def maybe_recover_critical_automation(store, week: dict[str, Any], *, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Run one safe on-demand fallback when a critical scheduled job is stale.

    A tiny Supabase lease prevents multiple Streamlit sessions/instances from
    doing the same provider work at once. If the lease table is unavailable,
    the normal GitHub scheduler remains in control and the player page proceeds
    normally rather than failing.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    action = recovery_action_due(store, week, now=now)
    if not action:
        return week, None

    week_id = str(week["id"])
    owner = uuid4().hex
    lease_key = f"week:{week_id}:{action}"
    if not store.claim_refresh_lease(lease_key, owner=owner, ttl_seconds=LEASE_TTL_SECONDS):
        return week, {"action": action, "triggered": False, "reason": "lease-busy-or-unavailable"}

    audit_id: str | None = None
    try:
        audit_id = store.start_data_run(
            "app_recovery",
            week_id=week_id,
            provider="streamlit-fallback",
            metadata={"action": action},
        )
        if action == "publish":
            result = publish_week_pool(store, week)
        elif action == "injury":
            result = refresh_injuries(store, week)
        elif action == "live":
            result = refresh_live_scores(store, week)
        elif action == "final":
            result = reconcile_final(store, week)
            # Mirror run_auto: a recovered Monday finalization must also create
            # the next real-week shell so Tuesday can open normally even if the
            # delayed GitHub cycle never gets a chance to do that bookkeeping.
            next_week_num = int(week.get("nfl_week") or 0) + 1
            if 1 <= next_week_num <= 18:
                ensure_week_shell_from_scoreboard(
                    store,
                    season=int(week.get("season") or 0),
                    nfl_week=next_week_num,
                )
        else:  # defensive; recovery_action_due only returns known actions.
            return week, None

        store.finish_data_run(
            audit_id,
            success=True,
            message=f"App fallback recovered {action} automation.",
            metadata={"action": action},
        )
        store.clear_week_cache(week_id)
        refreshed = store.get_week(week_id) or week
        _refresh_clock_snapshot_best_effort(store, refreshed)
        return refreshed, {"action": action, "triggered": True, "success": True, "result": result}
    except Exception as exc:
        if audit_id:
            try:
                store.finish_data_run(
                    audit_id,
                    success=False,
                    message=f"App fallback {action} attempt failed ({type(exc).__name__}).",
                    metadata={"action": action, "error_type": type(exc).__name__},
                )
            except Exception:
                pass
        # Recovery must never take the public app down. GitHub/manual controls
        # remain available and the next eligible page load can retry later.
        return week, {"action": action, "triggered": True, "success": False, "error_type": type(exc).__name__}
    finally:
        try:
            store.release_refresh_lease(lease_key, owner=owner)
        except Exception:
            pass
