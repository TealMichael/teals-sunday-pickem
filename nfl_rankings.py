from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from nfl_scoring import score_stat_line
from nfl_sources import normalize_name, normalize_team
from weekly import POSITIONS

# Week 1 is intentionally a one-time consensus seed rather than a permanent
# fantasy-site scraping dependency. Candidates were assembled from current
# public Week 1 rankings/projections immediately before the 2026 opener, then
# filtered to this game's Sunday 1:00 PM ET-or-later eligibility rule.
WEEK1_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "QB": [
        ("Jalen Hurts", "PHI"),
        ("Lamar Jackson", "BAL"),
        ("Josh Allen", "BUF"),
        ("Joe Burrow", "CIN"),
        ("Justin Herbert", "LAC"),
        ("Jaxson Dart", "NYG"),
        ("Dak Prescott", "DAL"),
        ("Caleb Williams", "CHI"),
        ("Jayden Daniels", "WAS"),
        ("Trevor Lawrence", "JAX"),
        ("Baker Mayfield", "TB"),
        ("C.J. Stroud", "HOU"),
        ("Jordan Love", "GB"),
        ("Bryce Young", "CAR"),
    ],
    "RB": [
        ("Jahmyr Gibbs", "DET"),
        ("Bijan Robinson", "ATL"),
        ("Jonathan Taylor", "IND"),
        ("De'Von Achane", "MIA"),
        ("Derrick Henry", "BAL"),
        ("Omarion Hampton", "LAC"),
        ("Saquon Barkley", "PHI"),
        ("James Cook", "BUF"),
        ("Chase Brown", "CIN"),
        ("Ashton Jeanty", "LV"),
        ("Breece Hall", "NYJ"),
        ("Bucky Irving", "TB"),
    ],
    "WR": [
        ("Ja'Marr Chase", "CIN"),
        ("Amon-Ra St. Brown", "DET"),
        ("CeeDee Lamb", "DAL"),
        ("Justin Jefferson", "MIN"),
        ("Chris Olave", "NO"),
        ("Zay Flowers", "BAL"),
        ("Nico Collins", "HOU"),
        ("Drake London", "ATL"),
        ("George Pickens", "DAL"),
        ("DeVonta Smith", "PHI"),
        ("Terry McLaurin", "WAS"),
        ("DJ Moore", "CHI"),
    ],
    "TE": [
        ("Brock Bowers", "LV"),
        ("Trey McBride", "ARI"),
        ("Tyler Warren", "IND"),
        ("Colston Loveland", "CHI"),
        ("Sam LaPorta", "DET"),
        ("Harold Fannin Jr.", "CLE"),
        ("Kyle Pitts", "ATL"),
        ("Mark Andrews", "BAL"),
        ("Dallas Goedert", "PHI"),
        ("Tucker Kraft", "GB"),
        ("Jake Ferguson", "DAL"),
        ("Dalton Kincaid", "BUF"),
    ],
}

# Kicker selection follows Michael's rule: choose the primary kicker from the
# strongest expected offenses, not the top fantasy-kicker projection itself.
WEEK1_KICKER_TEAM_ORDER = ["LAC", "DET", "CIN", "BAL", "DAL", "CHI", "PHI", "MIN", "TB", "BUF", "HOU", "JAX"]


