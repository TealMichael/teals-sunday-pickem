from __future__ import annotations

from collections import Counter
from math import ceil
from typing import Any

from gate4 import build_season_standings
from weekly import POSITIONS

NEWSLETTER_LOGIC_SCHEMA_VERSION = 2


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


def _join_names(names: list[str]) -> str:
    clean = [str(name or "Player").strip() or "Player" for name in names]
    if not clean:
        return "Player"
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def _identity(row: dict[str, Any]) -> str:
    player_id = str(row.get("player_id") or "").strip()
    if player_id:
        return f"id:{player_id}"
    return f"name:{str(row.get('nickname') or row.get('nickname_snapshot') or 'Player').casefold()}"


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
    """Keep every weekly finisher, while marking competition-rank ties clearly."""
    rows = sorted(
        results,
        key=lambda row: (
            int(row.get("finish_rank") or 999),
            -float(row.get("weekly_score") or 0),
            str(row.get("nickname_snapshot") or "Player").casefold(),
        ),
    )
    rank_counts = Counter(int(row.get("finish_rank") or 0) for row in rows)
    return " • ".join(
        (
            f"{int(row.get('finish_rank') or 0)}"
            f"{'T' if rank_counts[int(row.get('finish_rank') or 0)] > 1 else ''} "
            f"{row.get('nickname_snapshot') or 'Player'} "
            f"{float(row.get('weekly_score') or 0):.1f}"
        )
        for row in rows
    )


def compact_season_top_five(season_results: list[dict[str, Any]]) -> str:
    """Return only the five leading season entries, using the app's standings order."""
    season = build_season_standings(season_results)
    top_five = season[:5]
    if not top_five:
        return ""
    rank_counts = Counter(int(row.get("rank") or 0) for row in season)
    return " • ".join(
        (
            f"{int(row.get('rank') or 0)}"
            f"{'T' if rank_counts[int(row.get('rank') or 0)] > 1 else ''} "
            f"{row.get('nickname') or 'Player'} "
            f"{int(row.get('season_points') or 0)} pts"
        )
        for row in top_five
    )


def commissioner_story(
    *,
    final_week: dict[str, Any],
    final_results: list[dict[str, Any]],
    perfect: dict[str, Any],
    season_results: list[dict[str, Any]],
) -> str | None:
    """Choose one genuinely notable, data-backed sentence for the weekly text.

    The newsletter should feel like a commissioner recap, not a pile of
    automatic trivia. Stronger stories win; ordinary weeks simply omit this line.
    """
    week_num = int(final_week.get("nfl_week") or 0)
    weekly = sorted(
        final_results,
        key=lambda row: (
            int(row.get("finish_rank") or 999),
            -float(row.get("weekly_score") or 0),
            str(row.get("nickname_snapshot") or "Player").casefold(),
        ),
    )
    champions = [row for row in weekly if int(row.get("finish_rank") or 0) == 1]
    if not champions:
        return None

    champion_names = [str(row.get("nickname_snapshot") or "Player") for row in champions]
    champion_name = _join_names(champion_names)
    champion_score = float(champions[0].get("weekly_score") or 0)
    perfect_gap: float | None = None
    if perfect.get("complete"):
        perfect_score = float(perfect.get("score") or 0)
        gap = round(perfect_score - champion_score, 1)
        if gap >= 0:
            perfect_gap = gap

    # A shared weekly crown is always a story. If the winning score was also
    # unusually close to the best legal five, fold that into the same sentence.
    if len(champions) > 1:
        if perfect_gap is not None and perfect_gap <= 10:
            return (
                f"{champion_name} shared the Week {week_num} crown at {champion_score:.1f}, "
                f"finishing just {perfect_gap:.1f} points shy of the perfect possible lineup."
            )
        return f"{champion_name} shared the Week {week_num} crown at {champion_score:.1f}."

    champion = champions[0]
    champion_id = _identity({
        "player_id": champion.get("player_id"),
        "nickname": champion.get("nickname_snapshot"),
    })

    previous_week_results = [
        row for row in season_results
        if int(row.get("nfl_week") or 0) == week_num - 1
    ]
    if week_num > 1 and any(
        int(row.get("finish_rank") or 0) == 1
        and _identity({
            "player_id": row.get("player_id"),
            "nickname": row.get("nickname_snapshot"),
        }) == champion_id
        for row in previous_week_results
    ):
        return f"{champion_name} made it back-to-back weekly wins with {champion_score:.1f} points."

    current_season = build_season_standings(season_results)
    previous_season = build_season_standings(
        [row for row in season_results if int(row.get("nfl_week") or 0) < week_num]
    )

    # A new leader is more interesting than a routine winning score.
    if week_num > 1 and current_season and previous_season:
        current_leader = current_season[0]
        previous_leader = previous_season[0]
        if _identity(current_leader) != _identity(previous_leader):
            return (
                f"{current_leader.get('nickname') or 'Player'} moved into the season lead "
                f"with {int(current_leader.get('season_points') or 0)} points after Week {week_num}."
            )

    if perfect_gap is not None and perfect_gap <= 10:
        return (
            f"{champion_name} won Week {week_num} with {champion_score:.1f}, "
            f"just {perfect_gap:.1f} points shy of a perfect lineup."
        )

    # Use the next distinct score so a tied second place does not distort margin.
    next_distinct = next(
        (
            float(row.get("weekly_score") or 0)
            for row in weekly
            if float(row.get("weekly_score") or 0) < champion_score
        ),
        None,
    )
    if next_distinct is not None:
        margin = round(champion_score - next_distinct, 1)
        if margin >= 15:
            return f"{champion_name} ran away with Week {week_num}, winning by {margin:.1f} points."

    if len(current_season) >= 5:
        spread = int(current_season[0].get("season_points") or 0) - int(current_season[4].get("season_points") or 0)
        if spread <= 5:
            return f"The season race is packed: only {spread} points separate first through fifth."

    if week_num > 1 and current_season and previous_season:
        before = {_identity(row): row for row in previous_season}
        movers = []
        for row in current_season[:5]:
            old = before.get(_identity(row))
            if not old:
                continue
            places = int(old.get("rank") or 0) - int(row.get("rank") or 0)
            if places >= 4:
                movers.append((places, str(row.get("nickname") or "Player")))
        if movers:
            places, name = sorted(movers, key=lambda item: (-item[0], item[1].casefold()))[0]
            return f"{name} jumped {places} spots into the season Top 5 after Week {week_num}."

    if week_num == 1:
        return f"{champion_name} opened the season with the Week 1 win at {champion_score:.1f}."

    return None


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

    story = commissioner_story(
        final_week=final_week,
        final_results=final_results,
        perfect=perfect,
        season_results=season_results,
    )
    if story:
        lines.append(f"🗣️ Commish: {story}")

    standings = compact_final_standings(final_results)
    if standings:
        lines.append(f"🏆 Week {week_num}: {standings}")

    season_top_five = compact_season_top_five(season_results)
    if season_top_five:
        lines.append("📈 Season Top 5: " + season_top_five)

    clean_url = str(lineup_url or "").strip()
    if clean_url:
        if next_week:
            lines.append(f"👉 Week {int(next_week.get('nfl_week') or 0)} lineup: {clean_url}")
        else:
            lines.append(f"👉 Next lineup: {clean_url}")
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
