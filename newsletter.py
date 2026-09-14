from __future__ import annotations

from math import ceil
from typing import Any

from gate4 import build_season_standings
from weekly import POSITIONS

NEWSLETTER_LOGIC_SCHEMA_VERSION = 1


def _score(row: dict[str, Any]) -> float:
    manual = row.get("manual_score_override")
    value = manual if manual is not None else row.get("score_total")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _short_name(value: Any) -> str:
    """Compact an NFL player name for a text-message recap."""
    name = " ".join(str(value or "Player").split())
    if not name:
        return "Player"
    pieces = name.split(" ")
    if len(pieces) == 1:
        return pieces[0]
    # Last names keep the newsletter much shorter than full names while the
    # position label still makes the player easy to recognize.
    return pieces[-1]


def perfect_lineup(pool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the highest-scoring legal five from the week's visible 25-player pool.

    The final visible pool is the set participants could actually choose from
    after any pre-lock OUT-player replacement. Hidden reserve rows are ignored.
    """
    winners: list[dict[str, Any]] = []
    total = 0.0
    for position in POSITIONS:
        candidates = [
            row for row in pool_rows
            if str(row.get("position") or "").upper() == position
            and bool(row.get("is_visible", False))
        ]
        if not candidates:
            return {"complete": False, "players": winners, "score": round(total, 1)}
        candidates.sort(
            key=lambda row: (
                -_score(row),
                int(row.get("slot_rank") or 999),
                str(row.get("player_name") or "").casefold(),
            )
        )
        winner = dict(candidates[0])
        winner["points"] = round(_score(winner), 1)
        winner["short_name"] = _short_name(winner.get("player_name"))
        winners.append(winner)
        total += float(winner["points"])
    return {"complete": True, "players": winners, "score": round(total, 1)}


def compact_final_standings(results: list[dict[str, Any]]) -> str:
    rows = sorted(
        results,
        key=lambda row: (
            int(row.get("finish_rank") or 999),
            -float(row.get("weekly_score") or 0),
            str(row.get("nickname_snapshot") or "Player").casefold(),
        ),
    )
    return " | ".join(
        f"{int(row.get('finish_rank') or 0)} {row.get('nickname_snapshot') or 'Player'} {float(row.get('weekly_score') or 0):.1f}"
        for row in rows
    )


def build_tuesday_newsletter(
    *,
    final_week: dict[str, Any],
    final_results: list[dict[str, Any]],
    perfect: dict[str, Any],
    season_results: list[dict[str, Any]],
    next_week: dict[str, Any] | None,
    lineup_url: str,
) -> str:
    """Build the editable, copy/paste Tuesday text newsletter."""
    week_num = int(final_week.get("nfl_week") or 0)
    lines = [f"🏈 Teal's Sunday Pick'em — Week {week_num} Final"]

    standings = compact_final_standings(final_results)
    if standings:
        lines.append("Final: " + standings)

    if perfect.get("complete"):
        player_text = " • ".join(
            f"{row.get('position')} {row.get('short_name')}" for row in perfect.get("players") or []
        )
        lines.append(f"⭐ Perfect 5: {player_text} = {float(perfect.get('score') or 0):.1f}")

    season = build_season_standings(season_results)
    if season:
        top = season[0]
        tied = [
            row for row in season
            if int(row.get("season_points") or 0) == int(top.get("season_points") or 0)
            and float(row.get("total_fantasy_points") or 0) == float(top.get("total_fantasy_points") or 0)
        ]
        leaders = "+".join(str(row.get("nickname") or "Player") for row in tied)
        label = "Season leaders" if len(tied) > 1 else "Season leader"
        lines.append(f"🏆 {label}: {leaders} — {int(top.get('season_points') or 0)} pts")

    clean_url = str(lineup_url or "").strip()
    if clean_url:
        if next_week:
            lines.append(f"Set Week {int(next_week.get('nfl_week') or 0)}: {clean_url}")
        else:
            lines.append(f"Set next week's lineup: {clean_url}")
    return "\n".join(lines)


def sms_segment_estimate(text: str) -> int:
    """Approximate carrier SMS segments; iMessage/RCS may behave differently."""
    value = str(text or "")
    if not value:
        return 0
    # Newsletter intentionally uses emoji, so it normally takes the UCS-2 path:
    # 70 chars for one SMS, ~67 chars/segment once concatenated.
    unicode_mode = any(ord(ch) > 127 for ch in value)
    if unicode_mode:
        return 1 if len(value) <= 70 else ceil(len(value) / 67)
    return 1 if len(value) <= 160 else ceil(len(value) / 153)


def load_newsletter_data(store, current_week: dict[str, Any]) -> dict[str, Any] | None:
    """Load the most recently finalized Pick'em week plus next-week context."""
    season = int(current_week.get("season") or 0)
    all_results = list(store.get_weekly_results(season=season))
    if not all_results:
        return None

    finalized_week_num = max(int(row.get("nfl_week") or 0) for row in all_results)
    final_results = [row for row in all_results if int(row.get("nfl_week") or 0) == finalized_week_num]
    final_week = store.get_week_by_season_week(season, finalized_week_num)
    if not final_week:
        return None

    pool = list(store.get_full_week_pool(str(final_week["id"])))
    perfect = perfect_lineup(pool)

    next_week = current_week if int(current_week.get("nfl_week") or 0) > finalized_week_num else None
    return {
        "final_week": final_week,
        "final_results": final_results,
        "season_results": all_results,
        "perfect": perfect,
        "next_week": next_week,
    }
