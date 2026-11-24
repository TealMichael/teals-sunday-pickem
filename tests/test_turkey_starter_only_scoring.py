"""Guard against Thanksgiving backup activation while preserving Sunday's scoring."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from gate4 import build_weekly_leaderboard
from turkey_bowl import TurkeyBowlService


class Chain:
    def __init__(self, rows):
        self.rows = list(rows)
        self.data = None

    def select(self, *_args, **_kwargs): return self
    def eq(self, *_args, **_kwargs): return self
    def in_(self, *_args, **_kwargs): return self
    def limit(self, *_args, **_kwargs): return self
    def execute(self):
        self.data = list(self.rows)
        return self


class FakeTurkey(TurkeyBowlService):
    def __init__(self, data):
        self.data = data
        self.published = []

    def table(self, name): return Chain(self.data.get(name, []))
    def pool(self, event_id, *, visible_only=False): return list(self.data["special_pool"])
    def games(self, event_id): return []


def sample():
    picks = [dict(id="pick", lineup_id="l", position="QB", pool_player_id="qb-out",
                  emergency_pool_player_id="qb-backup")]
    pool = [dict(id="qb-out", position="QB", player_name="Starter", team_abbr="CHI",
                 availability_status="OUT", score_total=0),
            dict(id="qb-backup", position="QB", player_name="Backup", team_abbr="DET",
                 availability_status="HEALTHY", score_total=40)]
    return dict(special_lineups=[dict(id="l", event_id="turkey", player_id="p", confirmed_at="confirmed")],
                special_picks=picks,
                players=[dict(id="p", nickname="Player", emoji="🏈")], special_pool=pool)


def test_legacy_backup_is_ignored_when_turkey_bundle_is_built():
    service = FakeTurkey(sample())
    event = {"id": "turkey", "locks_at": "2020-11-26T18:00:00+00:00"}
    bundle = service.public_bundle(event)
    assert all("emergency_pool_player_id" not in p for p in bundle["picks"])
    scores = build_weekly_leaderboard(bundle)
    assert scores[0]["score"] == 0  # Not the old backup's 40 points!
    assert scores[0]["roster"][0]["player"]["player_name"] == "Starter"
    assert scores[0]["roster"][0]["emergency_activated"] is False


def test_regular_sunday_scoring_still_activates_its_own_backups():
    data = sample()
    bundle = dict(lineups=data["special_lineups"], picks=data["special_picks"],
                  pool=data["special_pool"], players=data["players"], games=[])
    scores = build_weekly_leaderboard(bundle)
    assert scores[0]["score"] == 40  # Sunday code unchanged
    assert scores[0]["roster"][0]["emergency_activated"] is True


def test_turkey_confirmation_does_not_require_backups():
    from unittest.mock import Mock
    class ConfirmFake(TurkeyBowlService):
        def __init__(self): self.updates = []
        def lineup(self, event_id, player_id):
            return dict(id="l"), [dict(position=p, pool_player_id=f"{p}-starter")
                                  for p in ("QB", "RB", "WR", "TE", "K")]
        def table(self, name):
            assert name == "special_lineups"
            fake = Mock()
            fake.update.return_value.eq.return_value.execute.return_value = None
            self.updates.append(fake)
            return fake
    svc = ConfirmFake()
    svc.confirm({"id": "turkey", "opens_at": "2020-11-24T17:00:00+00:00",
                 "locks_at": "2099-11-26T18:00:00+00:00", "published_at": "2020-11-24T18:00:00+00:00"}, "p")
    assert svc.updates and svc.updates[-1].update.called


def test_no_changes_to_sunday_scorer_source():
    # Turkey-only normalization is in its own module; never patch gate4.
    service_src = Path("turkey_bowl.py").read_text()
    assert '"pool_player_id")' in service_src
    assert "starter_only_picks" in service_src
    assert "build_weekly_leaderboard(self.public_bundle(event))" in service_src


def test_edit_of_existing_turkey_starter_explicitly_clears_old_backup():
    class WriteTable:
        def __init__(self, owner, name): self.owner, self.name = owner, name
        def upsert(self, payload, **kw):
            self.owner.writes.append((self.name, payload, kw))
            return self
        def update(self, payload):
            self.owner.writes.append((self.name, payload, {}))
            return self
        def eq(self, *args): return self
        def execute(self): return type('Result', (), {'data': []})()
    class Writer(TurkeyBowlService):
        def __init__(self): self.writes=[]
        def lineup(self, event_id, player_id): return ({'id':'lineup'}, [])
        def table(self, name): return WriteTable(self, name)
    service = Writer()
    event = {'id':'turkey', 'opens_at':'2020-11-24T17:00:00+00:00',
             'locks_at':'2099-11-26T18:00:00+00:00', 'published_at':'2020-11-24T18:00:00+00:00'}
    service.save_pick(event, 'player', 'QB', 'new-starter')
    pick = [payload for table, payload, kw in service.writes if table == 'special_picks'][0]
    assert pick['pool_player_id'] == 'new-starter'
    assert pick['emergency_pool_player_id'] is None
    assert len([p for table,p,kw in service.writes if table == 'special_picks']) == 1
