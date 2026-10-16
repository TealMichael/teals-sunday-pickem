"""Compact, factual engagement copy. No new scoring, lineup, or NFL fetches.

Everything in this module is pure so it can be tested without Streamlit or a DB.
Previous weeks always come from reconciled weekly_results, never unfinished games.
"""
from __future__ import annotations

from typing import Any

REACTION_OPTIONS = ("🔥", "😂", "👏", "👀")


def previous_results(rows: list[dict[str, Any]], nfl_week: int) -> list[dict[str, Any]]:
    return [r for r in rows if 0 < int(r.get("nfl_week") or 0) < nfl_week]


def personal_goal(rows: list[dict[str, Any]], player_id: str) -> dict[str, Any]:
    """Only one achievable, measurable weekly goal; no points are awarded."""
    own = sorted((r for r in rows if str(r.get("player_id")) == str(player_id)),
                 key=lambda r: int(r.get("nfl_week") or 0))
    if len(own) >= 2:
        average = round(sum(float(r.get("weekly_score") or 0) for r in own) / len(own), 1)
        return {"kind": "average", "threshold": average,
                "label": f"Beat your {average:.1f}-point season average"}
    if len(own) == 1:
        score = round(float(own[0].get("weekly_score") or 0), 1)
        return {"kind": "personal_best", "threshold": score,
                "label": f"Beat your {score:.1f}-point previous score"}
    return {"kind": "top_five", "threshold": 5, "label": "Finish in the Top 5"}


def goal_progress(goal: dict[str, Any], own: dict[str, Any] | None, *, final: bool) -> str:
    if not own:
        return f"🎯 {goal['label']}"
    if goal["kind"] == "top_five":
        reached = 0 < int(own.get("rank") or 0) <= 5
    else:
        reached = float(own.get("score") or 0) > float(goal["threshold"])
    if final:
        return f"{'✅ Goal achieved' if reached else '🎯 Goal not reached'}: {goal['label']}"
    return f"{'✅ Goal currently met' if reached else '🎯 Your goal'}: {goal['label']}"


def pregame_pulse(results: list[dict[str, Any]], player_id: str, week_number: int) -> dict[str, str]:
    history = previous_results(results, week_number)
    goal = personal_goal(history, player_id)
    own_weeks = [r for r in history if str(r.get("player_id")) == str(player_id)]
    if not own_weeks:
        return {"heading": "Your Sunday story starts here", "detail": "Five picks. A fresh chance to make a run.",
                "goal": goal["label"]}
    latest = max(own_weeks, key=lambda row: int(row.get("nfl_week") or 0))
    latest_week = int(latest.get("nfl_week") or 0)
    peers = [r for r in history if int(r.get("nfl_week") or 0) == latest_week
             and str(r.get("player_id")) != str(player_id)]
    if peers:
        closest = min(peers, key=lambda r: (abs(float(r.get("weekly_score") or 0) - float(latest.get("weekly_score") or 0)),
                                            str(r.get("nickname_snapshot") or "").casefold()))
        difference = float(latest.get("weekly_score") or 0) - float(closest.get("weekly_score") or 0)
        other = str(closest.get("nickname_snapshot") or "another player")
        if abs(difference) < 0.05:
            story = f"You tied {other} in Week {latest_week}. Ready for the rematch?"
        elif difference > 0:
            story = f"You finished {difference:.1f} points ahead of {other} in Week {latest_week}."
        else:
            story = f"{other} finished {abs(difference):.1f} points ahead of you in Week {latest_week}."
    else:
        story = f"You scored {float(latest.get('weekly_score') or 0):.1f} points in Week {latest_week}."
    return {"heading": f"Your Week {week_number} outlook", "detail": story, "goal": goal["label"]}


def snapshot_for(leaderboard: list[dict[str, Any]], player_id: str) -> dict[str, Any] | None:
    own = next((r for r in leaderboard if str(r.get("player_id")) == str(player_id)), None)
    if not own:
        return None
    return {"rank": int(own.get("rank") or 0),
            "score": round(float(own.get("score") or 0), 2),
            "player_count": len(leaderboard)}


def live_pulse(leaderboard: list[dict[str, Any]], player_id: str,
               old: dict[str, Any] | None, goal: dict[str, Any], *, final: bool = False) -> dict[str, str] | None:
    own = next((r for r in leaderboard if str(r.get("player_id")) == str(player_id)), None)
    if not own:
        return None
    rank, score = int(own.get("rank") or 0), float(own.get("score") or 0)
    heading = f"You're {ordinal(rank)} · {score:.1f} points"
    detail = "Your current place in the weekly standings."
    if not final and old and old.get("rank") is not None and old.get("score") is not None:
        earlier_rank = int(old["rank"])
        earlier_score = float(old["score"])
        if rank < earlier_rank:
            heading = f"You moved up {earlier_rank-rank} place{'s' if earlier_rank-rank != 1 else ''}!"
            detail = f"You're now {ordinal(rank)} with {score:.1f} points."
        elif rank > earlier_rank:
            heading = f"You're now {ordinal(rank)}"
            detail = f"You were {ordinal(earlier_rank)} at your previous check-in."
        elif score - earlier_score >= 0.05:
            heading = f"You added {score-earlier_score:.1f} points!"
            detail = f"You're {ordinal(rank)} with {score:.1f} points."
    if detail == "Your current place in the weekly standings." and not final:
        higher = [r for r in leaderboard if float(r.get("score") or 0) > score]
        if higher:
            nearest_score = min(float(r.get("score") or 0) for r in higher)
            names = sorted((str(r.get("nickname") or "Player") for r in higher
                           if abs(float(r.get("score") or 0)-nearest_score) < 0.001), key=str.casefold)
            rival = names[0] if len(names) == 1 else "the next place"
            detail = f"{nearest_score-score:.1f} points behind {rival}."
    if final:
        heading = f"You finished {ordinal(rank)}!"
        detail = f"Your final score: {score:.1f} points."
    return {"heading": heading, "detail": detail,
            "goal": goal_progress(goal, own, final=final)}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"


def reaction_totals(rows: list[dict[str, Any]], target_id: str, eligible: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get("value") or {}
        if str(value.get("target") or "") != target_id:
            continue
        sender = str(row.get("key") or "").rsplit(":", 1)[-1]
        emoji = str(value.get("emoji") or "")
        if sender not in eligible or sender == target_id or emoji not in REACTION_OPTIONS:
            continue
        counts[emoji] = counts.get(emoji, 0) + 1
    return counts
