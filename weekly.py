from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import TIMEZONE_NAME

UTC = timezone.utc
ET = ZoneInfo(TIMEZONE_NAME)
POSITIONS = ("QB", "RB", "WR", "TE", "K")
VISIBLE_POOL_SIZE = 5
HIDDEN_RANKING_SIZE = 10


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


def lineup_progress(picks: list[dict]) -> tuple[int, int]:
    chosen = len(picks_by_position(picks))
    return chosen, len(POSITIONS)


def required_backup_positions(picks: list[dict], pool_by_id: dict[str, dict]) -> list[str]:
    needs: list[str] = []
    for pos, pick in picks_by_position(picks).items():
        starter = pool_by_id.get(str(pick.get("pool_player_id")))
        if not starter:
            continue
        if str(starter.get("availability_status") or "HEALTHY").upper() == "QUESTIONABLE" and not pick.get("emergency_pool_player_id"):
            needs.append(pos)
    return [pos for pos in POSITIONS if pos in needs]


def first_incomplete_position(picks: list[dict], pool_by_id: dict[str, dict]) -> str | None:
    by_pos = picks_by_position(picks)
    for pos in POSITIONS:
        if pos not in by_pos:
            return pos
        starter = pool_by_id.get(str(by_pos[pos].get("pool_player_id")))
        if starter and str(starter.get("availability_status") or "HEALTHY").upper() == "QUESTIONABLE":
            if not by_pos[pos].get("emergency_pool_player_id"):
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
