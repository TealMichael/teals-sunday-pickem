"""Read-only personal season story and achievements from archived FINAL weekly results.

No saved-lineup access, player-pool access, writes, extra NFL requests, or new tables.
Awards are reproducible from archived results and never imply unverified feats.
"""
from __future__ import annotations

from typing import Any

from gate4 import build_season_standings


def _first_week(weeks: list[int], predicate) -> int | None:
    return next((week for week in weeks if predicate(week)), None)


def build_personal_season_story(
    results: list[dict[str, Any]], player_id: str,
) -> dict[str, Any]:
    """Summarize one participant's season using final archives for *all* players.

    Only actual player results become timeline rows; missing weeks are not
    represented as invented zero-point finishes or consecutive podiums.
    Season ranking uses the exact shared standings logic and competition ties.
    """
    if not str(player_id or "").strip():
        return {"weeks": [], "awards": [], "summary": None}

    valid = [row for row in results if row.get("player_id") and int(row.get("nfl_week") or 0) > 0]
    if not valid:
        return {"weeks": [], "awards": [], "summary": None}
    # Caller scopes results to one NFL season; don't quietly combine seasons if
    # an incorrectly broad caller accidentally supplies several.
    seasons = {int(row.get("season") or 0) for row in valid}
    if len(seasons) > 1:
        current_season = max(seasons)
        valid = [row for row in valid if int(row.get("season") or 0) == current_season]

    week_numbers = sorted({int(row["nfl_week"]) for row in valid})
    rankings: dict[int, dict[str, dict[str, Any]]] = {}
    for week in week_numbers:
        to_date = [row for row in valid if int(row["nfl_week"]) <= week]
        rankings[week] = {
            str(row["player_id"]): row for row in build_season_standings(to_date)
        }

    own_by_week = {
        int(row["nfl_week"]): row for row in valid
        if str(row["player_id"]) == str(player_id)
    }
    own_weeks = sorted(own_by_week)
    if not own_weeks:
        return {"weeks": [], "awards": [], "summary": None}

    timeline: list[dict[str, Any]] = []
    best_score: float | None = None
    best_week: int | None = None
    best_climb = 0
    best_climb_week: int | None = None
    podium_streak = 0
    longest_podium_streak = 0
    last_podium_week: int | None = None
    first_hat_trick_week: int | None = None
    season_lead_week: int | None = None

    for week in own_weeks:
        source = own_by_week[week]
        score = round(float(source.get("weekly_score") or 0.0), 1)
        finish = int(source.get("finish_rank") or 0)
        current = rankings[week][str(player_id)]
        previous_weeks = [prior for prior in week_numbers if prior < week]
        previous_rank = (
            rankings[previous_weeks[-1]].get(str(player_id), {}).get("rank")
            if previous_weeks else None
        )
        move = int(previous_rank) - int(current["rank"]) if previous_rank is not None else None
        if move is not None and move > best_climb:
            best_climb = move
            best_climb_week = week
        if best_score is None or score > best_score:
            best_score, best_week = score, week

        if finish > 0 and finish <= 3:
            podium_streak = podium_streak + 1 if last_podium_week == week - 1 else 1
            last_podium_week = week
            longest_podium_streak = max(longest_podium_streak, podium_streak)
            if podium_streak == 3 and first_hat_trick_week is None:
                first_hat_trick_week = week
        else:
            podium_streak = 0
            last_podium_week = None

        if season_lead_week is None and int(current["rank"]) == 1 and len(rankings[week]) > 1:
            season_lead_week = week

        timeline.append({
            "week": week,
            "finish_rank": finish,
            "score": score,
            "earned_points": int(source.get("season_points") or 0),
            "season_points": int(current["season_points"]),
            "season_rank": int(current["rank"]),
            "rank_move": move,
            "is_personal_best": best_week == week,
        })

    def badge(code: str, icon: str, title: str, detail: str, week: int | None) -> dict[str, Any] | None:
        if week is None:
            return None
        return {"code": code, "icon": icon, "title": title, "detail": detail, "week": week}

    first_win = _first_week(own_weeks, lambda w: int(own_by_week[w].get("finish_rank") or 0) == 1)
    first_podium = _first_week(own_weeks, lambda w: 0 < int(own_by_week[w].get("finish_rank") or 0) <= 3)
    first_century = _first_week(own_weeks, lambda w: float(own_by_week[w].get("weekly_score") or 0) >= 100)
    awards = [
        badge("first_win", "🏆", "First Victory", "First weekly 1st-place finish", first_win),
        badge("hat_trick", "🥇", "Podium Hat Trick", "Three consecutive weeks finishing in the top three", first_hat_trick_week),
        badge("climber", "📈", "Big Climb", "Moved up at least three places in the season standings", best_climb_week if best_climb >= 3 else None),
        badge("century", "💯", "100-Point Club", "Scored 100 or more fantasy points in one week", first_century),
        badge("first_podium", "🥉", "Podium Debut", "First weekly top-three finish", first_podium),
        badge("season_lead", "⭐", "Season Leader", "Reached first place in the season standings", season_lead_week),
        badge("first_week", "🏈", "Opening Kickoff", "Recorded a result in your first finalized Sunday", own_weeks[0]),
    ]
    awards = [award for award in awards if award is not None]
    latest_week = week_numbers[-1]
    latest_rank = rankings[latest_week].get(str(player_id))
    # The participant may have missed the most recently finalized week; show
    # their real current season rank, not the rank at their last played week.
    summary = {
        "season_rank": int(latest_rank["rank"]) if latest_rank else None,
        "season_points": int(latest_rank["season_points"]) if latest_rank else 0,
        "total_fantasy_points": round(float(latest_rank["total_fantasy_points"]), 1) if latest_rank else 0.0,
        "weeks_played": len(own_weeks),
        "finalized_weeks": len(week_numbers),
        "best_score": best_score,
        "best_week": best_week,
        "best_climb": best_climb,
        "longest_podium_streak": longest_podium_streak,
        "latest_played_week": own_weeks[-1],
        "latest_finalized_week": latest_week,
    }
    return {"weeks": list(reversed(timeline)), "awards": awards, "summary": summary}
