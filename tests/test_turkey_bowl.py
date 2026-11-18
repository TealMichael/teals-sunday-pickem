"""Offline rules/architecture regression for the isolated Thanksgiving event."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from gate4 import build_season_standings, build_weekly_leaderboard
from turkey_bowl import TurkeyBowlError, is_locked, is_open, rank_thanksgiving_pool, thanksgiving_games

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
EVENT = {
    "season": 2026, "nfl_week": 12, "game_date": "2026-11-26",
    "opens_at": "2026-11-24T17:00:00+00:00", "locks_at": "2026-11-26T18:00:00+00:00",
    "published_at": "2026-11-24T17:00:10+00:00",
}


def game(home, away, date, game_id):
    return {"home_team": home, "away_team": away,
            "kickoff_at": f"{date}T18:00:00+00:00", "provider_event_id": game_id}


def all_games():
    return [game("LAR", "GB", "2026-11-25", "wednesday"),
            game("DET", "CHI", "2026-11-26", "first"),
            game("DAL", "PHI", "2026-11-26", "second"),
            game("BUF", "KC", "2026-11-26", "third"),
            game("PIT", "DEN", "2026-11-27", "friday")]


class TurkeyRules(unittest.TestCase):
    def test_thursday_filter_excludes_wednesday_and_friday(self):
        result = thanksgiving_games(EVENT, all_games())
        self.assertEqual({g["provider_event_id"] for g in result}, {"first", "second", "third"})

    def test_wrong_three_games_fail_closed(self):
        samples = [all_games()[:3], all_games()[1:3],
                   [game("DET", "CHI", "2026-11-26", "a") for _ in range(3)]]
        for bad in samples:
            with self.subTest(bad=bad), self.assertRaises(TurkeyBowlError):
                thanksgiving_games(EVENT, bad)

    def test_opening_and_lock_are_strict(self):
        just_before = datetime.fromisoformat(EVENT["opens_at"]) - timedelta(microseconds=1)
        opening = datetime.fromisoformat(EVENT["opens_at"])
        just_before_lock = datetime.fromisoformat(EVENT["locks_at"]) - timedelta(microseconds=1)
        lock = datetime.fromisoformat(EVENT["locks_at"])
        self.assertFalse(is_open(EVENT, just_before))
        self.assertTrue(is_open(EVENT, opening))
        self.assertTrue(is_open(EVENT, just_before_lock))
        self.assertFalse(is_open(EVENT, lock))
        self.assertTrue(is_locked(EVENT, lock))
        self.assertFalse(is_locked(EVENT, just_before_lock))

    def test_pool_succeeds_with_only_six_holiday_kickers(self):
        games = thanksgiving_games(EVENT, all_games())
        team_list = ["DET", "CHI", "DAL", "PHI", "BUF", "KC"]
        players = {}
        for pos in ("QB", "RB", "WR", "TE", "K"):
            players[pos] = [
                {"full_name": f"{pos} Player {i}", "sleeper_player_id": f"{pos}-{i}",
                 "team_abbr": t, "position": pos, "depth_order": 1, "active": True,
                 "availability_status": "HEALTHY"}
                for i, t in enumerate(team_list)
            ]
        ranked = rank_thanksgiving_pool(players, [], games, 12)
        self.assertEqual({p: len(ranked[p]) for p in ranked}, {p: 6 for p in players})
        for pos in players:
            self.assertEqual(len([r for r in ranked[pos] if r["is_visible"]]), 5)
            self.assertEqual([r["slot_rank"] for r in ranked[pos]], list(range(1, 7)))
        self.assertEqual({r["team_abbr"] for r in ranked["K"]}, set(team_list))

    def test_missing_fifth_healthy_kicker_blocks_publication(self):
        games = thanksgiving_games(EVENT, all_games())
        team_list = ["DET", "CHI", "DAL", "PHI", "BUF", "KC"]
        players = {
            pos: [{"full_name": f"{pos} {i}", "team_abbr": t, "position": pos,
                   "availability_status": "OUT" if pos == "K" and i < 2 else "HEALTHY",
                   "sleeper_player_id": f"{pos}-{i}"}
                  for i, t in enumerate(team_list)]
            for pos in ("QB", "RB", "WR", "TE", "K")
        }
        with self.assertRaisesRegex(TurkeyBowlError, "K has only 4"):
            rank_thanksgiving_pool(players, [], games, 12)

    def test_full_round_points_and_tie_break_are_additive_not_double_counted(self):
        regular = [
            dict(player_id="a", nickname_snapshot="Alpha", emoji_snapshot="🏈", season_points=12, weekly_score=20,
                 finish_rank=1),
            dict(player_id="b", nickname_snapshot="Beta", emoji_snapshot="🏈", season_points=9, weekly_score=23,
                 finish_rank=2),
        ]
        extra = [
            dict(player_id="a", nickname_snapshot="Alpha", emoji_snapshot="🏈", season_points=12, weekly_score=18,
                 finish_rank=1, is_special_event=True),
            dict(player_id="b", nickname_snapshot="Beta", emoji_snapshot="🏈", season_points=12, weekly_score=18,
                 finish_rank=1, is_special_event=True),
        ]
        standings = build_season_standings(regular + extra)
        self.assertEqual([(p["player_id"], p["season_points"]) for p in standings], [("a", 24), ("b", 21)])
        self.assertEqual(standings[0]["total_fantasy_points"], 38.0)
        self.assertEqual(standings[1]["total_fantasy_points"], 41.0)

    def test_same_week_same_person_results_stay_separate(self):
        # Distinct Sunday/week result and Thanksgiving/event result IDs prevent
        # replacing Week 12's Sunday result in the standings.
        sunday = {"week_id": "sunday12", "player_id": "a", "season_points": 12, "weekly_score": 30}
        turkey = {"event_id": "turkey12", "player_id": "a", "season_points": 9, "weekly_score": 22}
        self.assertNotEqual(sunday.get("week_id"), turkey.get("event_id"))
        self.assertEqual(build_season_standings([sunday, turkey])[0]["season_points"], 21)

    def test_tied_turkey_bowl_champions_both_get_first_place(self):
        pool = [{"id": f"p{i}", "position": pos, "player_name": pos, "score_total": 10,
                 "availability_status": "HEALTHY"} for i, pos in enumerate(("QB", "RB", "WR", "TE", "K"))]
        bundle = {"players": [{"id": "a", "nickname": "Alpha", "emoji": "🏈"},
                              {"id": "b", "nickname": "Beta", "emoji": "🏈"}],
                  "lineups": [{"id": "la", "player_id": "a", "confirmed_at": "2026-11-26"},
                              {"id": "lb", "player_id": "b", "confirmed_at": "2026-11-26"}],
                  "pool": pool, "games": [], "picks": [
                      {"lineup_id": lid, "position": pos, "pool_player_id": f"p{i}"}
                      for lid in ("la", "lb") for i, pos in enumerate(("QB", "RB", "WR", "TE", "K"))]}
        scores = build_weekly_leaderboard(bundle)
        self.assertEqual([(r["rank"], r["season_points_if_final"]) for r in scores], [(1, 12), (1, 12)])

    def test_trophy_previous_season_only(self):
        # Repository-facing badge lookup is deliberately year-1, not year.
        from turkey_bowl import TurkeyBowlService
        class Fake(TurkeyBowlService):
            def results(self, *, season=None):
                self.requested_season = season
                return [{"player_id": "winner", "is_champion": True},
                        {"player_id": "second", "is_champion": False}]
        fake = Fake(None)
        self.assertEqual(fake.next_season_champions(2027), {"winner"})
        self.assertEqual(fake.requested_season, 2026)

    def test_privacy_gate_on_public_bundle(self):
        from turkey_bowl import TurkeyBowlService
        fake = TurkeyBowlService(None)
        with self.assertRaises(TurkeyBowlError):
            fake.public_bundle(EVENT)   # No DB access should occur before lock.

    def test_migration_contains_no_mutations_of_sunday_tables(self):
        sql = (ROOT / "db/018_turkey_bowl.sql").read_text()
        for table in ("weeks", "player_pool", "lineups", "lineup_picks", "weekly_results"):
            for operation in ("UPDATE", "ALTER TABLE", "DROP TABLE", "DELETE FROM"):
                self.assertNotIn(f"{operation} pickem.{table}", sql)
        self.assertIn("CREATE TRIGGER trg_guard_special_pick", sql)
        self.assertIn("CREATE TRIGGER trg_guard_special_lineup", sql)
        self.assertIn("now() >= ev.locks_at", sql)
        self.assertIn("ON CONFLICT (event_type,season) DO NOTHING", sql)

    def test_independent_worker_not_sunday(self):
        worker = (ROOT / ".github/workflows/turkey-bowl.yml").read_text()
        self.assertIn("python scripts/turkey_refresh.py", worker)
        self.assertIn("group: pickem-turkey-bowl", worker)
        self.assertIn("SUPABASE_SECRET_KEY", worker)
        self.assertNotIn("clock", worker.lower())


if __name__ == "__main__":
    unittest.main()
