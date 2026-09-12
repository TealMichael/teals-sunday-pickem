from copy import deepcopy

from preseason_replay import run_preseason_replay


class FakeProvider:
    def summary(self, event_id):
        assert event_id == "401-test"
        return {"fixture": True}

    def player_stats(self, payload):
        assert payload == {"fixture": True}
        return [
            {"player_name": "Tyson Bagent", "team_abbr": "CHI", "position": None, "espn_player_id": "qb", "stats": {"passing_yards": 208, "passing_tds": 2, "rushing_yards": 6}},
            {"player_name": "Roschon Johnson", "team_abbr": "CHI", "position": None, "espn_player_id": "rb", "stats": {"carries": 15, "rushing_yards": 52, "rushing_tds": 1}},
            {"player_name": "Zavion Thomas", "team_abbr": "CHI", "position": None, "espn_player_id": "wr", "stats": {"receptions": 5, "receiving_yards": 140, "receiving_tds": 1}},
            {"player_name": "Kylen Granson", "team_abbr": "TEN", "position": None, "espn_player_id": "te", "stats": {"receptions": 3, "receiving_yards": 39}},
            {"player_name": "Joey Slye", "team_abbr": "TEN", "position": None, "espn_player_id": "k", "stats": {"field_goals_made": 3, "extra_points_made": 0}},
        ]


class FakeScheduleProvider:
    def schedule_games(self, season, week, week_id=None, *, game_type="REG"):
        assert season == 2026
        assert week == 3
        assert game_type == "PRE"
        return [{
            "provider_event_id": "401-test",
            "home_team": "TEN",
            "away_team": "CHI",
            "home_score": 15,
            "away_score": 24,
            "game_status": "FINAL",
        }]


class FakeStore:
    def __init__(self):
        self.demo_week = {"id": "demo", "season": 2026, "nfl_week": 0, "is_demo": True, "data_status": "WAITING", "last_data_refresh_at": None, "finalized_at": None, "data_message": None}
        self.real_week = {"id": "real", "season": 2026, "nfl_week": 1, "is_demo": False}
        self.pool = []
        for pos in ("QB", "RB", "WR", "TE", "K"):
            self.pool.append({
                "id": f"{pos}-10", "week_id": "demo", "position": pos, "slot_rank": 10, "is_visible": False,
                "player_name": f"Demo {pos}", "score_total": None, "score_status": "SCHEDULED", "score_breakdown": {},
                "game_status": None, "score_updated_at": None, "espn_player_id": None, "provider_updated_at": None,
            })
        self.real_pool = [{"id": "real-1", "week_id": "real", "score_total": None, "score_status": "SCHEDULED", "score_breakdown": {}, "game_status": None, "score_updated_at": None, "manual_score_override": None, "manual_override_at": None}]
        self.stats = {"demo": {}, "real": {}}
        self.run = None

    def get_week_by_season_week(self, season, week, *, is_demo=False):
        if season == 2026 and week == 0 and is_demo:
            return deepcopy(self.demo_week)
        if season == 2026 and week == 1 and not is_demo:
            return deepcopy(self.real_week)
        return None

    def get_full_week_pool(self, week_id):
        return deepcopy(self.pool if week_id == "demo" else self.real_pool)

    def get_pool_score_state(self, ids):
        wanted = set(ids)
        return [deepcopy(row) for row in self.pool if row["id"] in wanted]

    def get_player_week_stats(self, week_id, ids=None):
        rows = list(self.stats.get(week_id, {}).values())
        if ids:
            wanted = set(ids)
            rows = [row for row in rows if row["pool_player_id"] in wanted]
        return deepcopy(rows)

    def upsert_player_week_stats(self, week_id, rows):
        for row in rows:
            item = deepcopy(row)
            item["week_id"] = week_id
            self.stats.setdefault(week_id, {})[item["pool_player_id"]] = item
        return deepcopy(rows)

    def apply_pool_scores(self, week, rows, *, score_status):
        by_id = {row["pool_player_id"]: row for row in rows}
        for pool_row in self.pool:
            if pool_row["id"] in by_id:
                score = by_id[pool_row["id"]]
                pool_row["score_total"] = score["points"]
                pool_row["score_status"] = score_status
                pool_row["score_breakdown"] = deepcopy(score["breakdown"])
                pool_row["game_status"] = score["game_status"]
                pool_row["espn_player_id"] = score["source_player_id"]
        self.demo_week["data_status"] = score_status
        return []

    def scoring_fingerprint(self, week_id):
        if week_id == "real":
            return {"pool": deepcopy(self.real_pool), "stats": deepcopy(self.stats["real"])}
        return {"pool": deepcopy(self.pool), "stats": deepcopy(self.stats["demo"])}

    def restore_player_week_stats(self, week_id, ids, original_rows):
        wanted = set(ids)
        current = self.stats.setdefault(week_id, {})
        for key in list(current):
            if key in wanted:
                del current[key]
        for row in original_rows:
            current[row["pool_player_id"]] = deepcopy(row)

    def restore_pool_score_state(self, rows):
        by_id = {row["id"]: row for row in rows}
        for idx, pool_row in enumerate(self.pool):
            if pool_row["id"] in by_id:
                saved = by_id[pool_row["id"]]
                for key in ("score_total", "score_status", "score_breakdown", "game_status", "score_updated_at", "espn_player_id", "provider_updated_at"):
                    pool_row[key] = deepcopy(saved.get(key))

    def update_week_data_state(self, week_id, **kwargs):
        if week_id == "demo":
            self.demo_week.update(kwargs)

    def start_data_run(self, run_type, *, week_id=None, provider=None, metadata=None):
        self.run = {"id": "run", "run_type": run_type, "week_id": week_id, "provider": provider, "metadata": metadata}
        return "run"

    def finish_data_run(self, run_id, *, success, message="", metadata=None):
        self.run.update({"success": success, "message": message, "result_metadata": metadata})


def test_real_preseason_replay_roundtrips_and_cleans_up():
    store = FakeStore()
    before = deepcopy(store.pool)
    result = run_preseason_replay(store, provider=FakeProvider(), schedule_provider=FakeScheduleProvider())
    assert result["success"] is True
    assert result["boxscore_pass"] is True
    assert result["anchor_pass"] is True
    assert result["database_pass"] is True
    assert result["week1_isolation_pass"] is True
    assert result["cleanup_pass"] is True
    assert len(result["rows"]) == 5
    assert store.pool == before
    assert store.stats["demo"] == {}
