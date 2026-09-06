from __future__ import annotations

from copy import deepcopy
from typing import Any

from config import NFL_SEASON
from nfl_scoring import score_stat_line


class ScoringDiagnosticError(RuntimeError):
    pass


SCENARIOS: dict[str, dict[str, Any]] = {
    "QB": {
        "label": "Passing + rushing + INT + 2-point",
        "stats": {
            "passing_yards": 287,
            "passing_tds": 2,
            "interceptions": 1,
            "rushing_yards": 37,
            "rushing_tds": 1,
            "passing_2pt_conversions": 1,
        },
        "expected": 29.18,
    },
    "RB": {
        "label": "Half-PPR + rushing + fumble + 2-point",
        "stats": {
            "rushing_yards": 87,
            "rushing_tds": 1,
            "receptions": 4,
            "receiving_yards": 25,
            "fumbles_lost": 1,
            "receiving_2pt_conversions": 1,
        },
        "expected": 19.2,
    },
    "WR": {
        "label": "Half-PPR + trick-play pass TD + return TD",
        "stats": {
            "receptions": 6,
            "receiving_yards": 104,
            "receiving_tds": 1,
            "passing_yards": 25,
            "passing_tds": 1,
            "punt_return_tds": 1,
        },
        "expected": 30.4,
    },
    "TE": {
        "label": "Fractional half-PPR receiving",
        "stats": {
            "receptions": 7,
            "receiving_yards": 63,
            "receiving_tds": 1,
        },
        "expected": 15.8,
    },
    "K": {
        "label": "Flat 3-point FGs + XPs; misses ignored",
        "stats": {
            "field_goals_made": 4,
            "field_goals_missed": 2,
            "extra_points_made": 3,
            "extra_points_missed": 1,
        },
        "expected": 15.0,
    },
}


