from nfl_scoring import display_score, score_stat_line


def test_half_ppr_core_scoring_is_fractional():
    result = score_stat_line({
        "passing_yards": 250,
        "passing_tds": 2,
        "interceptions": 1,
        "rushing_yards": 37,
        "rushing_tds": 1,
        "receptions": 4,
        "receiving_yards": 25,
        "receiving_tds": 1,
        "fumbles_lost": 1,
        "passing_2pt_conversions": 1,
    })
    # 10 + 8 -2 +3.7 +6 +2 +2.5 +6 -2 +2
    assert result.points == 36.2
    assert display_score(result.points) == "36.2"


def test_kicker_flat_field_goal_rule_ignores_distance():
    result = score_stat_line({"fg_made": 4, "pat_made": 3}, "K")
    assert result.points == 15.0
    assert result.breakdown["field_goals_made"]["points"] == 12.0
    assert result.breakdown["extra_points_made"]["points"] == 3.0


def test_missed_kicks_do_not_create_negative_points():
    result = score_stat_line({"fg_made": 1, "fg_missed": 4, "pat_made": 1, "pat_missed": 2}, "K")
    assert result.points == 4.0


def test_nonstandard_stats_count_for_any_position():
    result = score_stat_line({"passing_yards": 25, "passing_tds": 1, "special_teams_tds": 1}, "WR")
    assert result.points == 11.0


def test_nflverse_split_fumbles_are_combined():
    result = score_stat_line({"sack_fumbles_lost": 1, "rushing_fumbles_lost": 1, "receiving_fumbles_lost": 1})
    assert result.points == -6.0
