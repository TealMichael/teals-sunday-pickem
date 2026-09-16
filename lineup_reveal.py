"""Read-only, post-lock group lineup reveal built from the existing public bundle.

Never inspect or expose emergency backup IDs: the reveal describes the five
starters people locked in, not later injury-substitution decisions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from weekly import POSITIONS

LINEUP_REVEAL_SCHEMA_VERSION = 1


def build_lineup_reveal(bundle: dict[str, Any]) -> dict[str, Any]:
    """Count saved starters, unique picks, and complete identical lineups.

    Pure presentation logic: does not mutate inputs or write to the store.
    Orphan picks and empty lineups do not count toward participation.
    """
    pool = {str(r.get("id")): r for r in bundle.get("pool") or [] if r.get("id")}
    players = {str(r.get("id")): r for r in bundle.get("players") or [] if r.get("id")}
    lineups = {str(r.get("id")): r for r in bundle.get("lineups") or [] if r.get("id")}
    picks_by_lineup: dict[str, dict[str, str]] = defaultdict(dict)
    for pick in bundle.get("picks") or []:
        lid = str(pick.get("lineup_id") or "")
        pos = str(pick.get("position") or "")
        starter_id = str(pick.get("pool_player_id") or "")
        if lid in lineups and pos in POSITIONS and starter_id:
            picks_by_lineup[lid][pos] = starter_id

    active_lineups = {lid: positions for lid, positions in picks_by_lineup.items() if positions}
    counts_by_position: dict[str, Counter[str]] = {pos: Counter() for pos in POSITIONS}
    owners: dict[tuple[str, str], list[str]] = defaultdict(list)
    matching: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for lid, by_pos in active_lineups.items():
        player = players.get(str(lineups[lid].get("player_id"))) or {}
        name = str(player.get("nickname") or "Player")
        for pos, starter_id in by_pos.items():
            counts_by_position[pos][starter_id] += 1
            owners[(pos, starter_id)].append(name)
        if all(pos in by_pos for pos in POSITIONS):
            matching[tuple(by_pos[pos] for pos in POSITIONS)].append(name)

    positions = []
    solos = []
    for pos in POSITIONS:
        pos_rows = []
        for starter_id, count in counts_by_position[pos].items():
            player_name = str((pool.get(starter_id) or {}).get("player_name") or "Player unavailable")
            names = sorted(owners[(pos, starter_id)], key=str.casefold)
            item = {"player_name": player_name, "count": count, "owners": names}
            pos_rows.append(item)
            if count == 1:
                solos.append({"position": pos, "player_name": player_name, "nickname": names[0]})
        pos_rows.sort(key=lambda r: (-r["count"], r["player_name"].casefold()))
        positions.append({"position": pos, "picks_count": sum(counts_by_position[pos].values()), "choices": pos_rows})

    identical = [sorted(names, key=str.casefold) for names in matching.values() if len(names) > 1]
    identical.sort(key=lambda names: (-len(names), [n.casefold() for n in names]))
    solos.sort(key=lambda row: (POSITIONS.index(row["position"]), row["player_name"].casefold()))
    most_popular = sorted(
        ({"position": pos["position"], **choice} for pos in positions for choice in pos["choices"]),
        key=lambda row: (-row["count"], POSITIONS.index(row["position"]), row["player_name"].casefold()),
    )
    return {
        "lineup_count": len(active_lineups),
        "complete_count": sum(all(pos in lineup for pos in POSITIONS) for lineup in active_lineups.values()),
        "positions": positions,
        "solo_picks": solos,
        "same_brain": identical,
        "most_popular": most_popular[0] if most_popular else None,
    }
