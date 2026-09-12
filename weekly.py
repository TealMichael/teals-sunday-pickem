from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import TIMEZONE_NAME

UTC = timezone.utc
ET = ZoneInfo(TIMEZONE_NAME)
POSITIONS = ("QB", "RB", "WR", "TE", "K")
VISIBLE_POOL_SIZE = 5
HIDDEN_RANKING_SIZE = 10
WEEKLY_LOGIC_SCHEMA_VERSION = 3


def parse_timestamp(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


def week_phase(week: dict, now: datetime | None = None) -> str:
    now = (now or now_utc()).astimezone(UTC)
    opens = parse_timestamp(week.get("opens_at"))
    locks = parse_timestamp(week.get("locks_at"))
    if not opens or not locks:
        return "unavailable"
    if now < opens:
        return "upcoming"
    if now < locks:
        return "open"
    return "locked"


def seconds_until(value: str | datetime | None, now: datetime | None = None) -> int:
    target = parse_timestamp(value)
    if not target:
        return 0
    now = (now or now_utc()).astimezone(UTC)
    return max(0, int((target - now).total_seconds()))


def et_label(value: str | datetime | None, *, include_date: bool = True) -> str:
    dt = parse_timestamp(value)
    if not dt:
        return ""
    local = dt.astimezone(ET)
    if include_date:
        return local.strftime("%A, %b %-d • %-I:%M %p ET")
    return local.strftime("%-I:%M %p ET")


def position_pool(pool: list[dict], position: str, *, visible_only: bool = True) -> list[dict]:
    rows = [p for p in pool if str(p.get("position")) == position]
    if visible_only:
        rows = [p for p in rows if bool(p.get("is_visible", True))]
    return sorted(rows, key=lambda p: int(p.get("slot_rank") or 999))


def pool_is_ready(pool: list[dict]) -> bool:
    return all(len(position_pool(pool, position)) == VISIBLE_POOL_SIZE for position in POSITIONS)


def picks_by_position(picks: list[dict]) -> dict[str, dict]:
    return {str(p["position"]): p for p in picks if p.get("position") in POSITIONS}


def selected_pool_ids_missing_from_visible_pool(pool: list[dict], picks: list[dict]) -> list[str]:
    """Return saved starter/backup ids that are no longer in the visible pool.

    A published replacement may hide an OUT/ineligible player for future
    choices, but already-saved lineups still legitimately reference that row.
    """
    known = {str(row.get("id")) for row in pool if row.get("id")}
    referenced: set[str] = set()
    for pick in picks:
        if pick.get("pool_player_id"):
            referenced.add(str(pick["pool_player_id"]))
        if pick.get("emergency_pool_player_id"):
            referenced.add(str(pick["emergency_pool_player_id"]))
    return sorted(referenced - known)


def lineup_progress(picks: list[dict]) -> tuple[int, int]:
    chosen = len(picks_by_position(picks))
    return chosen, len(POSITIONS)


def required_backup_positions(picks: list[dict], pool_by_id: dict[str, dict]) -> list[str]:
    needs: list[str] = []
    for pos, pick in picks_by_position(picks).items():
        starter = pool_by_id.get(str(pick.get("pool_player_id")))
        if not starter:
            continue
        if str(starter.get("availability_status") or "HEALTHY").upper() != "QUESTIONABLE":
            continue
        backup_id = pick.get("emergency_pool_player_id")
        backup = pool_by_id.get(str(backup_id)) if backup_id else None
        if (
            not backup
            or str(backup.get("availability_status") or "HEALTHY").upper() == "OUT"
            or not bool(backup.get("schedule_eligible", True))
        ):
            needs.append(pos)
    return [pos for pos in POSITIONS if pos in needs]


def questionable_starter_positions(picks: list[dict], pool_by_id: dict[str, dict]) -> list[str]:
    """Return every position whose selected starter is currently Questionable.

    This intentionally differs from ``required_backup_positions``: a player can
    remain Questionable even after a valid emergency backup has been saved. The
    Sunday status card needs both facts so it can say "Questionable — backup
    ready" instead of hiding the injury flag once the lineup is technically
    complete.
    """
    questionable: list[str] = []
    for pos, pick in picks_by_position(picks).items():
        starter = pool_by_id.get(str(pick.get("pool_player_id")))
        if starter and safe_status(starter.get("availability_status")) == "QUESTIONABLE":
            questionable.append(pos)
    return [pos for pos in POSITIONS if pos in questionable]


def lineup_readiness(picks: list[dict], pool_by_id: dict[str, dict]) -> dict:
    """Summarize lineup health without changing any save/lock behavior."""
    chosen, total = lineup_progress(picks)
    by_pos = picks_by_position(picks)
    missing = [pos for pos in POSITIONS if pos not in by_pos]
    questionable = questionable_starter_positions(picks, pool_by_id)
    needs_backup = required_backup_positions(picks, pool_by_id)
    unavailable = unavailable_starter_positions(picks, pool_by_id)
    return {
        "chosen": chosen,
        "total": total,
        "missing": missing,
        "questionable": questionable,
        "needs_backup": needs_backup,
        "unavailable": unavailable,
        "ready": chosen == total and not needs_backup and not unavailable,
    }


def unavailable_starter_positions(picks: list[dict], pool_by_id: dict[str, dict]) -> list[str]:
    """Return saved starters that require a pre-lock replacement.

    An OUT starter can be safely covered by a valid emergency backup. A player
    whose game itself became ineligible (Monday flex, postponement outside the
    Sunday window, etc.) cannot be rescued by an emergency backup under the
    published rules and must be replaced before lock.
    """
    unavailable: list[str] = []
    for pos, pick in picks_by_position(picks).items():
        starter = pool_by_id.get(str(pick.get("pool_player_id")))
        if not starter:
            continue
        if not bool(starter.get("schedule_eligible", True)):
            unavailable.append(pos)
            continue
        if str(starter.get("availability_status") or "HEALTHY").upper() == "OUT":
            backup_id = pick.get("emergency_pool_player_id")
            backup = pool_by_id.get(str(backup_id)) if backup_id else None
            backup_valid = bool(
                backup
                and str(backup.get("availability_status") or "HEALTHY").upper() != "OUT"
                and bool(backup.get("schedule_eligible", True))
            )
            if not backup_valid:
                unavailable.append(pos)
    return [pos for pos in POSITIONS if pos in unavailable]


def schedule_ineligible_starter_positions(picks: list[dict], pool_by_id: dict[str, dict]) -> list[str]:
    positions: list[str] = []
    for pos, pick in picks_by_position(picks).items():
        starter = pool_by_id.get(str(pick.get("pool_player_id")))
        if starter and not bool(starter.get("schedule_eligible", True)):
            positions.append(pos)
    return [pos for pos in POSITIONS if pos in positions]


def first_incomplete_position(picks: list[dict], pool_by_id: dict[str, dict]) -> str | None:
    by_pos = picks_by_position(picks)
    for pos in POSITIONS:
        if pos not in by_pos:
            return pos
        starter = pool_by_id.get(str(by_pos[pos].get("pool_player_id")))
        if starter and not bool(starter.get("schedule_eligible", True)):
            return pos
        if starter and str(starter.get("availability_status") or "HEALTHY").upper() == "OUT":
            backup_id = by_pos[pos].get("emergency_pool_player_id")
            backup = pool_by_id.get(str(backup_id)) if backup_id else None
            backup_valid = bool(
                backup
                and str(backup.get("availability_status") or "HEALTHY").upper() != "OUT"
                and bool(backup.get("schedule_eligible", True))
            )
            if not backup_valid:
                return pos
        if starter and str(starter.get("availability_status") or "HEALTHY").upper() == "QUESTIONABLE":
            backup_id = by_pos[pos].get("emergency_pool_player_id")
            backup = pool_by_id.get(str(backup_id)) if backup_id else None
            if not backup or str(backup.get("availability_status") or "HEALTHY").upper() == "OUT":
                return pos
    return None


def next_position(position: str) -> str | None:
    try:
        idx = POSITIONS.index(position)
    except ValueError:
        return POSITIONS[0]
    return POSITIONS[idx + 1] if idx + 1 < len(POSITIONS) else None


def previous_position(position: str) -> str | None:
    try:
        idx = POSITIONS.index(position)
    except ValueError:
        return None
    return POSITIONS[idx - 1] if idx > 0 else None


def safe_status(value: str | None) -> str:
    status = str(value or "HEALTHY").upper()
    return status if status in {"HEALTHY", "QUESTIONABLE", "OUT"} else "HEALTHY"
