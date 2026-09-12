from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from weekly import POSITIONS

SEASON_POINTS = {1: 12, 2: 9, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1}
GATE4_LOGIC_SCHEMA_VERSION = 3


def _score(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    manual = row.get("manual_score_override")
    value = manual if manual is not None else row.get("score_total")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def competition_ranks(values: Iterable[float]) -> list[int]:
    ranks: list[int] = []
    previous = None
    current_rank = 0
    for index, value in enumerate(values, start=1):
        if previous is None or value != previous:
            current_rank = index
        ranks.append(current_rank)
        previous = value
    return ranks


def season_points_for_rank(rank: int) -> int:
    return int(SEASON_POINTS.get(int(rank), 0))


def _effective_pick(pick: dict[str, Any], pool_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, bool]:
    starter = pool_by_id.get(str(pick.get("pool_player_id")))
    backup = pool_by_id.get(str(pick.get("emergency_pool_player_id"))) if pick.get("emergency_pool_player_id") else None
    # Emergency activation contract: the backup becomes public/active only when
    # the locked starter is officially OUT/inactive. A Questionable player who
    # plays remains the starter, even if the backup is stored privately.
    backup_valid = bool(
        backup
        and str(backup.get("availability_status") or "HEALTHY").upper() != "OUT"
        and bool(backup.get("schedule_eligible", True))
    )
    if (
        starter
        and bool(starter.get("schedule_eligible", True))
        and str(starter.get("availability_status") or "").upper() == "OUT"
        and backup_valid
    ):
        return backup, True
    return starter, False


def game_status_text(pool_row: dict[str, Any] | None, games_by_team: dict[str, dict[str, Any]]) -> str:
    if not pool_row:
        return ""
    team = str(pool_row.get("team_abbr") or "").upper()
    game = games_by_team.get(team)
    if not game:
        status = str(pool_row.get("game_status") or pool_row.get("score_status") or "SCHEDULED").upper()
        return status
    status = str(game.get("game_status") or "SCHEDULED").upper()
    if status == "LIVE":
        period = game.get("period")
        clock = str(game.get("game_clock") or "").strip()
        detail = f"Q{period}" if period else "LIVE"
        if clock:
            detail += f" • {clock}"
        return f"LIVE • {detail}" if not detail.startswith("LIVE") else detail
    if status == "FINAL" or game.get("completed"):
        return "FINAL"
    return status


def build_weekly_leaderboard(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    players = {str(row["id"]): row for row in bundle.get("players") or []}
    lineups = list(bundle.get("lineups") or [])
    picks = list(bundle.get("picks") or [])
    pool = list(bundle.get("pool") or [])
    games = list(bundle.get("games") or [])
    pool_by_id = {str(row["id"]): row for row in pool}
    games_by_team: dict[str, dict[str, Any]] = {}
    for game in games:
        for key in ("home_team", "away_team"):
            team = str(game.get(key) or "").upper()
            if team:
                games_by_team[team] = game

    picks_by_lineup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pick in picks:
        picks_by_lineup[str(pick.get("lineup_id"))].append(pick)

    rows: list[dict[str, Any]] = []
    for lineup in lineups:
        lineup_picks = picks_by_lineup.get(str(lineup.get("id")), [])
        if not lineup_picks:
            continue
        player = players.get(str(lineup.get("player_id"))) or {}
        by_position = {str(p.get("position")): p for p in lineup_picks}
        roster: list[dict[str, Any]] = []
        total = 0.0
        for position in POSITIONS:
            pick = by_position.get(position)
            if not pick:
                roster.append({"position": position, "missing": True, "points": 0.0})
                continue
            active, emergency_activated = _effective_pick(pick, pool_by_id)
            starter = pool_by_id.get(str(pick.get("pool_player_id")))
            backup = pool_by_id.get(str(pick.get("emergency_pool_player_id"))) if pick.get("emergency_pool_player_id") else None
            points = _score(active)
            total += points
            roster.append({
                "position": position,
                "missing": False,
                "player": active,
                "starter": starter,
                "backup": backup,
                "points": round(points, 3),
                "emergency_activated": emergency_activated,
                "game_status_text": game_status_text(active, games_by_team),
            })
        rows.append({
            "player_id": str(lineup.get("player_id")),
            "lineup_id": str(lineup.get("id")),
            "nickname": str(player.get("nickname") or "Player"),
            "emoji": str(player.get("emoji") or "🏈"),
            "confirmed": bool(lineup.get("confirmed_at")),
            "score": round(total, 1),
            "roster": roster,
            "starter_pick_ids": tuple(str(by_position[pos].get("pool_player_id")) for pos in POSITIONS if pos in by_position),
        })

    rows.sort(key=lambda row: (-float(row["score"]), str(row["nickname"]).casefold()))
    ranks = competition_ranks([float(row["score"]) for row in rows])
    for row, rank in zip(rows, ranks):
        row["rank"] = rank
        row["season_points_if_final"] = season_points_for_rank(rank)
    return rows


def build_storylines(bundle: dict[str, Any], leaderboard: list[dict[str, Any]]) -> dict[str, Any]:
    pool = {str(row["id"]): row for row in bundle.get("pool") or []}
    players_by_lineup = {str(row["lineup_id"]): row for row in leaderboard}
    picks = list(bundle.get("picks") or [])

    counts: Counter[str] = Counter()
    owner_for_pick: dict[str, list[str]] = defaultdict(list)
    signatures: dict[tuple[str, ...], list[str]] = defaultdict(list)
    picks_by_lineup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pick in picks:
        picks_by_lineup[str(pick.get("lineup_id"))].append(pick)
        pool_id = str(pick.get("pool_player_id"))
        counts[pool_id] += 1
        owner = players_by_lineup.get(str(pick.get("lineup_id")))
        if owner:
            owner_for_pick[pool_id].append(str(owner.get("nickname")))

    for lineup_id, lineup_picks in picks_by_lineup.items():
        owner = players_by_lineup.get(lineup_id)
        if not owner:
            continue
        by_pos = {str(p.get("position")): str(p.get("pool_player_id")) for p in lineup_picks}
        if len(by_pos) == len(POSITIONS):
            signatures[tuple(by_pos.get(pos, "") for pos in POSITIONS)].append(str(owner.get("nickname")))

    most_popular = None
    if counts:
        pool_id, count = sorted(counts.items(), key=lambda item: (-item[1], str((pool.get(item[0]) or {}).get("player_name") or "")))[0]
        row = pool.get(pool_id) or {}
        most_popular = {"player_name": row.get("player_name"), "count": count, "total": len(leaderboard)}

    alone = []
    for pool_id, count in sorted(counts.items(), key=lambda item: str((pool.get(item[0]) or {}).get("player_name") or "")):
        if count != 1:
            continue
        row = pool.get(pool_id) or {}
        owners = owner_for_pick.get(pool_id) or []
        if owners:
            alone.append({"nickname": owners[0], "player_name": row.get("player_name")})

    same_brain = []
    for names in signatures.values():
        if len(names) >= 2:
            same_brain.append(sorted(names, key=str.casefold))
    same_brain.sort(key=lambda names: (-len(names), [name.casefold() for name in names]))
    return {"most_popular": most_popular, "went_alone": alone, "same_brain": same_brain}


def build_weekly_recap(
    bundle: dict[str, Any],
    leaderboard: list[dict[str, Any]],
    season_results: list[dict[str, Any]] | None = None,
    *,
    current_week: int | None = None,
) -> dict[str, Any]:
    """Build the Monday recap from data the app already owns.

    No recap fields are persisted. That keeps v1.0.2 schema-free and makes the
    recap a presentation layer over the finalized current week.
    """
    story = build_storylines(bundle, leaderboard)
    pool = {str(row.get("id")): row for row in bundle.get("pool") or []}
    picks = list(bundle.get("picks") or [])
    players_by_lineup = {str(row.get("lineup_id")): row for row in leaderboard}

    champions = [row for row in leaderboard if int(row.get("rank") or 0) == 1]

    # Closest adjacent finish in the final standings. Ignore an all-zero pair so
    # two incomplete lineups do not become the featured "closest finish."
    closest = None
    for upper, lower in zip(leaderboard, leaderboard[1:]):
        upper_score = float(upper.get("score") or 0)
        lower_score = float(lower.get("score") or 0)
        if upper_score == 0 and lower_score == 0:
            continue
        gap = round(abs(upper_score - lower_score), 1)
        candidate = {
            "upper": str(upper.get("nickname") or "Player"),
            "lower": str(lower.get("nickname") or "Player"),
            "upper_score": upper_score,
            "lower_score": lower_score,
            "gap": gap,
            "tied": gap == 0,
        }
        if closest is None or gap < float(closest["gap"]):
            closest = candidate

    # "Boldest solo" = highest-scoring starter selected by exactly one lineup.
    pick_counts: Counter[str] = Counter(str(p.get("pool_player_id")) for p in picks if p.get("pool_player_id"))
    solo_candidates: list[dict[str, Any]] = []
    for pick in picks:
        pool_id = str(pick.get("pool_player_id") or "")
        if not pool_id or pick_counts.get(pool_id) != 1:
            continue
        owner = players_by_lineup.get(str(pick.get("lineup_id")))
        player_row = pool.get(pool_id)
        if not owner or not player_row:
            continue
        solo_candidates.append({
            "nickname": str(owner.get("nickname") or "Player"),
            "player_name": str(player_row.get("player_name") or "Player"),
            "points": round(_score(player_row), 1),
        })
    solo_candidates.sort(key=lambda row: (-float(row["points"]), str(row["player_name"]).casefold(), str(row["nickname"]).casefold()))
    boldest_solo = solo_candidates[0] if solo_candidates else None

    # Rank movement compares the standings entering this week with the standings
    # after this week. New entrants are not treated as having "moved" from an
    # invented prior rank.
    biggest_mover = None
    if season_results and current_week and int(current_week) > 1:
        previous_results = [r for r in season_results if int(r.get("nfl_week") or 0) < int(current_week)]
        through_current = [r for r in season_results if int(r.get("nfl_week") or 0) <= int(current_week)]
        before = {str(r.get("player_id")): r for r in build_season_standings(previous_results) if r.get("player_id")}
        after = {str(r.get("player_id")): r for r in build_season_standings(through_current) if r.get("player_id")}
        movers: list[dict[str, Any]] = []
        for player_id, old in before.items():
            new = after.get(player_id)
            if not new:
                continue
            places = int(old.get("rank") or 0) - int(new.get("rank") or 0)
            if places > 0:
                movers.append({
                    "nickname": str(new.get("nickname") or "Player"),
                    "places": places,
                    "from_rank": int(old.get("rank") or 0),
                    "to_rank": int(new.get("rank") or 0),
                })
        if movers:
            best = max(int(row["places"]) for row in movers)
            tied = [row for row in movers if int(row["places"]) == best]
            tied.sort(key=lambda row: str(row["nickname"]).casefold())
            biggest_mover = {"places": best, "movers": tied}

    return {
        "champions": champions,
        "most_popular": story.get("most_popular"),
        "boldest_solo": boldest_solo,
        "closest_finish": closest,
        "same_brain": (story.get("same_brain") or [None])[0],
        "biggest_mover": biggest_mover,
    }


def build_share_summary(
    week: dict[str, Any],
    recap: dict[str, Any],
    leaderboard: list[dict[str, Any]],
    season_standings: list[dict[str, Any]] | None = None,
) -> str:
    """Return a compact group-chat-friendly recap."""
    label = str(week.get("label") or f"Week {week.get('nfl_week', '')}").strip()
    lines = [f"🏈 Teal's Sunday Pick'em — {label} FINAL"]

    champions = list(recap.get("champions") or [])
    if champions:
        names = " + ".join(str(row.get("nickname") or "Champion") for row in champions)
        score = float(champions[0].get("score") or 0)
        lines.append(f"🏆 Champion{'s' if len(champions) > 1 else ''}: {names} — {score:.1f} pts")

    podium = leaderboard[:3]
    if podium:
        lines.append("Final: " + " • ".join(f"{int(row.get('rank') or 0)}. {row.get('nickname','Player')} {float(row.get('score') or 0):.1f}" for row in podium))

    popular = recap.get("most_popular")
    if popular and popular.get("player_name"):
        lines.append(f"🔥 Most popular: {popular['player_name']} ({int(popular.get('count') or 0)}/{int(popular.get('total') or 0)} lineups)")

    solo = recap.get("boldest_solo")
    if solo:
        lines.append(f"🦄 Boldest solo: {solo['nickname']} on {solo['player_name']} — {float(solo['points']):.1f} pts")

    closest = recap.get("closest_finish")
    if closest:
        if closest.get("tied"):
            lines.append(f"🤏 Closest finish: {closest['upper']} + {closest['lower']} tied at {float(closest['upper_score']):.1f}")
        else:
            lines.append(f"🤏 Closest finish: {closest['upper']} over {closest['lower']} by {float(closest['gap']):.1f}")

    same = recap.get("same_brain") or []
    if same:
        lines.append(f"👯 Same Brain: {' + '.join(str(name) for name in same)}")

    mover = recap.get("biggest_mover")
    if mover and mover.get("movers"):
        names = " + ".join(str(row.get("nickname") or "Player") for row in mover["movers"])
        lines.append(f"📈 Biggest mover: {names} (+{int(mover.get('places') or 0)} place{'s' if int(mover.get('places') or 0) != 1 else ''})")

    if season_standings:
        leader = season_standings[0]
        lines.append(f"⭐ Season leader: {leader.get('nickname','Player')} — {int(leader.get('season_points') or 0)} pts")
    return "\n".join(lines)


def build_season_standings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = {}
    for result in results:
        player_id = str(result.get("player_id") or f"snapshot:{result.get('nickname_snapshot')}")
        row = agg.setdefault(player_id, {
            "player_id": result.get("player_id"),
            "nickname": result.get("nickname_snapshot") or "Player",
            "emoji": result.get("emoji_snapshot") or "🏈",
            "season_points": 0,
            "total_fantasy_points": 0.0,
            "wins": 0,
            "seconds": 0,
            "thirds": 0,
            "weeks": 0,
        })
        row["season_points"] += int(result.get("season_points") or 0)
        row["total_fantasy_points"] += float(result.get("weekly_score") or 0)
        rank = int(result.get("finish_rank") or 0)
        row["wins"] += int(rank == 1)
        row["seconds"] += int(rank == 2)
        row["thirds"] += int(rank == 3)
        row["weeks"] += 1
        row["nickname"] = result.get("nickname_snapshot") or row["nickname"]
        row["emoji"] = result.get("emoji_snapshot") or row["emoji"]

    rows = list(agg.values())
    for row in rows:
        row["total_fantasy_points"] = round(float(row["total_fantasy_points"]), 1)
    rows.sort(key=lambda row: (-int(row["season_points"]), -float(row["total_fantasy_points"]), str(row["nickname"]).casefold()))
    ranks: list[int] = []
    previous: tuple[int, float] | None = None
    current_rank = 0
    for index, row in enumerate(rows, start=1):
        key = (int(row["season_points"]), float(row["total_fantasy_points"]))
        if previous is None or key != previous:
            current_rank = index
        ranks.append(current_rank)
        previous = key
    for row, rank in zip(rows, ranks):
        row["rank"] = rank
    return rows


def profile_stats(player_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    own = [r for r in results if str(r.get("player_id")) == str(player_id)]
    standings = build_season_standings(own)
    if standings:
        row = standings[0]
        return {
            "wins": int(row["wins"]),
            "seconds": int(row["seconds"]),
            "thirds": int(row["thirds"]),
            "season_points": int(row["season_points"]),
            "total_fantasy_points": float(row["total_fantasy_points"]),
        }
    return {"wins": 0, "seconds": 0, "thirds": 0, "season_points": 0, "total_fantasy_points": 0.0}


def add_zero_point_players(standings: list[dict[str, Any]], registered_players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {str(row.get("player_id")) for row in standings if row.get("player_id")}
    rows = [dict(row) for row in standings]
    for player in registered_players:
        if str(player.get("id")) in existing:
            continue
        rows.append({
            "player_id": str(player.get("id")),
            "nickname": player.get("nickname") or "Player",
            "emoji": player.get("emoji") or "🏈",
            "season_points": 0,
            "total_fantasy_points": 0.0,
            "wins": 0,
            "seconds": 0,
            "thirds": 0,
            "weeks": 0,
        })
    rows.sort(key=lambda row: (-int(row.get("season_points") or 0), -float(row.get("total_fantasy_points") or 0), str(row.get("nickname") or "").casefold()))
    previous = None
    current_rank = 0
    for index, row in enumerate(rows, start=1):
        key = (int(row.get("season_points") or 0), float(row.get("total_fantasy_points") or 0))
        if previous is None or key != previous:
            current_rank = index
        row["rank"] = current_rank
        previous = key
    return rows
