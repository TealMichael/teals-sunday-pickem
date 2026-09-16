"""Read-only, week-frozen NFL season-stat summaries for player picker cards.

The published pool and lineup tables are never written by this module. A single
shared app_meta snapshot covers *all* ranked players, including hidden reserves
that might be promoted after a late injury. Only the prior completed weeks are
eligible. A short Supabase lease prevents every phone from downloading nflverse.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import uuid4

from nfl_sources import NFLverseProvider, normalize_name, normalize_team

UTC = timezone.utc
STATS_SNAPSHOT_SCHEMA = 1
FAILURE_RETRY_MINUTES = 20
POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K"})


def _number(row: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value is None or str(value).strip().lower() in {"", "na", "nan", "none"}:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _has_numeric_column(row: Mapping[str, Any], *keys: str) -> bool:
    return any(str(row.get(k, "")).strip().lower() not in {"", "na", "nan", "none"}
               for k in keys if k in row)


def _previous_games(rows: list[dict[str, Any]], current_week: int) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    """Index strictly past REG weeks by position/team/name (no fuzzy IDs)."""
    results: dict[tuple[str, str, str], dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        try:
            week = int(float(row.get("week") or 0))
        except (TypeError, ValueError):
            continue
        if not 1 <= week < current_week:
            continue
        if str(row.get("season_type") or "REG").upper() not in {"REG", "REGULAR"}:
            continue
        pos = str(row.get("position") or "").upper()
        if pos not in POSITIONS:
            continue
        name = normalize_name(row.get("player_display_name") or row.get("player_name") or row.get("player_name_display"))
        team = normalize_team(row.get("team") or row.get("recent_team"))
        if not name or not team:
            continue
        # Provider's player-week rows should be unique. Do not count duplicates
        # or infer another game from a duplicate weekly feed record.
        results[(pos, team, name)][week] = row
    return {key: [week_rows[w] for w in sorted(week_rows)] for key, week_rows in results.items()}


def _history_for_player(index: dict[tuple[str, str, str], list[dict[str, Any]]],
                        pool_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    position = str(pool_row.get("position") or "").upper()
    team = normalize_team(pool_row.get("team_abbr"))
    name = normalize_name(pool_row.get("player_name"))
    if not name or position not in POSITIONS:
        return []
    direct = index.get((position, team, name))
    # A player might have changed teams during the season. Only merge across
    # teams when the provider's stable player_id agrees; otherwise preserve
    # exact team/name matches and never accidentally combine two players.
    matching = [r for (pos, _team, nm), rows in index.items() if pos == position and nm == name for r in rows]
    direct_ids = {str(r.get("player_id") or "") for r in (direct or [])}
    all_ids = {str(r.get("player_id") or "") for r in matching}
    if len(direct_ids) == 1 and next(iter(direct_ids)):
        wanted = next(iter(direct_ids))
        matching = [r for r in matching if str(r.get("player_id") or "") == wanted]
    elif direct:
        return direct
    elif len(all_ids) != 1 or not next(iter(all_ids)):
        return []
    unique_weeks = {int(float(r["week"])): r for r in matching}
    return [unique_weeks[w] for w in sorted(unique_weeks)]


def _player_summary(pool_row: Mapping[str, Any], history: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not history:
        return None
    pos = str(pool_row.get("position") or "").upper()
    gp = len(history)
    if pos == "K":
        # nflverse 2025+ stats_player weekly includes kicking fields. If its
        # schema changes, do not display a fabricated 0-for-0 kicker season.
        kicking = [r for r in history if _has_numeric_column(r, "fg_made", "field_goals_made", "fg_att", "pat_made", "extra_points_made")]
        if not kicking:
            return None
        made = sum(_number(r, "fg_made", "field_goals_made") for r in kicking)
        attempted = sum(_number(r, "fg_att", "field_goals_attempted") for r in kicking)
        xp = sum(_number(r, "pat_made", "extra_points_made", "xp_made") for r in kicking)
        return {"gp": len(kicking), "fg_made": round(made), "xp_made": round(xp),
                "fg_pct": round(made * 100.0 / attempted, 1) if attempted > 0 else None}

    passing = sum(_number(r, "passing_yards", "pass_yds") for r in history)
    passing_tds = sum(_number(r, "passing_tds", "pass_td") for r in history)
    rushing = sum(_number(r, "rushing_yards", "rush_yds") for r in history)
    receiving = sum(_number(r, "receiving_yards", "rec_yds") for r in history)
    receptions = sum(_number(r, "receptions", "rec") for r in history)
    total_tds = sum(
        _number(r, "rushing_tds", "rush_td") + _number(r, "receiving_tds", "rec_td")
        + _number(r, "special_teams_tds", "return_tds", "return_td")
        for r in history
    )
    if pos == "QB":
        return {"gp": gp, "passing_yards_pg": round(passing / gp, 1),
                "passing_tds": round(passing_tds), "rushing_yards_pg": round(rushing / gp, 1)}
    if pos == "RB":
        return {"gp": gp, "rushing_yards_pg": round(rushing / gp, 1),
                "receiving_yards_pg": round(receiving / gp, 1), "total_tds": round(total_tds)}
    if pos in {"WR", "TE"}:
        return {"gp": gp, "receiving_yards_pg": round(receiving / gp, 1),
                "receptions_pg": round(receptions / gp, 1), "total_tds": round(total_tds)}
    return None


def build_snapshot(week: Mapping[str, Any], pool: list[dict[str, Any]],
                   stat_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure snapshot builder: no mutation of supplied pool, picks, or ranking."""
    current_week = int(week["nfl_week"])
    index = _previous_games(stat_rows, current_week)
    result: dict[str, dict[str, Any]] = {}
    for row in pool:
        pool_id = str(row.get("id") or "")
        if not pool_id:
            continue
        summary = _player_summary(row, _history_for_player(index, row))
        if summary is not None:
            result[pool_id] = summary
    return {"schema": STATS_SNAPSHOT_SCHEMA, "season": int(week["season"]),
            "nfl_week": current_week, "through_week": current_week - 1,
            "players": result}


