from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from config import LIVE_SCORE_REFRESH_MINUTES
from nfl_sync import ensure_week_shell_from_scoreboard, publish_week_pool, reconcile_final, refresh_injuries, refresh_live_scores
from weekly import parse_timestamp

UTC = timezone.utc

# GitHub Actions remains the primary scheduler. These thresholds only activate
# the Streamlit-server fallback after the scheduled job has had a small grace
# period to finish. The fallback is intentionally limited to launch-critical
# windows rather than turning ordinary page loads into provider polling.
PUBLISH_RECOVERY_GRACE_MINUTES = 10
CRITICAL_REFRESH_GRACE_MINUTES = 2
FAILED_ATTEMPT_COOLDOWN_MINUTES = 5
FINAL_RECOVERY_GRACE_MINUTES = 20
LEASE_TTL_SECONDS = 180


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

    # Sunday pre-lock: once inside the final two hours, injury/status data should
    # never depend solely on a delayed GitHub cron. The scheduled 15-minute job
    # gets a two-minute grace period before an active app session may recover it.
    if lock - timedelta(hours=2) <= now < lock:
        due_after = LIVE_SCORE_REFRESH_MINUTES + CRITICAL_REFRESH_GRACE_MINUTES
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
