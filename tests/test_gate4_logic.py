from gate4 import (
    add_zero_point_players,
    build_season_standings,
    build_storylines,
    build_weekly_leaderboard,
    competition_ranks,
    season_points_for_rank,
)


def _bundle():
    players = [
        {"id": "p1", "nickname": "Mike", "emoji": "🏈"},
        {"id": "p2", "nickname": "Jenny", "emoji": "🦅"},
        {"id": "p3", "nickname": "Alan", "emoji": "🐺"},
    ]
    pool = []
    for pos in ("QB", "RB", "WR", "TE", "K"):
        for slot in (1, 2, 3):
            pool.append({
                "id": f"{pos}{slot}", "position": pos, "player_name": f"{pos} {slot}",
                "team_abbr": "DET", "opponent_abbr": "GB", "availability_status": "HEALTHY",
                "score_total": 10 + slot, "score_breakdown": {}, "game_status": "LIVE",
            })
    # Mike and Jenny same five; Alan goes alone on QB3.
    lineups = [
        {"id": "l1", "player_id": "p1", "confirmed_at": "x"},
        {"id": "l2", "player_id": "p2", "confirmed_at": "x"},
        {"id": "l3", "player_id": "p3", "confirmed_at": "x"},
    ]
    picks = []
    for lid, slots in (("l1", [1,1,1,1,1]), ("l2", [1,1,1,1,1]), ("l3", [3,2,2,2,2])):
        for pos, slot in zip(("QB","RB","WR","TE","K"), slots):
            picks.append({"lineup_id": lid, "position": pos, "pool_player_id": f"{pos}{slot}", "emergency_pool_player_id": None})
    return {"players": players, "pool": pool, "lineups": lineups, "picks": picks, "games": []}


def test_competition_ranking_and_season_points():
    assert competition_ranks([90.0, 80.0, 80.0, 70.0]) == [1, 2, 2, 4]
    assert season_points_for_rank(1) == 12
    assert season_points_for_rank(2) == 9
    assert season_points_for_rank(4) == 6
    assert season_points_for_rank(10) == 0


def test_live_leaderboard_and_storylines():
    bundle = _bundle()
    rows = build_weekly_leaderboard(bundle)
    assert len(rows) == 3
    assert rows[0]["rank"] == 1
    story = build_storylines(bundle, rows)
    assert story["most_popular"]["count"] == 2
    assert any(item["player_name"] == "QB 3" for item in story["went_alone"])
    assert any(set(group) == {"Mike", "Jenny"} for group in story["same_brain"])


def test_emergency_backup_activates_only_for_out_starter():
    bundle = _bundle()
    starter = next(row for row in bundle["pool"] if row["id"] == "QB1")
    backup = next(row for row in bundle["pool"] if row["id"] == "QB2")
    starter["availability_status"] = "OUT"
    pick = next(p for p in bundle["picks"] if p["lineup_id"] == "l1" and p["position"] == "QB")
    pick["emergency_pool_player_id"] = backup["id"]
    rows = build_weekly_leaderboard(bundle)
    mike = next(r for r in rows if r["player_id"] == "p1")
    qb = next(r for r in mike["roster"] if r["position"] == "QB")
    assert qb["emergency_activated"] is True
    assert qb["player"]["id"] == "QB2"


def test_season_standings_tiebreak_and_zero_joiner():
    results = [
        {"player_id":"p1","nickname_snapshot":"Mike","emoji_snapshot":"🏈","season_points":12,"weekly_score":80,"finish_rank":1},
        {"player_id":"p2","nickname_snapshot":"Jenny","emoji_snapshot":"🦅","season_points":12,"weekly_score":90,"finish_rank":1},
    ]
    standings = build_season_standings(results)
    assert standings[0]["nickname"] == "Jenny"
    with_zero = add_zero_point_players(standings, [{"id":"p3","nickname":"Alan","emoji":"🐺"}])
    assert with_zero[-1]["nickname"] == "Alan"
    assert with_zero[-1]["season_points"] == 0


def test_weekly_ranking_uses_display_precision_for_ties():
    bundle = _bundle()
    # Make Mike/Jenny totals differ beneath the displayed tenth; they should tie.
    for row in bundle["pool"]:
        if row["id"] == "QB1":
            row["score_total"] = 11.04
    rows = build_weekly_leaderboard(bundle)
    mike = next(r for r in rows if r["player_id"] == "p1")
    jenny = next(r for r in rows if r["player_id"] == "p2")
    assert mike["score"] == jenny["score"]
    assert mike["rank"] == jenny["rank"]