def snapshot_key(week: Mapping[str, Any]) -> str:
    return f"season_card_stats:{int(week['season'])}:{int(week['nfl_week'])}:v{STATS_SNAPSHOT_SCHEMA}"


def load_or_prepare_snapshot(store, week: dict[str, Any], *, provider=None) -> dict[str, Any] | None:
    """One shared, frozen per-week snapshot; failures never block lineup picks.

    Can be called by a player opening the picker *after* this week's pool was
    published. Uses a cross-session lease and shared retry marker; no write to
    player_pool, lineup_picks, or weekly scores is possible from this module.
    """
    if not week.get("published_at") or week.get("is_demo") or int(week.get("nfl_week") or 0) <= 1:
        return None
    key = snapshot_key(week)
    try:
        existing = store.get_app_meta(key)
        value = (existing or {}).get("value") or {}
        if (value.get("schema") == STATS_SNAPSHOT_SCHEMA
                and int(value.get("through_week") or 0) == int(week["nfl_week"]) - 1
                and isinstance(value.get("players"), dict)):
            return value
        until = value.get("retry_after")
        if until and datetime.fromisoformat(str(until).replace("Z", "+00:00")) > datetime.now(UTC):
            return None
    except Exception:
        # No app_meta access must ever prevent someone from making picks.
        return None

    owner = str(uuid4())
    lease = f"season-card-stats:{int(week['season'])}:{int(week['nfl_week'])}"
    try:
        if not store.claim_refresh_lease(lease, owner=owner, ttl_seconds=150):
            return None
    except Exception:
        return None
    try:
        # Check again after lease; another session may just have completed it.
        existing = store.get_app_meta(key)
        value = (existing or {}).get("value") or {}
        if value.get("schema") == STATS_SNAPSHOT_SCHEMA and isinstance(value.get("players"), dict):
            return value
        pool = store.get_full_week_pool(str(week["id"]))
        if not pool:
            return None
        data = (provider or NFLverseProvider()).weekly_player_stats(int(week["season"]))
        snapshot = build_snapshot(week, pool, data)
        # If provider returns no prior-week stats at all, do not freeze an
        # apparently valid but empty snapshot for the entire week.
        if not snapshot["players"]:
            raise RuntimeError("No verified prior-week player stats available")
        store.set_app_meta(key, snapshot)
        return snapshot
    except Exception:
        try:
            store.set_app_meta(key, {"retry_after": (datetime.now(UTC) + timedelta(minutes=FAILURE_RETRY_MINUTES)).isoformat()})
        except Exception:
            pass
        return None
    finally:
        store.release_refresh_lease(lease, owner=owner)


def stats_line(row: Mapping[str, Any]) -> str:
    """Short text for *inside* the existing full-card native button."""
    stats = row.get("_season_stats")
    if not isinstance(stats, dict):
        return "Season stats pending"
    pos = str(row.get("position") or "").upper()
    gp = int(stats.get("gp") or 0)
    if not gp:
        return "Season stats pending"
    if pos == "QB":
        return (f"{stats['passing_yards_pg']:.1f} pass yds/g · {stats['passing_tds']} pass TD · "
                f"{stats['rushing_yards_pg']:.1f} rush yds/g · {gp} GP")
    if pos == "RB":
        return (f"{stats['rushing_yards_pg']:.1f} rush yds/g · {stats['receiving_yards_pg']:.1f} rec yds/g · "
                f"{stats['total_tds']} TD · {gp} GP")
    if pos in {"WR", "TE"}:
        return (f"{stats['receiving_yards_pg']:.1f} rec yds/g · {stats['receptions_pg']:.1f} catches/g · "
                f"{stats['total_tds']} TD · {gp} GP")
    if pos == "K":
        pct = "—" if stats.get("fg_pct") is None else f"{stats['fg_pct']:.1f}%"
        return f"{stats['fg_made']} FG · {stats['xp_made']} XP · FG {pct} · {gp} GP"
    return "Season stats pending"


def attach_snapshot(pool: list[dict[str, Any]], snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Copy rows: never mutate a shared Store pool cache or its saved picks."""
    stats = (snapshot or {}).get("players") or {}
    return [{**row, "_season_stats": stats.get(str(row.get("id")))} for row in pool]
