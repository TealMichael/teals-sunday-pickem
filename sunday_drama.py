"""Personal, read-only Sunday race moments from the existing public score bundle.

This module deliberately does not use saved emergency backup identifiers, external
NFL APIs, session state, or persistence. The caller must gate rendering to the
post-lock Sunday view; no lineup choices are exposed while picks are open.
"""
from __future__ import annotations

from typing import Any

SUNDAY_DRAMA_SCHEMA_VERSION = 1


def _display_name(row: dict[str, Any]) -> str:
    return str(row.get("nickname") or "Player")


def _closest_distinct_score(
    leaderboard: list[dict[str, Any]], own_score: float, *, above: bool
) -> dict[str, Any] | None:
    """Find the nearest different *score* (not next alphabetical tied row)."""
    opponents = [
        row for row in leaderboard
        if (float(row.get("score") or 0) > own_score if above
            else float(row.get("score") or 0) < own_score)
    ]
    if not opponents:
        return None
    target_score = (
        min(float(row.get("score") or 0) for row in opponents)
        if above else max(float(row.get("score") or 0) for row in opponents)
    )
    peers = sorted(
        (row for row in opponents if float(row.get("score") or 0) == target_score),
        key=lambda row: (_display_name(row).casefold(), str(row.get("player_id") or "")),
    )
    return {
        "names": [_display_name(row) for row in peers],
        "rank": int(peers[0].get("rank") or 0),
        "gap": round(abs(target_score - own_score), 1),
    }


def _own_game_moments(
    bundle: dict[str, Any], roster: list[dict[str, Any]]
) -> dict[str, Any]:
    """Only use game rows that positively match an active starter's team.

    Unmatched games are *unknown*, not automatically live or final. A backup is
    only counted when gate4's existing scoring logic actually activated it.
    """
    games_by_team: dict[str, dict[str, Any]] = {}
    for game in bundle.get("games") or []:
        for team_key in ("home_team", "away_team"):
            team = str(game.get(team_key) or "").upper()
            if team:
                games_by_team[team] = game

    counts = {"live": 0, "scheduled": 0, "final": 0, "unknown": 0}
    known_roster = 0
    for slot in roster:
        if slot.get("missing") or not (slot.get("player") or {}).get("id"):
            # No player selected or a missing pool row is not a known game.
            continue
        known_roster += 1
        team = str((slot.get("player") or {}).get("team_abbr") or "").upper()
        game = games_by_team.get(team)
        if not game:
            counts["unknown"] += 1
            continue
        status = str(game.get("game_status") or "").upper()
        if status == "FINAL" or bool(game.get("completed")):
            counts["final"] += 1
        elif status == "LIVE":
            counts["live"] += 1
        elif status == "SCHEDULED":
            counts["scheduled"] += 1
        else:
            counts["unknown"] += 1

    counts["known_players"] = known_roster
    return counts


def build_personal_sunday_drama(
    bundle: dict[str, Any],
    leaderboard: list[dict[str, Any]],
    current_player_id: str,
) -> dict[str, Any] | None:
    """Describe *this* player's current race using confirmed scores only.

    No trends, movement since the prior refresh, win probabilities, or future
    projections can be claimed without actual historical or predictive data.
    """
    own = next(
        (row for row in leaderboard if str(row.get("player_id") or "") == str(current_player_id)),
        None,
    )
    if own is None or not current_player_id:
        return None

    score = float(own.get("score") or 0)
    peers = sorted(
        (_display_name(row) for row in leaderboard
         if str(row.get("player_id") or "") != str(current_player_id)
         and float(row.get("score") or 0) == score),
        key=str.casefold,
    )
    roster = list(own.get("roster") or [])
    chasing = _closest_distinct_score(leaderboard, score, above=True)
    holding_off = _closest_distinct_score(leaderboard, score, above=False)
    # One real nearby rival is enough for a useful, factual comparison. If
    # multiple people share that score, don't arbitrarily choose one of them.
    rival_games = None
    nearest = chasing or holding_off
    if nearest and len(nearest["names"]) == 1:
        matches = [
            row for row in leaderboard
            if str(row.get("player_id") or "") != str(current_player_id)
            and int(row.get("rank") or 0) == nearest["rank"]
            and _display_name(row) == nearest["names"][0]
        ]
        if len(matches) == 1:
            game_counts = _own_game_moments(bundle, list(matches[0].get("roster") or []))
            if game_counts["live"] or game_counts["scheduled"]:
                rival_games = {"name": nearest["names"][0], "games": game_counts}
    top_scorers = sorted(
        (
            {
                "name": str((slot.get("player") or {}).get("player_name") or "Player"),
                "position": str(slot.get("position") or ""),
                "points": round(float(slot.get("points") or 0), 1),
            }
            for slot in roster if not slot.get("missing") and slot.get("player")
            and float(slot.get("points") or 0) > 0
        ),
        key=lambda item: (-item["points"], item["position"], item["name"].casefold()),
    )
    return {
        "rank": int(own.get("rank") or 0),
        "score": round(score, 1),
        "total_lineups": len(leaderboard),
        "tied_with": peers,
        "chasing": chasing,
        "holding_off": holding_off,
        "rival_games": rival_games,
        "top_scorer": top_scorers[0] if top_scorers else None,
        "games": _own_game_moments(bundle, roster),
    }
