from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from config import (
    LOGIN_WINDOW_MINUTES,
    MAX_FAILED_LOGINS_PER_WINDOW,
    NFL_SEASON,
    PBKDF2_ITERATIONS,
    TIMEZONE_NAME,
)
from gate4 import build_season_standings, build_weekly_leaderboard
from nfl_scoring import score_stat_line
from weekly import POSITIONS, parse_timestamp, pool_is_ready, week_phase

UTC = timezone.utc
ET = ZoneInfo(TIMEZONE_NAME)


@dataclass(frozen=True)
class LaunchCheck:
    key: str
    status: str  # PASS | WARN | FAIL
    title: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _check(key: str, status: str, title: str, detail: str) -> LaunchCheck:
    return LaunchCheck(key=key, status=status, title=title, detail=detail)


def _age_minutes(value: str | datetime | None, now: datetime) -> float | None:
    stamp = parse_timestamp(value)
    if not stamp:
        return None
    return max(0.0, (now.astimezone(UTC) - stamp).total_seconds() / 60.0)


def _metadata_pass(run: dict[str, Any] | None, *keys: str) -> bool:
    if not run:
        return False
    metadata = run.get("metadata") or {}
    return all(bool(metadata.get(key)) for key in keys)


def _pool_counts(rows: list[dict[str, Any]], *, visible_only: bool) -> dict[str, int]:
    counts = {pos: 0 for pos in POSITIONS}
    for row in rows:
        if visible_only and not bool(row.get("is_visible")):
            continue
        pos = str(row.get("position") or "")
        if pos in counts:
            counts[pos] += 1
    return counts


