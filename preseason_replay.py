from __future__ import annotations

from copy import deepcopy
from typing import Any

from config import NFL_SEASON
from nfl_scoring import score_stat_line
from nfl_sources import ESPNProvider, normalize_name, normalize_team


class PreseasonReplayError(RuntimeError):
    pass


PRESEASON_WEEK = 3
TARGET_TEAMS = {"CHI", "TEN"}
TARGET_LABEL = "Chicago Bears 24 at Tennessee Titans 15 — 2026 Preseason Week 3"
POSITION_ORDER = ("QB", "RB", "WR", "TE", "K")

# Independent anchors from the published NFL recap. These are intentionally
# small and stable: they prove the ESPN summary parser mapped the real box
# score into our normalized fields correctly, rather than merely proving the
# fantasy-scoring formula against synthetic data.
ANCHORS = {
    "Tyson Bagent": {
        "passing_yards": 208.0,
        "passing_tds": 2.0,
    },
    "Zavion Thomas": {
        "receptions": 5.0,
        "receiving_yards": 140.0,
        "receiving_tds": 1.0,
    },
}


def _same_number(left: Any, right: Any, tolerance: float = 0.001) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def _pick_hidden_test_rows(pool: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for position in POSITION_ORDER:
        rows = [row for row in pool if str(row.get("position") or "").upper() == position]
        rows.sort(key=lambda row: int(row.get("slot_rank") or 0), reverse=True)
        row = next((item for item in rows if not bool(item.get("is_visible"))), None)
        if row is None and rows:
            row = rows[0]
        if row is None:
            raise PreseasonReplayError(f"Gate 2 Test Week is missing a {position} player.")
        selected[position] = row
    return selected


def _pool_state_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = (
        "score_total",
        "score_status",
        "score_breakdown",
        "game_status",
        "score_updated_at",
        "espn_player_id",
        "provider_updated_at",
    )
    return {str(row.get("id")): {key: row.get(key) for key in keys} for row in rows}


def _stats_state_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = ("source", "source_player_id", "raw_stats", "points", "breakdown", "game_status")
    return {
        str(row.get("pool_player_id")): {key: row.get(key) for key in keys}
        for row in rows
    }


def _has_meaningful_stats(row: dict[str, Any], position: str) -> bool:
    stats = row.get("stats") or {}
    if position == "QB":
        return any(float(stats.get(key) or 0) != 0 for key in ("passing_yards", "passing_tds", "rushing_yards"))
    if position == "RB":
        return any(float(stats.get(key) or 0) != 0 for key in ("carries", "rushing_yards", "receptions", "receiving_yards"))
    if position in {"WR", "TE"}:
        return any(float(stats.get(key) or 0) != 0 for key in ("receptions", "receiving_yards", "receiving_tds"))
    if position == "K":
        return any(float(stats.get(key) or 0) != 0 for key in ("field_goals_made", "extra_points_made"))
    return False


def _select_real_samples(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for position in POSITION_ORDER:
        candidates = [
            row for row in rows
            if str(row.get("position") or "").upper() == position and _has_meaningful_stats(row, position)
        ]
        if not candidates:
            raise PreseasonReplayError(
                f"The real preseason box score did not expose a usable {position} stat line."
            )
        # Prefer the player with the largest absolute scoring footprint so the
        # replay exercises meaningful values instead of a token 0.1-point line.
        candidates.sort(
            key=lambda row: abs(score_stat_line(row.get("stats") or {}, position).points),
            reverse=True,
        )
        selected[position] = candidates[0]
    return selected


def _find_target_game(provider: ESPNProvider) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = provider.scoreboard(NFL_SEASON, PRESEASON_WEEK, season_type=1)
    games = provider.normalize_games(payload)
    target = next(
        (
            game for game in games
            if {normalize_team(game.get("home_team")), normalize_team(game.get("away_team"))} == TARGET_TEAMS
            and str(game.get("game_status") or "").upper() == "FINAL"
        ),
        None,
    )
    if not target:
        raise PreseasonReplayError("The completed Bears–Titans preseason replay game was not found in ESPN.")
    if not str(target.get("provider_event_id") or ""):
        raise PreseasonReplayError("The preseason game was found but ESPN did not provide an event id.")

    # Independent final-score anchor: Chicago 24, Tennessee 15.
    scores = {
        normalize_team(target.get("home_team")): target.get("home_score"),
        normalize_team(target.get("away_team")): target.get("away_score"),
    }
    if scores.get("CHI") != 24 or scores.get("TEN") != 15:
        raise PreseasonReplayError(
            f"The target preseason game was found, but its final score was unexpected: CHI {scores.get('CHI')} – TEN {scores.get('TEN')}."
        )
    return target, payload


def _anchor_checks(parsed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = {normalize_name(row.get("player_name")): row for row in parsed_rows}
    checks: list[dict[str, Any]] = []
    for player_name, expected_stats in ANCHORS.items():
        row = index.get(normalize_name(player_name))
        if not row:
            raise PreseasonReplayError(f"ESPN box score did not include the expected player {player_name}.")
        raw = row.get("stats") or {}
        for stat_key, expected in expected_stats.items():
            actual = raw.get(stat_key)
            passed = _same_number(actual, expected)
            checks.append({
                "player": player_name,
                "stat": stat_key,
                "expected": expected,
                "actual": actual,
                "pass": passed,
            })
    if not all(bool(check["pass"]) for check in checks):
        raise PreseasonReplayError("The real ESPN box-score parser did not match the known preseason stat anchors.")
    return checks


def _summary_text(stats: dict[str, Any], position: str) -> str:
    if position == "QB":
        return f"{int(stats.get('passing_yards') or 0)} pass yds • {int(stats.get('passing_tds') or 0)} pass TD"
    if position == "RB":
        return f"{int(stats.get('rushing_yards') or 0)} rush yds • {int(stats.get('receptions') or 0)} rec"
    if position in {"WR", "TE"}:
        return f"{int(stats.get('receptions') or 0)} rec • {int(stats.get('receiving_yards') or 0)} rec yds"
    if position == "K":
        return f"{int(stats.get('field_goals_made') or 0)} FG • {int(stats.get('extra_points_made') or 0)} XP"
    return "Real preseason stat line"


def run_preseason_replay(store, *, provider: ESPNProvider | None = None) -> dict[str, Any]:
    """Replay one real 2026 preseason box score through the production parser.

    This is an isolated Gate 3.5 acceptance test. It reads a completed real ESPN
    box score, verifies a few independently known box-score anchors, chooses one
    real stat line at every Pick'em position, scores those lines with the
    production scorer, round-trips them through the real Supabase persistence
    path using hidden Gate 2 Test Week players, proves Week 1 stayed unchanged,
    and restores the test week to its exact prior score/stat state.
    """
    provider = provider or ESPNProvider()
    demo_week = store.get_week_by_season_week(NFL_SEASON, 0, is_demo=True)
    if not demo_week:
        raise PreseasonReplayError("Gate 2 Test Week was not found.")
    real_week = store.get_week_by_season_week(NFL_SEASON, 1, is_demo=False)
    if not real_week:
        raise PreseasonReplayError("Real Week 1 shell was not found; isolation cannot be verified.")

    target_game, _ = _find_target_game(provider)
    summary = provider.summary(str(target_game["provider_event_id"]))
    parsed_rows = provider.player_stats(summary)
    if not parsed_rows:
        raise PreseasonReplayError("ESPN returned the preseason game but no player box-score rows were parsed.")
    anchor_checks = _anchor_checks(parsed_rows)
    real_samples = _select_real_samples(parsed_rows)

    demo_pool = store.get_full_week_pool(str(demo_week["id"]))
    demo_targets = _pick_hidden_test_rows(demo_pool)
    tested_ids = [str(demo_targets[position]["id"]) for position in POSITION_ORDER]

    score_rows: list[dict[str, Any]] = []
    display_rows: list[dict[str, Any]] = []
    for position in POSITION_ORDER:
        real = real_samples[position]
        stats = deepcopy(real.get("stats") or {})
        result = score_stat_line(stats, position)
        score_rows.append({
            "pool_player_id": str(demo_targets[position]["id"]),
            "source": "espn-preseason-replay",
            "source_player_id": real.get("espn_player_id"),
            "raw_stats": stats,
            "points": float(result.points),
            "breakdown": deepcopy(result.breakdown),
            "game_status": "FINAL",
        })
        display_rows.append({
            "position": position,
            "real_player": real.get("player_name"),
            "team": real.get("team_abbr"),
            "stat_summary": _summary_text(stats, position),
            "calculated": float(result.points),
            "stored": None,
            "database_pass": False,
        })

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
        "preseason_replay",
        week_id=str(demo_week["id"]),
        provider="ESPN-real-boxscore",
        metadata={
            "provider_event_id": target_game.get("provider_event_id"),
            "matchup": TARGET_LABEL,
            "tested_pool_player_ids": tested_ids,
        },
    )

    primary_error: Exception | None = None
    cleanup_error: Exception | None = None
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
        for row, position in zip(display_rows, POSITION_ORDER):
            pool_id = str(demo_targets[position]["id"])
            pool_score = (stored_pool.get(pool_id) or {}).get("score_total")
            stat_score = (stored_stats.get(pool_id) or {}).get("points")
            source = (stored_stats.get(pool_id) or {}).get("source")
            expected = float(row["calculated"])
            row["stored"] = float(pool_score or 0)
            row["database_pass"] = (
                _same_number(pool_score, expected)
                and _same_number(stat_score, expected)
                and source == "espn-preseason-replay"
            )

        isolation_pass = real_before == store.scoring_fingerprint(str(real_week["id"]))
        if not all(bool(row["database_pass"]) for row in display_rows):
            raise PreseasonReplayError("One or more real preseason scores did not survive the Supabase round trip.")
        if not isolation_pass:
            raise PreseasonReplayError("Week 1 changed during the isolated preseason replay.")
    except Exception as exc:
        primary_error = exc
    finally:
        try:
            store.restore_player_week_stats(str(demo_week["id"]), tested_ids, original_stats)
            store.restore_pool_score_state(original_pool_state)
            store.update_week_data_state(str(demo_week["id"]), **original_demo_state)
            cleanup_pass = (
                _pool_state_map(store.get_pool_score_state(tested_ids)) == _pool_state_map(original_pool_state)
                and _stats_state_map(store.get_player_week_stats(str(demo_week["id"]), tested_ids)) == _stats_state_map(original_stats)
            )
            if not cleanup_pass:
                raise PreseasonReplayError("The preseason replay passed but cleanup verification failed.")
        except Exception as exc:
            cleanup_error = exc

    success = primary_error is None and cleanup_error is None and cleanup_pass
    message = "Real preseason box score replay passed and test data was restored." if success else str(cleanup_error or primary_error)
    store.finish_data_run(
        run_id,
        success=success,
        message=message,
        metadata={
            "provider_event_id": target_game.get("provider_event_id"),
            "matchup": TARGET_LABEL,
            "anchor_pass": all(bool(check["pass"]) for check in anchor_checks),
            "database_pass": all(bool(row["database_pass"]) for row in display_rows),
            "week1_isolation_pass": isolation_pass,
            "cleanup_pass": cleanup_pass,
            "rows": display_rows,
            "anchors": anchor_checks,
        },
    )

    if not success:
        raise PreseasonReplayError(message)

    return {
        "success": True,
        "matchup": TARGET_LABEL,
        "provider_event_id": target_game.get("provider_event_id"),
        "boxscore_pass": True,
        "anchor_pass": True,
        "database_pass": True,
        "week1_isolation_pass": True,
        "cleanup_pass": True,
        "rows": display_rows,
        "anchors": anchor_checks,
    }
