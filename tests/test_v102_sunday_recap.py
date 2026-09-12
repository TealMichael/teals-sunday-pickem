from pathlib import Path

from gate4 import build_share_summary, build_season_standings, build_weekly_leaderboard, build_weekly_recap
from weekly import lineup_readiness

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def _pool():
    rows = []
    for pos in POSITIONS:
        for slot in (1, 2, 3):
            score = 10.0
            if pos == "QB" and slot == 3:
                score = 30.0
            if pos == "K" and slot == 3:
                score = 20.0
            rows.append({
                "id": f"{pos}{slot}",
                "position": pos,
                "player_name": f"{pos} {slot}",
                "team_abbr": "DET",
                "opponent_abbr": "GB",
                "availability_status": "HEALTHY",
                "score_total": score,
                "score_breakdown": {},
                "game_status": "FINAL",
            })
    return rows


def _bundle():
    players = [
        {"id": "p1", "nickname": "Mike", "emoji": "🏈"},
        {"id": "p2", "nickname": "Jenny", "emoji": "🦅"},
        {"id": "p3", "nickname": "Alan", "emoji": "🐺"},
        {"id": "p4", "nickname": "Chris", "emoji": "🔥"},
    ]
    lineups = [{"id": f"l{i}", "player_id": f"p{i}", "confirmed_at": "x"} for i in range(1, 5)]
    choices = {
        "l1": [1, 1, 1, 1, 1],
        "l2": [1, 1, 1, 1, 1],
        "l3": [3, 1, 1, 1, 1],
        "l4": [1, 1, 1, 1, 3],
    }
    picks = []
    for lineup_id, slots in choices.items():
        for pos, slot in zip(POSITIONS, slots):
            picks.append({
                "lineup_id": lineup_id,
                "position": pos,
                "pool_player_id": f"{pos}{slot}",
                "emergency_pool_player_id": None,
            })
    return {"players": players, "lineups": lineups, "picks": picks, "pool": _pool(), "games": []}


def _picks_for_one():
    return [
        {"position": pos, "pool_player_id": f"{pos}1", "emergency_pool_player_id": None}
        for pos in POSITIONS
    ]


def test_lineup_readiness_keeps_questionable_visible_after_backup_is_set():
    pool = _pool()
    by_id = {row["id"]: row for row in pool}
    picks = _picks_for_one()
    by_id["WR1"]["availability_status"] = "QUESTIONABLE"

    needs = lineup_readiness(picks, by_id)
    assert needs["ready"] is False
    assert needs["questionable"] == ["WR"]
    assert needs["needs_backup"] == ["WR"]

    wr_pick = next(p for p in picks if p["position"] == "WR")
    wr_pick["emergency_pool_player_id"] = "WR2"
    ready = lineup_readiness(picks, by_id)
    assert ready["ready"] is True
    assert ready["questionable"] == ["WR"]
    assert ready["needs_backup"] == []


def test_lineup_readiness_surfaces_out_and_missing_players():
    by_id = {row["id"]: row for row in _pool()}
    picks = _picks_for_one()[:-1]
    by_id["QB1"]["availability_status"] = "OUT"
    status = lineup_readiness(picks, by_id)
    assert status["ready"] is False
    assert status["missing"] == ["K"]
    assert status["unavailable"] == ["QB"]


def test_final_recap_builds_champion_social_awards_and_biggest_mover():
    bundle = _bundle()
    leaderboard = build_weekly_leaderboard(bundle)
    season_results = [
        {"nfl_week": 1, "player_id": "p1", "nickname_snapshot": "Mike", "emoji_snapshot": "🏈", "season_points": 12, "weekly_score": 100, "finish_rank": 1},
        {"nfl_week": 1, "player_id": "p2", "nickname_snapshot": "Jenny", "emoji_snapshot": "🦅", "season_points": 9, "weekly_score": 90, "finish_rank": 2},
        {"nfl_week": 1, "player_id": "p3", "nickname_snapshot": "Alan", "emoji_snapshot": "🐺", "season_points": 7, "weekly_score": 80, "finish_rank": 3},
        {"nfl_week": 1, "player_id": "p4", "nickname_snapshot": "Chris", "emoji_snapshot": "🔥", "season_points": 6, "weekly_score": 70, "finish_rank": 4},
        {"nfl_week": 2, "player_id": "p1", "nickname_snapshot": "Mike", "emoji_snapshot": "🏈", "season_points": 7, "weekly_score": 50, "finish_rank": 3},
        {"nfl_week": 2, "player_id": "p2", "nickname_snapshot": "Jenny", "emoji_snapshot": "🦅", "season_points": 7, "weekly_score": 50, "finish_rank": 3},
        {"nfl_week": 2, "player_id": "p3", "nickname_snapshot": "Alan", "emoji_snapshot": "🐺", "season_points": 12, "weekly_score": 90, "finish_rank": 1},
        {"nfl_week": 2, "player_id": "p4", "nickname_snapshot": "Chris", "emoji_snapshot": "🔥", "season_points": 9, "weekly_score": 60, "finish_rank": 2},
    ]

    recap = build_weekly_recap(bundle, leaderboard, season_results, current_week=2)
    assert [row["nickname"] for row in recap["champions"]] == ["Alan"]
    assert recap["most_popular"]["count"] == 4
    assert recap["boldest_solo"] == {"nickname": "Alan", "player_name": "QB 3", "points": 30.0}
    assert recap["closest_finish"]["tied"] is True
    assert {recap["closest_finish"]["upper"], recap["closest_finish"]["lower"]} == {"Mike", "Jenny"}
    assert set(recap["same_brain"]) == {"Mike", "Jenny"}
    assert recap["biggest_mover"]["places"] == 2
    assert [row["nickname"] for row in recap["biggest_mover"]["movers"]] == ["Alan"]

    season = build_season_standings(season_results)
    share = build_share_summary({"label": "Week 2", "nfl_week": 2}, recap, leaderboard, season)
    assert "Week 2 FINAL" in share
    assert "🏆 Champion: Alan" in share
    assert "🦄 Boldest solo: Alan on QB 3" in share
    assert "👯 Same Brain: Jenny + Mike" in share or "👯 Same Brain: Mike + Jenny" in share
    assert "📈 Biggest mover: Alan (+2 places)" in share


def test_v102_ui_contract_final_recap_and_sunday_status_are_scoped():
    app = (ROOT / "app.py").read_text("utf-8")
    weekly_ui = (ROOT / "weekly_ui.py").read_text("utf-8")
    gate4_ui = (ROOT / "gate4_ui.py").read_text("utf-8")
    ui = (ROOT / "ui.py").read_text("utf-8")

    assert "WEEKLY_UI_SCHEMA_VERSION = 9" in weekly_ui
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 9' in app
    assert "GATE4_UI_SCHEMA_VERSION = 4" in gate4_ui
    assert 'getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 4' in app
    assert "_render_live_prelock_status(store, week, player)" in weekly_ui
    assert "NFL data updated" in weekly_ui
    assert "if data_status == \"FINAL\":" in gate4_ui
    assert "_weekly_recap(store, fresh_week, bundle, leaderboard)" in gate4_ui
    assert "Copy recap for group chat" in gate4_ui
    assert ".sunday-status" in ui
    assert ".recap-grid" in ui