def launch_readiness(store, week: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Run a production-safe launch audit without mutating Week 1.

    Checks are phase-aware so pre-Tuesday conditions are not mislabeled as
    failures. The audit intentionally reads the same stored state used by the
    player and Commissioner UIs; it never publishes, scores, or edits a lineup.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    checks: list[LaunchCheck] = []

    # Database / current-week integrity.
    db_ok = bool(store.healthcheck())
    checks.append(_check(
        "database",
        "PASS" if db_ok else "FAIL",
        "Database",
        "Supabase is reachable from the deployed app." if db_ok else "Supabase is not reachable from the deployed app.",
    ))

    opens = parse_timestamp(week.get("opens_at"))
    locks = parse_timestamp(week.get("locks_at"))
    timing_ok = bool(opens and locks and opens < locks)
    lock_contract_ok = False
    if locks:
        lock_et = locks.astimezone(ET)
        lock_contract_ok = lock_et.weekday() == 6 and lock_et.hour == 13 and lock_et.minute == 0
    checks.append(_check(
        "week_timing",
        "PASS" if timing_ok and lock_contract_ok else "FAIL",
        "Week timing",
        "Tuesday opening precedes the universal Sunday 1:00 PM ET lock."
        if timing_ok and lock_contract_ok
        else "The current week timestamps do not match the launch timing contract.",
    ))

    phase = week_phase(week, now)

    # NFL schedule cache.
    games = store.get_nfl_games(str(week["id"]), eligible_only=False)
    eligible = [g for g in games if bool(g.get("is_eligible"))]
    if eligible:
        schedule_status = "PASS"
        schedule_detail = f"{len(eligible)} eligible Sunday games are stored for {week.get('label') or 'the current week'}."
    elif phase == "upcoming":
        schedule_status = "WARN"
        schedule_detail = "No eligible games are cached yet. This is acceptable before Tuesday, but run the NFL data check before launch."
    else:
        schedule_status = "FAIL"
        schedule_detail = "No eligible Sunday games are stored even though the week is open/locked."
    checks.append(_check("schedule", schedule_status, "NFL schedule", schedule_detail))

    # Pool publication state. Full rankings should be 10/position after publish;
    # visible choices must be exactly 5/position.
    full_pool = store.get_full_week_pool(str(week["id"]))
    visible_counts = _pool_counts(full_pool, visible_only=True)
    full_counts = _pool_counts(full_pool, visible_only=False)
    visible_ready = all(visible_counts[pos] == 5 for pos in POSITIONS)
    hidden_ready = all(full_counts[pos] >= 10 for pos in POSITIONS)
    published = bool(week.get("published_at"))
    if phase == "upcoming" and not published:
        pool_status = "PASS"
        pool_detail = "Player pool is correctly unpublished before Tuesday noon."
    elif published and visible_ready and hidden_ready:
        pool_status = "PASS"
        pool_detail = "Published pool has 5 visible + at least 5 reserve choices at every position."
    elif phase == "upcoming":
        pool_status = "WARN"
        pool_detail = "A pre-open pool exists but is not launch-critical yet."
    else:
        pool_status = "FAIL"
        pool_detail = f"Pool is incomplete. Visible counts: {visible_counts}; total ranked counts: {full_counts}."
    checks.append(_check("pool", pool_status, "Weekly player pool", pool_detail))

    # Proven real-provider path.
    replay = store.last_successful_run("preseason_replay")
    replay_ok = _metadata_pass(replay, "anchor_pass", "database_pass", "week1_isolation_pass", "cleanup_pass")
    checks.append(_check(
        "real_boxscore",
        "PASS" if replay_ok else "FAIL",
        "Real box-score replay",
        "Real NFL box score → parser → Pick'em scoring → Supabase has passed end-to-end."
        if replay_ok
        else "The Gate 3.5 real-box-score replay has not recorded a complete PASS.",
    ))

    scoring = store.last_successful_run("scoring_diagnostic")
    scoring_ok = _metadata_pass(scoring, "math_pass", "database_pass", "week1_isolation_pass", "cleanup_pass")
    checks.append(_check(
        "scoring",
        "PASS" if scoring_ok else "FAIL",
        "Scoring pipeline",
        "Scoring math, persistence, Week 1 isolation, and cleanup have all passed."
        if scoring_ok
        else "The controlled Gate 3 scoring diagnostic has not recorded a complete PASS.",
    ))

    # GitHub worker heartbeat is added in Gate 6. A fresh cycle proves the
    # scheduler is actually reaching Supabase independently of Streamlit.
    heartbeat = store.last_successful_run("auto_cycle", week_id=str(week["id"]))
    heartbeat_age = _age_minutes((heartbeat or {}).get("completed_at"), now)
    if heartbeat_age is None:
        heartbeat_status = "WARN"
        heartbeat_detail = "No Gate 6 automation heartbeat is recorded yet. It should appear after the next scheduled GitHub run."
    elif heartbeat_age <= 75:
        heartbeat_status = "PASS"
        heartbeat_detail = f"GitHub NFL worker checked in {int(round(heartbeat_age))} minutes ago."
    else:
        heartbeat_status = "WARN"
        heartbeat_detail = f"Last GitHub worker heartbeat was {int(round(heartbeat_age))} minutes ago; verify Actions before game day."
    checks.append(_check("automation", heartbeat_status, "Automation heartbeat", heartbeat_detail))

    # Surface only recent current-week data failures. Historical preseason
    # debugging failures should not keep Week 1 red forever.
    recent_runs = store.get_recent_data_runs(week_id=str(week["id"]), limit=20)
    recent_failures = []
    for row in recent_runs:
        if row.get("success") is not False:
            continue
        age = _age_minutes(row.get("completed_at") or row.get("started_at"), now)
        if age is not None and age <= 360:
            recent_failures.append(row)
    checks.append(_check(
        "recent_failures",
        "WARN" if recent_failures else "PASS",
        "Recent provider errors",
        f"{len(recent_failures)} failed current-week data run(s) in the last 6 hours. Review Commissioner activity."
        if recent_failures
        else "No failed current-week data runs in the last 6 hours.",
    ))

    # Security configuration is static but worth making visible in the launch
    # audit because the player PIN space is intentionally only four digits.
    security_ok = PBKDF2_ITERATIONS >= 600_000 and MAX_FAILED_LOGINS_PER_WINDOW <= 8 and LOGIN_WINDOW_MINUTES >= 10
    checks.append(_check(
        "auth_security",
        "PASS" if security_ok else "FAIL",
        "PIN/session protection",
        f"PBKDF2 {PBKDF2_ITERATIONS:,} iterations + {MAX_FAILED_LOGINS_PER_WINDOW} attempts/{LOGIN_WINDOW_MINUTES} min throttling are enabled."
        if security_ok
        else "PIN hashing or login-throttling settings are below the launch baseline.",
    ))

    # Account readiness.
    players = store.get_registered_players()
    checks.append(_check(
        "players",
        "PASS" if players else "WARN",
        "Player accounts",
        f"{len(players)} registered player{'s' if len(players) != 1 else ''}; new friends can still join during the season."
        if players
        else "No player accounts exist yet.",
    ))

    statuses = [c.status for c in checks]
    overall = "FAIL" if "FAIL" in statuses else ("WARN" if "WARN" in statuses else "READY")
    return {
        "overall": overall,
        "checks": [c.to_dict() for c in checks],
        "phase": phase,
        "season": int(week.get("season") or NFL_SEASON),
        "nfl_week": int(week.get("nfl_week") or 0),
        "checked_at": now.isoformat(),
    }


def run_full_week_rehearsal() -> dict[str, Any]:
    """Exercise core Week 1 contracts entirely in memory.

    This is intentionally deterministic and has zero database/provider writes.
    It complements (rather than duplicates) the real Gate 3.5 replay.
    """
    steps: list[dict[str, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        steps.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    # 2026 Week 1 contract: Tuesday noon ET open; Sunday 1 PM ET lock.
    opens = datetime(2026, 9, 8, 12, 0, tzinfo=ET).astimezone(UTC)
    locks = datetime(2026, 9, 13, 13, 0, tzinfo=ET).astimezone(UTC)
    week = {"opens_at": opens.isoformat(), "locks_at": locks.isoformat()}
    record("Pre-open phase", week_phase(week, opens - timedelta(minutes=1)) == "upcoming", "Before Tuesday noon, picks remain closed.")
    record("Open phase", week_phase(week, opens + timedelta(minutes=1)) == "open", "After Tuesday noon, picks are editable.")
    record("Universal lock", week_phase(week, locks) == "locked", "At exactly Sunday 1:00 PM ET, picks are locked.")

    score = score_stat_line({"passing_yards": 250, "passing_tds": 2, "rushing_yards": 30})
    record("Fractional scoring", abs(score.points - 21.0) < 1e-9, "Production scoring formula returns the expected 21.0 points.")

    pool = []
    for pos in POSITIONS:
        pool.append({
            "id": f"{pos}-starter", "position": pos, "player_name": f"{pos} Starter",
            "availability_status": "HEALTHY", "score_total": 10.0, "team_abbr": "DET",
        })
        pool.append({
            "id": f"{pos}-backup", "position": pos, "player_name": f"{pos} Backup",
            "availability_status": "HEALTHY", "score_total": 12.0, "team_abbr": "GB",
        })
    # Make QB starter OUT so the already-locked emergency backup must activate.
    pool[0]["availability_status"] = "OUT"
    lineups = [
        {"id": "l1", "player_id": "p1", "confirmed_at": locks.isoformat()},
        {"id": "l2", "player_id": "p2", "confirmed_at": locks.isoformat()},
        {"id": "l3", "player_id": "p3", "confirmed_at": locks.isoformat()},
    ]
    players = [
        {"id": "p1", "nickname": "Alpha", "emoji": "🏈"},
        {"id": "p2", "nickname": "Bravo", "emoji": "🏈"},
        {"id": "p3", "nickname": "Charlie", "emoji": "🏈"},
    ]
    picks = []
    for lineup in lineups[:2]:
        for pos in POSITIONS:
            picks.append({
                "lineup_id": lineup["id"], "position": pos,
                "pool_player_id": f"{pos}-starter",
                "emergency_pool_player_id": f"{pos}-backup" if pos == "QB" else None,
            })
    # Third player intentionally submits only a QB to verify missing positions = 0.
    picks.append({"lineup_id": "l3", "position": "QB", "pool_player_id": "QB-starter", "emergency_pool_player_id": "QB-backup"})
    bundle = {"players": players, "lineups": lineups, "picks": picks, "pool": pool, "games": []}
    leaderboard = build_weekly_leaderboard(bundle)
    first = next(row for row in leaderboard if row["player_id"] == "p1")
    third = next(row for row in leaderboard if row["player_id"] == "p3")
    qb_row = next(row for row in first["roster"] if row["position"] == "QB")
    record("Emergency backup", bool(qb_row.get("emergency_activated")) and abs(float(qb_row["points"]) - 12.0) < 1e-9, "OUT starter activates the stored same-position emergency backup.")
    record("Incomplete lineup", abs(float(third["score"]) - 12.0) < 1e-9, "Missing positions score 0 instead of disqualifying the player.")

    # Alpha and Bravo are identical, so competition ranking should award both 1st/12.
    tied = sorted([row for row in leaderboard if row["player_id"] in {"p1", "p2"}], key=lambda r: r["player_id"])
    record("Weekly tie", all(row["rank"] == 1 and row["season_points_if_final"] == 12 for row in tied), "Identical weekly scores share 1st and both earn 12 season points.")
    record("Competition ranking", third["rank"] == 3 and third["season_points_if_final"] == 7, "After a tie for 1st, the next finish is 3rd and earns 7 points.")

    season_results = [
        {"player_id": "p1", "nickname_snapshot": "Alpha", "emoji_snapshot": "🏈", "weekly_score": 50.0, "finish_rank": 1, "season_points": 12},
        {"player_id": "p2", "nickname_snapshot": "Bravo", "emoji_snapshot": "🏈", "weekly_score": 50.0, "finish_rank": 1, "season_points": 12},
    ]
    season = build_season_standings(season_results)
    record("Season co-champion tie", len(season) == 2 and season[0]["rank"] == season[1]["rank"] == 1, "Equal season points and total fantasy points remain tied instead of inventing a tiebreaker.")

    success = all(step["status"] == "PASS" for step in steps)
    return {"success": success, "steps": steps, "passed": sum(step["status"] == "PASS" for step in steps), "total": len(steps)}
