from copy import deepcopy

from scoring_diagnostic import SCENARIOS, run_scoring_diagnostic


class FakeScoringStore:
    def __init__(self):
        self.demo_week = {
            "id": "demo-week",
            "season": 2026,
            "nfl_week": 0,
            "label": "Gate 2 Test Week",
            "is_demo": True,
            "data_status": "WAITING",
            "last_data_refresh_at": None,
            "finalized_at": None,
            "data_message": None,
        }
        self.real_week = {
            "id": "real-week",
            "season": 2026,
            "nfl_week": 1,
            "label": "Week 1",
            "is_demo": False,
            "data_status": "WAITING",
        }
        self.demo_pool = []
        for pos in ("QB", "RB", "WR", "TE", "K"):
            self.demo_pool.append({
                "id": f"{pos}-10",
                "week_id": "demo-week",
                "position": pos,
                "slot_rank": 10,
                "player_name": f"Demo {pos} Juliet",
                "is_visible": False,
                "score_total": None,
                "score_status": "SCHEDULED",
                "score_breakdown": {},
                "game_status": None,
                "score_updated_at": None,
                "espn_player_id": None,
                "provider_updated_at": None,
            })
        self.real_pool = [{
            "id": "real-qb-1",
            "week_id": "real-week",
            "position": "QB",
            "score_total": None,
            "score_status": "SCHEDULED",
            "score_breakdown": {},
            "game_status": None,
            "score_updated_at": None,
            "manual_score_override": None,
            "manual_override_at": None,
        }]
        self.stats = {"demo-week": {}, "real-week": {}}
        self.run = None

    def get_week_by_season_week(self, season, week, *, is_demo=False):
        if season == 2026 and week == 0 and is_demo:
            return deepcopy(self.demo_week)
        if season == 2026 and week == 1 and not is_demo:
            return deepcopy(self.real_week)
        return None

    def get_full_week_pool(self, week_id):
        return deepcopy(self.demo_pool if week_id == "demo-week" else self.real_pool)

    def get_pool_score_state(self, ids):
        wanted = set(ids)
        return [deepcopy(row) for row in self.demo_pool if row["id"] in wanted]

    def get_player_week_stats(self, week_id, ids=None):
        rows = list(self.stats.get(week_id, {}).values())
        if ids:
            wanted = set(ids)
            rows = [row for row in rows if row["pool_player_id"] in wanted]
        return deepcopy(rows)

    def scoring_fingerprint(self, week_id):
        if week_id == "real-week":
            return {"pool": deepcopy(self.real_pool), "stats": deepcopy(list(self.stats[week_id].values()))}
        return {"pool": deepcopy(self.demo_pool), "stats": deepcopy(list(self.stats[week_id].values()))}

    def start_data_run(self, run_type, *, week_id=None, provider=None, metadata=None):
        self.run = {"type": run_type, "week_id": week_id, "provider": provider, "metadata": metadata}
        return "run-1"

    def upsert_player_week_stats(self, week_id, rows):
        for row in rows:
            item = deepcopy(row)
            item["week_id"] = week_id
            item["id"] = f"stat-{row['pool_player_id']}"
            item["updated_at"] = "now"
            self.stats[week_id][row["pool_player_id"]] = item
        return self.get_player_week_stats(week_id)

    def apply_pool_scores(self, week, rows, *, score_status):
        by_id = {row["pool_player_id"]: row for row in rows}
        for pool_row in self.demo_pool:
            score = by_id.get(pool_row["id"])
            if not score:
                continue
            pool_row["score_total"] = score["points"]
            pool_row["score_status"] = score_status
            pool_row["score_breakdown"] = deepcopy(score["breakdown"])
            pool_row["game_status"] = score["game_status"]
            pool_row["espn_player_id"] = score["source_player_id"]
            pool_row["score_updated_at"] = "now"
            pool_row["provider_updated_at"] = "now"
        self.demo_week["data_status"] = score_status
        self.demo_week["last_data_refresh_at"] = "now"
        self.demo_week["data_message"] = "Final score refresh complete."

    def restore_player_week_stats(self, week_id, ids, original_rows):
        for pool_id in ids:
            self.stats[week_id].pop(pool_id, None)
        for row in original_rows:
            self.stats[week_id][row["pool_player_id"]] = deepcopy(row)

    def restore_pool_score_state(self, rows):
        before = {row["id"]: row for row in rows}
        for current in self.demo_pool:
            original = before.get(current["id"])
            if original:
                current.clear()
                current.update(deepcopy(original))

    def update_week_data_state(self, week_id, **fields):
        if week_id == "demo-week":
            self.demo_week.update(fields)

    def finish_data_run(self, run_id, *, success, message="", metadata=None):
        self.run.update({"success": success, "message": message, "result_metadata": metadata})


def test_controlled_scenarios_cover_expected_rules():
    assert set(SCENARIOS) == {"QB", "RB", "WR", "TE", "K"}
    assert SCENARIOS["QB"]["expected"] == 29.18
    assert SCENARIOS["RB"]["expected"] == 19.2
    assert SCENARIOS["WR"]["expected"] == 30.4
    assert SCENARIOS["TE"]["expected"] == 15.8
    assert SCENARIOS["K"]["expected"] == 15.0
    assert SCENARIOS["K"]["stats"]["field_goals_made"] == 4
    assert SCENARIOS["K"]["stats"]["field_goals_missed"] == 2


def test_scoring_diagnostic_round_trips_and_restores_demo_state():
    store = FakeScoringStore()
    demo_before = deepcopy(store.demo_pool)
    week_before = deepcopy(store.demo_week)
    real_before = store.scoring_fingerprint("real-week")

    result = run_scoring_diagnostic(store)

    assert result["success"] is True
    assert result["math_pass"] is True
    assert result["database_pass"] is True
    assert result["week1_isolation_pass"] is True
    assert result["cleanup_pass"] is True
    assert all(row["math_pass"] and row["database_pass"] for row in result["rows"])
    assert store.demo_pool == demo_before
    assert store.demo_week == week_before
    assert store.scoring_fingerprint("real-week") == real_before
    assert store.run["success"] is True
