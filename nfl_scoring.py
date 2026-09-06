from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _num(stats: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        value = stats.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _whole(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


@dataclass(frozen=True)
class ScoreResult:
    points: float
    breakdown: dict[str, dict[str, Any]]


def score_stat_line(stats: Mapping[str, Any], position: str | None = None) -> ScoreResult:
    """Score one NFL stat line using Teal's Sunday Pick'em rules.

    The formula is position-agnostic on purpose: trick-play passing/rushing/
    receiving stats count for any selected player. Kicking is added whenever
    the stat line contains made FGs/XPs. Missed kicks have no penalty.
    """
    passing_yards = _num(stats, "passing_yards", "pass_yds")
    passing_tds = _num(stats, "passing_tds", "pass_td")
    interceptions = _num(stats, "interceptions", "passing_interceptions", "int")
    rushing_yards = _num(stats, "rushing_yards", "rush_yds")
    rushing_tds = _num(stats, "rushing_tds", "rush_td")
    receptions = _num(stats, "receptions", "rec")
    receiving_yards = _num(stats, "receiving_yards", "rec_yds")
    receiving_tds = _num(stats, "receiving_tds", "rec_td")
    fumbles_lost = _num(stats, "fumbles_lost", "fum_lost")
    if fumbles_lost == 0:
        fumbles_lost = (
            _num(stats, "sack_fumbles_lost")
            + _num(stats, "rushing_fumbles_lost")
            + _num(stats, "receiving_fumbles_lost")
        )
    two_point = (
        _num(stats, "two_point_conversions", "two_pt")
        + _num(stats, "passing_2pt_conversions")
        + _num(stats, "rushing_2pt_conversions")
        + _num(stats, "receiving_2pt_conversions")
    )
    # nflverse may expose kickoff/punt return TDs separately. ESPN live parsing
    # normalizes them to return_tds.
    return_tds = (
        _num(stats, "return_tds", "return_td")
        + _num(stats, "kickoff_return_tds")
        + _num(stats, "punt_return_tds")
        + _num(stats, "special_teams_tds")
    )
    fg_made = _num(stats, "field_goals_made", "fg_made")
    xp_made = _num(stats, "extra_points_made", "xp_made", "pat_made")

    components = [
        ("passing_yards", passing_yards, passing_yards / 25.0, "passing yds"),
        ("passing_tds", passing_tds, passing_tds * 4.0, "passing TD"),
        ("interceptions", interceptions, interceptions * -2.0, "INT thrown"),
        ("rushing_yards", rushing_yards, rushing_yards / 10.0, "rushing yds"),
        ("rushing_tds", rushing_tds, rushing_tds * 6.0, "rushing TD"),
        ("receptions", receptions, receptions * 0.5, "receptions"),
        ("receiving_yards", receiving_yards, receiving_yards / 10.0, "receiving yds"),
        ("receiving_tds", receiving_tds, receiving_tds * 6.0, "receiving TD"),
        ("fumbles_lost", fumbles_lost, fumbles_lost * -2.0, "fumbles lost"),
        ("two_point_conversions", two_point, two_point * 2.0, "2-pt conversion"),
        ("return_tds", return_tds, return_tds * 6.0, "return TD"),
        # Gate 3 kicker rule: every made FG is 3, regardless of distance.
        ("field_goals_made", fg_made, fg_made * 3.0, "FG made"),
        ("extra_points_made", xp_made, xp_made * 1.0, "XP made"),
    ]

    breakdown: dict[str, dict[str, Any]] = {}
    total = 0.0
    for key, stat_value, points, label in components:
        if stat_value == 0:
            continue
        points = round(float(points), 3)
        total += points
        breakdown[key] = {
            "stat": stat_value,
            "points": points,
            "label": label,
            "text": f"{_whole(stat_value)} {label} — {points:+.1f}",
        }

    return ScoreResult(points=round(total, 3), breakdown=breakdown)


def display_score(value: float | int | None) -> str:
    return f"{float(value or 0):.1f}"
