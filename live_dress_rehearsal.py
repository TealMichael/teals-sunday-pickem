from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from nfl_scoring import display_score, score_stat_line
from nfl_sources import ESPNProvider, NFLverseProvider, normalize_name, normalize_team, parse_iso
from weekly import ET, POSITIONS

UTC = timezone.utc


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _game_label(game: dict[str, Any]) -> str:
    kickoff = parse_iso(game.get("kickoff_at"))
    if kickoff:
        when = kickoff.astimezone(ET).strftime("%a %-I:%M %p ET")
    else:
        when = "time TBD"
    away = normalize_team(game.get("away_team")) or "AWAY"
    home = normalize_team(game.get("home_team")) or "HOME"
    return f"{away} @ {home} — {when}"


def discover_rehearsal_games(
    *,
    season: int,
    nfl_week: int,
    nflverse: NFLverseProvider | None = None,
) -> list[dict[str, Any]]:
    """Read the real regular-season schedule for a Commissioner-only test.

    This function deliberately does not receive a store. It cannot write to the
    Pick'em database or mutate the public Week 1 experience.
    """
    provider = nflverse or NFLverseProvider()
    games = provider.schedule_games(int(season), int(nfl_week), game_type="REG")
    games = sorted(games, key=lambda row: str(row.get("kickoff_at") or ""))
    return [dict(row, label=_game_label(row)) for row in games]


def _summary_game_state(payload: dict[str, Any]) -> dict[str, Any]:
    header = payload.get("header") or {}
    competition = (header.get("competitions") or [{}])[0]
    status = competition.get("status") or header.get("status") or {}
    type_info = status.get("type") or {}
    state = str(type_info.get("state") or "pre").lower()
    completed = bool(type_info.get("completed"))
    if completed or state == "post":
        game_status = "FINAL"
    elif state == "in":
        game_status = "LIVE"
    else:
        game_status = "SCHEDULED"

    home_score = None
    away_score = None
    home_team = None
    away_team = None
    for competitor in competition.get("competitors") or []:
        side = str(competitor.get("homeAway") or "").lower()
        team = normalize_team((competitor.get("team") or {}).get("abbreviation"))
        try:
            score = int(float(competitor.get("score"))) if competitor.get("score") not in (None, "") else None
        except (TypeError, ValueError):
            score = None
        if side == "home":
            home_team, home_score = team, score
        elif side == "away":
            away_team, away_score = team, score

    return {
        "game_status": game_status,
        "period": status.get("period"),
        "clock": status.get("displayClock"),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
    }


def _format_formula(breakdown: dict[str, dict[str, Any]], total: float) -> tuple[str, str]:
    if not breakdown:
        return "No fantasy-scoring stats yet.", f"0.0 = {display_score(total)} pts"

    stat_parts: list[str] = []
    point_parts: list[str] = []
    for component in breakdown.values():
        stat = component.get("stat")
        label = str(component.get("label") or "stat")
        points = float(component.get("points") or 0.0)
        try:
            stat_num = float(stat)
            stat_text = str(int(stat_num)) if stat_num.is_integer() else f"{stat_num:g}"
        except (TypeError, ValueError):
            stat_text = str(stat)
        stat_parts.append(f"{stat_text} {label}")
        if not point_parts:
            point_parts.append(f"{points:.1f}")
        else:
            point_parts.append(("+ " if points >= 0 else "− ") + f"{abs(points):.1f}")

    return " + ".join(stat_parts), " ".join(point_parts) + f" = {display_score(total)} pts"