def _pick_hidden_test_rows(pool: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for position in ("QB", "RB", "WR", "TE", "K"):
        rows = [row for row in pool if str(row.get("position")) == position]
        rows.sort(key=lambda row: int(row.get("slot_rank") or 0), reverse=True)
        row = next((item for item in rows if not bool(item.get("is_visible"))), None)
        if row is None and rows:
            row = rows[0]
        if row is None:
            raise ScoringDiagnosticError(f"Test week is missing a {position} player.")
        selected[position] = row
    return selected




def _pool_state_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = ("score_total", "score_status", "score_breakdown", "game_status", "espn_player_id")
    return {
        str(row.get("id")): {key: row.get(key) for key in keys}
        for row in rows
    }


def _stats_state_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = ("source", "source_player_id", "raw_stats", "points", "breakdown", "game_status")
    return {
        str(row.get("pool_player_id")): {key: row.get(key) for key in keys}
        for row in rows
    }

def _same_number(left: Any, right: Any, tolerance: float = 0.001) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def run_scoring_diagnostic(store) -> dict[str, Any]:
    """Round-trip controlled scoring through Supabase using only the demo week.

    The test writes controlled stat lines to hidden Gate 2 test-week players,
    applies the same pool-scoring persistence path used on Sundays, reads the
    values back, verifies real Week 1's scoring footprint did not change, and
    then restores the demo week to its exact pre-test score/stat state.
    """
    demo_week = store.get_week_by_season_week(NFL_SEASON, 0, is_demo=True)
    if not demo_week:
        raise ScoringDiagnosticError("Gate 2 Test Week was not found.")

    real_week = store.get_week_by_season_week(NFL_SEASON, 1, is_demo=False)
    if not real_week:
        raise ScoringDiagnosticError("Real Week 1 shell was not found; isolation cannot be verified.")
    demo_pool = store.get_full_week_pool(str(demo_week["id"]))
    selected = _pick_hidden_test_rows(demo_pool)
    tested_ids = [str(selected[position]["id"]) for position in ("QB", "RB", "WR", "TE", "K")]

    math_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    for position in ("QB", "RB", "WR", "TE", "K"):
        scenario = SCENARIOS[position]
        result = score_stat_line(scenario["stats"], position)
        expected = float(scenario["expected"])
        math_ok = _same_number(result.points, expected)
        math_rows.append(
            {
                "position": position,
                "player": selected[position].get("player_name"),
                "scenario": scenario["label"],
                "expected": expected,
                "calculated": float(result.points),
                "math_pass": math_ok,
            }
        )
        score_rows.append(
            {
                "pool_player_id": str(selected[position]["id"]),
                "source": "gate3-scoring-diagnostic",
                "source_player_id": f"diagnostic-{position.lower()}",
                "raw_stats": deepcopy(scenario["stats"]),
                "points": float(result.points),
                "breakdown": deepcopy(result.breakdown),
                "game_status": "FINAL",
            }
        )

    original_pool_state = store.get_pool_score_state(tested_ids)
    original_stats = store.get_player_week_stats(str(demo_week["id"]), tested_ids)
    original_demo_state = {
        "data_status": demo_week.get("data_status"),
        "last_data_refresh_at": demo_week.get("last_data_refresh_at"),
        "finalized_at": demo_week.get("finalized_at"),
        "data_message": demo_week.get("data_message"),
    }
    real_before = store.scoring_fingerprint(str(real_week["id"]))

    run_id = store.start_data_run(
        "scoring_diagnostic",
        week_id=str(demo_week["id"]),
        provider="controlled-test",
        metadata={"tested_pool_player_ids": tested_ids},
    )

    primary_error: Exception | None = None
    cleanup_error: Exception | None = None
    roundtrip_rows: list[dict[str, Any]] = []
    isolation_pass = False
    cleanup_pass = False

    try:
        store.upsert_player_week_stats(str(demo_week["id"]), score_rows)
        store.apply_pool_scores(demo_week, score_rows, score_status="FINAL")

        stored_pool = {str(row["id"]): row for row in store.get_pool_score_state(tested_ids)}
        stored_stats = {
            str(row["pool_player_id"]): row
            for row in store.get_player_week_stats(str(demo_week["id"]), tested_ids)
        }

        for row in math_rows:
            position = str(row["position"])
            pool_id = str(selected[position]["id"])
            expected = float(row["expected"])
            pool_score = (stored_pool.get(pool_id) or {}).get("score_total")
            stat_score = (stored_stats.get(pool_id) or {}).get("points")
            source = (stored_stats.get(pool_id) or {}).get("source")
            db_pass = (
                _same_number(pool_score, expected)
                and _same_number(stat_score, expected)
                and source == "gate3-scoring-diagnostic"
            )
            roundtrip_rows.append(
                {
                    **row,
                    "stored_pool": float(pool_score or 0),
                    "stored_stats": float(stat_score or 0),
                    "database_pass": db_pass,
                }
            )

        real_after = store.scoring_fingerprint(str(real_week["id"]))
        isolation_pass = real_before == real_after

        if not all(bool(row["math_pass"]) for row in roundtrip_rows):
            raise ScoringDiagnosticError("One or more scoring formulas did not match the expected result.")
        if not all(bool(row["database_pass"]) for row in roundtrip_rows):
            raise ScoringDiagnosticError("One or more controlled scores did not survive the Supabase round trip.")
        if not isolation_pass:
            raise ScoringDiagnosticError("Week 1 scoring data changed during the isolated scoring test.")
    except Exception as exc:
        primary_error = exc
    finally:
        try:
            store.restore_player_week_stats(str(demo_week["id"]), tested_ids, original_stats)
            store.restore_pool_score_state(original_pool_state)
            store.update_week_data_state(str(demo_week["id"]), **original_demo_state)

            restored_pool = store.get_pool_score_state(tested_ids)
            restored_stats = store.get_player_week_stats(str(demo_week["id"]), tested_ids)
            cleanup_pass = (
                _pool_state_map(restored_pool) == _pool_state_map(original_pool_state)
                and _stats_state_map(restored_stats) == _stats_state_map(original_stats)
            )
            if not cleanup_pass:
                raise ScoringDiagnosticError("The demo scoring rows were tested successfully but cleanup verification failed.")
        except Exception as exc:
            cleanup_error = exc

    success = primary_error is None and cleanup_error is None and cleanup_pass
    message = "Controlled scoring round trip passed and the test week was restored." if success else str(cleanup_error or primary_error)
    store.finish_data_run(
        run_id,
        success=success,
        message=message,
        metadata={
            "math_pass": all(bool(row.get("math_pass")) for row in roundtrip_rows) if roundtrip_rows else False,
            "database_pass": all(bool(row.get("database_pass")) for row in roundtrip_rows) if roundtrip_rows else False,
            "week1_isolation_pass": isolation_pass,
            "cleanup_pass": cleanup_pass,
            "rows": roundtrip_rows,
        },
    )

    if not success:
        raise ScoringDiagnosticError(message)

    return {
        "success": True,
        "math_pass": True,
        "database_pass": True,
        "week1_isolation_pass": True,
        "cleanup_pass": True,
        "rows": roundtrip_rows,
        "tested_week": demo_week.get("label") or "Gate 2 Test Week",
        "week1_label": (real_week or {}).get("label") or "Week 1",
    }