def _eligible_team_schedule(games: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for game in games:
        if not bool(game.get("is_eligible")):
            continue
        home = normalize_team(game.get("home_team"))
        away = normalize_team(game.get("away_team"))
        if home:
            result[home] = {"opponent": away, "kickoff_at": game.get("kickoff_at")}
        if away:
            result[away] = {"opponent": home, "kickoff_at": game.get("kickoff_at")}
    return result


def _player_index(players: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for p in players:
        key = (normalize_team(p.get("team_abbr")), normalize_name(p.get("full_name")))
        index[key] = p
    return index


def _resolve_named_candidate(name: str, team: str, players: list[dict[str, Any]]) -> dict[str, Any] | None:
    team = normalize_team(team)
    wanted = normalize_name(name)
    index = _player_index(players)
    exact = index.get((team, wanted))
    if exact:
        return exact
    # Conservative fallback for suffix/punctuation differences: require same
    # team and a strong normalized-name containment relationship.
    for p in players:
        if normalize_team(p.get("team_abbr")) != team:
            continue
        got = normalize_name(p.get("full_name"))
        if wanted and got and (wanted in got or got in wanted):
            return p
    return None


def _kicker_for_team(team: str, kickers: list[dict[str, Any]]) -> dict[str, Any] | None:
    options = [p for p in kickers if normalize_team(p.get("team_abbr")) == normalize_team(team) and p.get("active") is not False]
    if not options:
        return None
    # Sleeper depth_chart_order is useful when present. Unknown order goes last.
    options.sort(key=lambda p: (int(p.get("depth_order") or 999), normalize_name(p.get("full_name"))))
    return options[0]



def week1_kicker_team_order(games: list[dict[str, Any]]) -> list[str]:
    """Rank eligible Week 1 offenses by current implied team total.

    If ESPN's current odds are missing for some games, append the build-time
    consensus offense order as a deterministic fallback.
    """
    implied: list[tuple[float, str]] = []
    for game in games:
        if not game.get("is_eligible"):
            continue
        total = game.get("over_under")
        spread = game.get("spread")
        favorite = normalize_team(game.get("favored_team"))
        home = normalize_team(game.get("home_team"))
        away = normalize_team(game.get("away_team"))
        try:
            total_f = float(total)
            spread_f = abs(float(spread or 0))
        except (TypeError, ValueError):
            continue
        if not favorite or favorite not in {home, away}:
            # With no favorite marker, a tied projection gives both teams the
            # same implied total; deterministic fallback order breaks ties.
            implied.extend([(total_f / 2.0, home), (total_f / 2.0, away)])
            continue
        dog = away if favorite == home else home
        implied.append((total_f / 2.0 + spread_f / 2.0, favorite))
        implied.append((total_f / 2.0 - spread_f / 2.0, dog))
    implied.sort(key=lambda pair: pair[0], reverse=True)
    ordered: list[str] = []
    for _, team in implied:
        if team and team not in ordered:
            ordered.append(team)
    for team in WEEK1_KICKER_TEAM_ORDER:
        if team not in ordered:
            ordered.append(team)
    return ordered

def week1_rankings(players_by_position: dict[str, list[dict[str, Any]]], games: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    schedule = _eligible_team_schedule(games)
    ranked: dict[str, list[dict[str, Any]]] = {}

    for position in ("QB", "RB", "WR", "TE"):
        rows: list[dict[str, Any]] = []
        for name, team in WEEK1_CANDIDATES[position]:
            if team not in schedule:
                continue
            player = _resolve_named_candidate(name, team, players_by_position.get(position, []))
            if not player:
                continue
            rows.append(_pool_row(position, player, schedule[team], len(rows) + 1))
            if len(rows) == 10:
                break
        if len(rows) < 10:
            raise RuntimeError(f"Week 1 {position} ranking resolved only {len(rows)} of 10 players.")
        ranked[position] = rows

    kickers: list[dict[str, Any]] = []
    for team in week1_kicker_team_order(games):
        if team not in schedule:
            continue
        kicker = _kicker_for_team(team, players_by_position.get("K", []))
        if not kicker:
            continue
        kickers.append(_pool_row("K", kicker, schedule[team], len(kickers) + 1))
        if len(kickers) == 10:
            break
    if len(kickers) < 10:
        raise RuntimeError(f"Week 1 K ranking resolved only {len(kickers)} of 10 kickers.")
    ranked["K"] = kickers
    return ranked


def _pool_row(position: str, player: dict[str, Any], schedule: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "position": position,
        "slot_rank": rank,
        "player_name": player.get("full_name"),
        "nfl_player_id": player.get("sleeper_player_id"),
        "sleeper_player_id": player.get("sleeper_player_id"),
        "team_abbr": normalize_team(player.get("team_abbr")),
        "opponent_abbr": normalize_team(schedule.get("opponent")),
        "kickoff_at": schedule.get("kickoff_at"),
        "is_visible": rank <= 5,
        "availability_status": player.get("availability_status") or "HEALTHY",
        "raw_injury_status": player.get("injury_status"),
        "schedule_eligible": True,
        "schedule_note": None,
    }


def nflverse_rankings(
    *,
    current_week: int,
    players_by_position: dict[str, list[dict[str, Any]]],
    games: list[dict[str, Any]],
    stat_rows: list[dict[str, Any]],
    kicker_team_order: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Rank Week 2+ without matchup-strength inputs.

    Formula: 55% season Pick'em PPG + 30% last-three PPG + 15% workload.
    The current opponent never enters the ranking score; it is displayed only.
    """
    schedule = _eligible_team_schedule(games)
    rows_by_player: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in stat_rows:
        week = _to_int(row.get("week"))
        if week <= 0 or week >= current_week:
            continue
        position = str(row.get("position") or "").upper()
        if position not in {"QB", "RB", "WR", "TE"}:
            continue
        team = normalize_team(row.get("team") or row.get("recent_team"))
        name = row.get("player_display_name") or row.get("player_name") or row.get("player_name_display") or ""
        if not name or not team:
            continue
        rows_by_player[(position, team, normalize_name(name))].append(row)

    result: dict[str, list[dict[str, Any]]] = {}
    for position in ("QB", "RB", "WR", "TE"):
        candidates: list[tuple[float, dict[str, Any]]] = []
        for sleeper in players_by_position.get(position, []):
            team = normalize_team(sleeper.get("team_abbr"))
            if team not in schedule:
                continue
            key = (position, team, normalize_name(sleeper.get("full_name")))
            history = rows_by_player.get(key, [])
            if not history:
                continue
            history.sort(key=lambda r: _to_int(r.get("week")))
            scored = [score_stat_line(row, position).points for row in history]
            season_ppg = mean(scored)
            last3 = mean(scored[-3:])
            workload_values = [_workload(position, row) for row in history]
            workload = mean(workload_values[-3:]) if workload_values else 0.0
            ranking_score = 0.55 * season_ppg + 0.30 * last3 + 0.15 * workload
            candidates.append((ranking_score, sleeper))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        top = candidates[:10]
        if len(top) < 10:
            raise RuntimeError(f"Week {current_week} {position} ranking resolved only {len(top)} of 10 players.")
        result[position] = [_pool_row(position, player, schedule[normalize_team(player.get("team_abbr"))], rank) for rank, (_, player) in enumerate(top, 1)]

    teams = [normalize_team(x) for x in (kicker_team_order or []) if normalize_team(x) in schedule]
    if len(teams) < 10:
        # Safe fallback: eligible-team alphabetical order is only used if the
        # team-offense scorer couldn't resolve enough teams. The publish step
        # refuses incomplete pools, so this cannot silently publish <10.
        teams.extend(t for t in sorted(schedule) if t not in teams)
    kicker_rows: list[dict[str, Any]] = []
    for team in teams:
        kicker = _kicker_for_team(team, players_by_position.get("K", []))
        if not kicker:
            continue
        kicker_rows.append(_pool_row("K", kicker, schedule[team], len(kicker_rows) + 1))
        if len(kicker_rows) == 10:
            break
    if len(kicker_rows) < 10:
        raise RuntimeError(f"Week {current_week} K ranking resolved only {len(kicker_rows)} of 10 kickers.")
    result["K"] = kicker_rows
    return result


def _workload(position: str, row: dict[str, Any]) -> float:
    if position == "QB":
        return (_to_float(row.get("attempts")) + _to_float(row.get("carries")) * 2.0) / 3.0
    if position == "RB":
        return (_to_float(row.get("carries")) + _to_float(row.get("targets"))) * 0.75
    return (_to_float(row.get("targets")) + _to_float(row.get("receptions"))) * 0.85


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