def run_live_game_rehearsal(
    store,
    *,
    season: int,
    nfl_week: int,
    provider_event_id: str,
    nflverse: NFLverseProvider | None = None,
    espn: ESPNProvider | None = None,
) -> dict[str, Any]:
    """Read one real game through the production parser/scorer without writes.

    The test intentionally mirrors the live scoring chain's critical read path:
    nflverse schedule -> ESPN CDN summary -> ESPN player parser -> team/name
    matching against cached Sleeper identities -> production scoring formula.

    It never calls a store mutator and never writes scores, lineups, standings,
    schedule rows, data-state timestamps, or Commissioner actions.
    """
    event_id = str(provider_event_id or "").strip()
    if not event_id:
        raise ValueError("Choose a game before running the live test.")

    nflverse = nflverse or NFLverseProvider()
    espn = espn or ESPNProvider()
    games = discover_rehearsal_games(season=season, nfl_week=nfl_week, nflverse=nflverse)
    game = next((row for row in games if str(row.get("provider_event_id")) == event_id), None)
    if not game:
        raise ValueError("That game was not found in the current NFL week schedule.")

    summary = espn.summary(event_id)
    parsed = espn.player_stats(summary)
    espn_state = _summary_game_state(summary)

    cached_players = store.get_nfl_players()
    cached_index: dict[tuple[str, str], dict[str, Any]] = {}
    cached_by_name: dict[str, list[dict[str, Any]]] = {}
    cached_by_team: dict[str, list[dict[str, Any]]] = {}
    for row in cached_players:
        team = normalize_team(row.get("team_abbr"))
        key = str(row.get("canonical_key") or normalize_name(row.get("full_name")))
        if team and key:
            cached_index[(team, key)] = row
            cached_by_team.setdefault(team, []).append(row)
        if key:
            cached_by_name.setdefault(key, []).append(row)

    def _broad_role(raw_stats: dict[str, Any]) -> str:
        keys = set(raw_stats)
        if keys & {"field_goals_made", "fg_made", "extra_points_made", "xp_made", "pat_made"}:
            return "K"
        if keys & {"passing_yards", "pass_yds", "passing_tds", "pass_td", "interceptions", "passing_interceptions"}:
            return "QB"
        if keys & {"receptions", "rec", "receiving_yards", "rec_yds", "receiving_tds", "rec_td"}:
            return "REC"
        if keys & {"rushing_yards", "rush_yds", "rushing_tds", "rush_td"}:
            return "RUSH"
        return "?"

    # Score every ESPN row that contains a Pick'em-relevant stat.  Do not use
    # ESPN/Sleeper position resolution as a gate: ESPN's live CDN often omits
    # athlete.position, especially outside rushing tables.  Production Sunday
    # scoring already knows each selected player's position from player_pool and
    # matches ESPN by normalized team + name.  The dress rehearsal should expose
    # passing/receiving/kicking data even when the arbitrary Wednesday player's
    # position cannot be resolved from the cached roster.
    rows: list[dict[str, Any]] = []
    for entry in parsed:
        team = normalize_team(entry.get("team_abbr"))
        name = str(entry.get("player_name") or "").strip()
        key = normalize_name(name)
        raw_stats = dict(entry.get("stats") or {})
        generic_scored = score_stat_line(raw_stats)
        if not generic_scored.breakdown:
            continue

        exact_match = cached_index.get((team, key))
        name_matches = cached_by_name.get(key) or []
        name_only_match = name_matches[0] if not exact_match and len(name_matches) == 1 else None
        position_source = exact_match or name_only_match or {}
        position = str(position_source.get("position") or entry.get("position") or "").upper()
        if position == "PK":
            position = "K"
        if position not in POSITIONS:
            position = _broad_role(raw_stats)

        scored = score_stat_line(raw_stats, position if position in POSITIONS else None)
        stat_formula, points_formula = _format_formula(scored.breakdown, scored.points)
        rows.append({
            "key": f"{team}:{key}",
            "team_abbr": team,
            "player_name": name,
            "position": position,
            "espn_position": str(entry.get("position") or "").upper() or None,
            "espn_player_id": entry.get("espn_player_id"),
            "matched_cached_player": bool(exact_match),
            "cached_player_name": (exact_match or name_only_match or {}).get("full_name"),
            "identity_resolution": (
                "exact team+name" if exact_match
                else "name-only position hint" if name_only_match
                else "ESPN/inferred role"
            ),
            "raw_stats": raw_stats,
            "points": scored.points,
            "display_points": display_score(scored.points),
            "breakdown": scored.breakdown,
            "stat_formula": stat_formula,
            "points_formula": points_formula,
        })

    def _candidate_summary(candidate: dict[str, Any], similarity: float) -> dict[str, Any]:
        return {
            "full_name": candidate.get("full_name"),
            "team_abbr": normalize_team(candidate.get("team_abbr")),
            "position": candidate.get("position"),
            "sleeper_player_id": candidate.get("sleeper_player_id"),
            "last_synced_at": candidate.get("last_synced_at"),
            "similarity": round(float(similarity), 3),
        }

    # Explain exact production-key misses without changing production matching.
    # This is intentionally diagnostic-only: it helps us distinguish stale team
    # assignments, name variants, and players absent from the cached Sleeper roster.
    unmatched_diagnostics: list[dict[str, Any]] = []
    for row in rows:
        if row.get("matched_cached_player"):
            continue
        team = normalize_team(row.get("team_abbr"))
        key = normalize_name(row.get("player_name"))
        exact_name_elsewhere = list(cached_by_name.get(key) or [])

        candidates: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for candidate in exact_name_elsewhere:
            cid = str(candidate.get("sleeper_player_id") or f"{candidate.get('team_abbr')}:{candidate.get('full_name')}")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            candidates.append(_candidate_summary(candidate, 1.0))

        fuzzy_same_team: list[tuple[float, dict[str, Any]]] = []
        for candidate in cached_by_team.get(team, []):
            candidate_key = str(candidate.get("canonical_key") or normalize_name(candidate.get("full_name")))
            if not candidate_key or candidate_key == key:
                continue
            similarity = SequenceMatcher(None, key, candidate_key).ratio()
            if similarity >= 0.58:
                fuzzy_same_team.append((similarity, candidate))
        fuzzy_same_team.sort(key=lambda item: item[0], reverse=True)
        for similarity, candidate in fuzzy_same_team[:3]:
            cid = str(candidate.get("sleeper_player_id") or f"{candidate.get('team_abbr')}:{candidate.get('full_name')}")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            candidates.append(_candidate_summary(candidate, similarity))

        if not team:
            reason = "ESPN row has no team abbreviation."
        elif exact_name_elsewhere:
            candidate_teams = sorted({normalize_team(c.get("team_abbr")) or "—" for c in exact_name_elsewhere})
            reason = "Same normalized name exists in cache, but under team " + ", ".join(candidate_teams) + "."
        elif fuzzy_same_team and fuzzy_same_team[0][0] >= 0.82:
            top = fuzzy_same_team[0][1]
            reason = f"Likely name variation on {team}: {top.get('full_name')}."
        else:
            reason = "No exact cached Sleeper player for this team+name key."

        top_candidate = candidates[0] if candidates else None
        unmatched_diagnostics.append({
            "player_name": row.get("player_name"),
            "team_abbr": team,
            "position": row.get("position"),
            "espn_position": row.get("espn_position"),
            "espn_player_id": row.get("espn_player_id"),
            "stat_formula": row.get("stat_formula"),
            "reason": reason,
            "candidate_count": len(candidates),
            "top_candidate": top_candidate,
            "candidates": candidates,
        })

    cache_sync_values = [str(row.get("last_synced_at")) for row in cached_players if row.get("last_synced_at")]
    cache_latest_synced_at = max(cache_sync_values) if cache_sync_values else None

    # Prefer a player with actual live stats for each position. Before kickoff,
    # fall back to the first parsed player so the parser/matching path can still
    # be inspected without pretending live scoring has begun.
    samples: dict[str, dict[str, Any]] = {}
    for position in POSITIONS:
        candidates = [row for row in rows if row["position"] == position]
        if not candidates:
            continue
        nonzero = [row for row in candidates if row.get("breakdown")]
        chosen = max(nonzero or candidates, key=lambda row: float(row.get("points") or 0.0))
        samples[position] = chosen

    matched = sum(1 for row in rows if row.get("matched_cached_player"))
    active_stat_rows = len(rows)

    category_samples: dict[str, dict[str, Any]] = {}
    category_keys = {
        "Passing": {"passing_yards", "passing_tds", "interceptions"},
        "Rushing": {"rushing_yards", "rushing_tds"},
        "Receiving": {"receptions", "receiving_yards", "receiving_tds"},
        "Kicking": {"field_goals_made", "extra_points_made"},
    }
    for label, component_keys in category_keys.items():
        candidates = [row for row in rows if component_keys & set((row.get("breakdown") or {}).keys())]
        if candidates:
            category_samples[label] = max(candidates, key=lambda row: float(row.get("points") or 0.0))

    return {
        "fetched_at": _iso_now(),
        "season": int(season),
        "nfl_week": int(nfl_week),
        "provider_event_id": event_id,
        "matchup": _game_label(game),
        "schedule_status": str(game.get("game_status") or "SCHEDULED"),
        "espn_status": espn_state.get("game_status") or "SCHEDULED",
        "period": espn_state.get("period"),
        "clock": espn_state.get("clock"),
        "home_team": espn_state.get("home_team") or game.get("home_team"),
        "away_team": espn_state.get("away_team") or game.get("away_team"),
        "home_score": espn_state.get("home_score"),
        "away_score": espn_state.get("away_score"),
        "parsed_rows": len(parsed),
        "fantasy_rows": len(rows),
        "active_stat_rows": active_stat_rows,
        "matched_rows": matched,
        "match_rate": (matched / len(rows)) if rows else 0.0,
        "samples": samples,
        "category_samples": category_samples,
        "rows": rows,
        "unmatched_diagnostics": unmatched_diagnostics,
        "cached_player_count": len(cached_players),
        "cache_latest_synced_at": cache_latest_synced_at,
        "read_only": True,
    }


def compare_rehearsal_snapshots(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"changed_players": 0, "score_changes": [], "status_changed": False}
    before = {str(row.get("key")): row for row in previous.get("rows") or []}
    changes: list[dict[str, Any]] = []
    for row in current.get("rows") or []:
        old = before.get(str(row.get("key")))
        if not old:
            continue
        old_points = float(old.get("points") or 0.0)
        new_points = float(row.get("points") or 0.0)
        if old_points != new_points or (old.get("raw_stats") or {}) != (row.get("raw_stats") or {}):
            changes.append({
                "player_name": row.get("player_name"),
                "position": row.get("position"),
                "team_abbr": row.get("team_abbr"),
                "before": old_points,
                "after": new_points,
                "delta": round(new_points - old_points, 3),
            })
    return {
        "changed_players": len(changes),
        "score_changes": changes,
        "status_changed": str(previous.get("espn_status")) != str(current.get("espn_status")),
    }
