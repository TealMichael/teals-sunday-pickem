"""Synthetic NFL/database fixtures shared by offline release tests and probes."""

from copy import deepcopy
from threading import get_ident
from types import SimpleNamespace
from store import SupabaseStore

NOW = "2026-10-25T18:00:00+00:00"

WEEK = {"id": "synthetic-week", "season": 2026, "nfl_week": 8,
        "data_status": "LIVE", "locks_at": "2026-10-25T17:00:00+00:00"}

TEAMS = [("BUF", "MIA"), ("NE", "NYJ"), ("BAL", "CIN"),
         ("CLE", "PIT"), ("HOU", "IND"), ("JAX", "TEN"),
         ("DEN", "KC"), ("LV", "LAC"), ("DAL", "NYG"), ("PHI", "WAS")]

def fixture():
    games, pool, summaries = [], [], {}
    for i, (home, away) in enumerate(TEAMS):
        event = f"event-{i:02}"
        games.append({"id": event, "week_id": WEEK["id"], "provider_event_id": event,
                      "home_team": home, "away_team": away, "game_status": "LIVE",
                      "kickoff_at": "2026-10-25T17:00:00+00:00", "is_eligible": True,
                      "completed": False, "period": 2, "game_clock": "8:41",
                      "home_score": 7, "away_score": 10, "provider_updated_at": NOW})
        categories = []
        # One LIVE game deliberately has no players in the entire pool.
        for j, position in enumerate(["QB", "RB", "WR", "TE", "K"] if i < 9 else []):
            name = f"Synthetic {i} {position}"
            ident = f"pool-{i}-{position}"
            pool.append({"id": ident, "week_id": WEEK["id"], "player_name": name,
                         "position": position, "slot_rank": i + 1, "team_abbr": home,
                         "is_visible": i < 5, "score_total": 9.5, "score_updated_at": NOW,
                         "game_status": "LIVE", "manual_score_override": None,
                         "availability_status": "HEALTHY"})
            category, labels, values = {
                "QB": ("passing", ["YDS", "TD", "INT"], ["250", "2", "1"]),
                "RB": ("rushing", ["YDS", "TD"], ["67", "1"]),
                "WR": ("receiving", ["REC", "YDS", "TD"], ["5", "83", "1"]),
                "TE": ("receiving", ["REC", "YDS", "TD"], ["3", "35", "0"]),
                "K": ("kicking", ["FG", "XP"], ["2/3", "3/3"]),
            }[position]
            categories.append({"name": category, "labels": labels,
                               "athletes": [{"athlete": {"id": ident, "displayName": name,
                                               "position": {"abbreviation": position}}, "stats": values}]})
        summaries[event] = {"header": {"competitions": [{"status": {
            "period": 2, "displayClock": "8:41", "type": {"state": "in", "completed": False}},
            "competitors": [{"homeAway": "home", "score": "7", "team": {"abbreviation": home}},
                            {"homeAway": "away", "score": "10", "team": {"abbreviation": away}}]}]},
            "boxscore": {"players": [{"team": {"abbreviation": home}, "statistics": categories}]}}
    return games, pool, summaries

class Query:
    def __init__(self, store, table):
        self.store, self.table = store, table
        self.operation, self.payload, self.filters = "select", None, []
        self.conflict = "id"
        self.ordering, self.maximum = [], None
    def select(self, *a, **kw): return self
    def order(self, key, desc=False):
        self.ordering.append((key,desc))
        return self
    def limit(self, maximum):
        self.maximum = maximum
        return self
    def lt(self, key, value):
        self.filters.append(lambda row: row.get(key) is not None and row[key] < value)
        return self
    def delete(self):
        self.operation = "delete"
        return self
    def eq(self, key, value):
        self.filters.append(lambda row: row.get(key) == value)
        return self
    def in_(self, key, values):
        self.filters.append(lambda row: row.get(key) in values)
        return self
    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self
    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self
    def upsert(self, payload, on_conflict="id"):
        self.operation, self.payload, self.conflict = "upsert", payload, on_conflict
        return self
    def execute(self):
        self.store.operations.append(f"{self.table}.{self.operation}")
        assert get_ident() == self.store.owner, "Database operations left caller thread"
        rows = self.store.tables.setdefault(self.table, [])
        matched = [row for row in rows if all(f(row) for f in self.filters)]
        if self.operation == "select":
            result = matched
            for key,desc in reversed(self.ordering):
                result = sorted(result,key=lambda r:(r.get(key) is None,r.get(key)),reverse=desc)
            if self.maximum is not None: result = result[:self.maximum]
        elif self.operation == "delete":
            result = deepcopy(matched)
            rows[:] = [r for r in rows if r not in matched]
        elif self.operation == "update":
            for row in matched: row.update(deepcopy(self.payload))
            result = matched
        else:
            incoming = deepcopy(self.payload if isinstance(self.payload, list) else [self.payload])
            keys = self.conflict.split(",")
            for row in incoming:
                if self.operation == "insert" and self.table == "refresh_leases":
                    if any(r["lease_key"] == row["lease_key"] for r in rows):
                        raise RuntimeError("Synthetic duplicate lease")
                old = next((r for r in rows if all(r.get(k) == row.get(k) for k in keys)), None)
                if self.operation == "upsert" and old is not None: old.update(row)
                else:
                    row.setdefault("id", f"synthetic-{self.table}-{len(rows)}")
                    rows.append(row)
            result = incoming
        return SimpleNamespace(data=deepcopy(result))

class Store(SupabaseStore):
    def __init__(self, games, pool):
        self.owner = get_ident()
        self.operations = []
        self._public_cache = {}
        self.tables = {"weeks": [deepcopy(WEEK)], "nfl_games": deepcopy(games),
                       "player_pool": deepcopy(pool), "player_week_stats": [], "data_runs": [],
                       "lineups": [{"id": "lineup-1", "week_id": WEEK["id"], "player_id": "person-1"}],
                       "players": [{"id": "person-1", "nickname": "Synthetic"}],
                       "lineup_picks": [{"id": "pick-1", "lineup_id": "lineup-1", "position": "QB",
                                         "pool_player_id": "pool-0-QB", "emergency_pool_player_id": "pool-5-QB"}]}
    def _table(self, name): return Query(self, name)
