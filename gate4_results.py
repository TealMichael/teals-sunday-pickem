from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gate4 import build_season_standings, build_weekly_leaderboard, season_points_for_rank

UTC = timezone.utc


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def archive_week_results(store, week: dict[str, Any]) -> dict[str, Any]:
    """Archive one finalized week into compact history rows.

    Idempotent: weekly_results upserts by (week_id, player_id), so a Monday
    retry or Commissioner re-run cannot duplicate awards.
    """
    bundle = store.get_week_public_bundle(str(week["id"]), ttl_seconds=0.01)
    leaderboard = build_weekly_leaderboard(bundle)
    stamp = str(week.get("finalized_at") or _iso_now())
    rows: list[dict[str, Any]] = []
    for row in leaderboard:
        rank = int(row["rank"])
        rows.append({
            "week_id": str(week["id"]),
            "season": int(week["season"]),
            "nfl_week": int(week["nfl_week"]),
            "player_id": str(row["player_id"]),
            "nickname_snapshot": str(row["nickname"]),
            "emoji_snapshot": str(row["emoji"]),
            "weekly_score": float(row["score"]),
            "finish_rank": rank,
            "season_points": season_points_for_rank(rank),
            "is_champion": rank == 1,
            "finalized_at": stamp,
        })
    store.upsert_weekly_results(rows)
    store.update_week_data_state(str(week["id"]), results_archived_at=stamp)

    champions: list[dict[str, Any]] = []
    if int(week.get("nfl_week") or 0) == 18:
        season_results = store.get_weekly_results(season=int(week["season"]))
        standings = build_season_standings(season_results)
        if standings:
            top = standings[0]
            champions = [
                row for row in standings
                if int(row["season_points"]) == int(top["season_points"])
                and float(row["total_fantasy_points"]) == float(top["total_fantasy_points"])
            ]
            store.upsert_season_champions([
                {
                    "season": int(week["season"]),
                    "player_id": row.get("player_id"),
                    "nickname_snapshot": row["nickname"],
                    "emoji_snapshot": row["emoji"],
                    "season_points": int(row["season_points"]),
                    "total_fantasy_points": float(row["total_fantasy_points"]),
                    "awarded_at": stamp,
                }
                for row in champions
            ])
    return {"rows": rows, "champions": champions}
