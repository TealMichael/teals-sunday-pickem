from nfl_rankings import WEEK1_CANDIDATES, week1_kicker_team_order, week1_rankings


def _games():
    teams = ["PHI","BAL","BUF","CIN","LAC","NYG","DAL","CHI","WAS","JAX","TB","HOU","GB","CAR","DET","ATL","IND","MIA","LV","NO","MIN","CLE","ARI"]
    games = []
    seen = set()
    for i in range(0, len(teams)-1, 2):
        home, away = teams[i], teams[i+1]
        seen.update([home, away])
        games.append({
            "home_team": home, "away_team": away,
            "kickoff_at": "2026-09-13T17:00:00+00:00", "is_eligible": True,
            "over_under": 50 - i/4, "spread": -3, "favored_team": home,
        })
    # Ensure DET/NO etc if odd list positioning left anything out.
    return games


def _players():
    by_pos = {"QB": [], "RB": [], "WR": [], "TE": [], "K": []}
    for pos, candidates in WEEK1_CANDIDATES.items():
        for idx, (name, team) in enumerate(candidates):
            by_pos[pos].append({
                "sleeper_player_id": f"{pos}{idx}", "full_name": name, "position": pos,
                "team_abbr": team, "active": True, "availability_status": "HEALTHY", "injury_status": None,
            })
    # One primary kicker per eligible team.
    for idx, team in enumerate({t for g in _games() for t in (g["home_team"], g["away_team"]) }):
        by_pos["K"].append({
            "sleeper_player_id": f"K{idx}", "full_name": f"Kicker {team}", "position": "K", "team_abbr": team,
            "active": True, "availability_status": "HEALTHY", "depth_order": 1,
        })
    return by_pos


def test_week1_rankings_produce_exact_hidden_top_ten_and_visible_top_five():
    rankings = week1_rankings(_players(), _games())
    for pos in ("QB","RB","WR","TE","K"):
        assert len(rankings[pos]) == 10
        assert [r["slot_rank"] for r in rankings[pos]] == list(range(1,11))
        assert [r["is_visible"] for r in rankings[pos]][:5] == [True]*5
        assert [r["is_visible"] for r in rankings[pos]][5:] == [False]*5


def test_kicker_offenses_follow_implied_team_totals_when_odds_present():
    games = [
        {"home_team":"LAC","away_team":"LV","is_eligible":True,"over_under":52,"spread":-6,"favored_team":"LAC"},
        {"home_team":"DET","away_team":"NO","is_eligible":True,"over_under":49,"spread":-7,"favored_team":"DET"},
    ]
    order = week1_kicker_team_order(games)
    assert order[0] == "LAC"  # implied 29
    assert order[1] == "DET"  # implied 28
