from datetime import datetime, timedelta, timezone

import pytest

from gate5 import (
    CommissionerError,
    clear_score_override,
    generate_pool_again,
    replace_pool_player,
    reset_player_pin,
    set_score_override,
    week_snapshot,
)
from security import verify_pin

UTC = timezone.utc


class FakeStore:
    def __init__(self):
        self.players = [
            {"id": "p1", "nickname": "Mike", "emoji": "🤘"},
            {"id": "p2", "nickname": "Jenny", "emoji": "🦅"},
        ]
        self.reset_args = None
        self.actions = []
        self.lineup_admin = [
            {**self.players[0], "pick_count": 5, "confirmed": True},
            {**self.players[1], "pick_count": 2, "confirmed": False},
        ]
        self.replaced = None
        self.score_set = None
        self.score_cleared = None

    def get_player_by_id(self, player_id):
        return next((p for p in self.players if p["id"] == player_id), None)

    def reset_player_pin(self, player_id, *, pin_salt, pin_hash, revoke_sessions):
        self.reset_args = (player_id, pin_salt, pin_hash, revoke_sessions)

    def record_commissioner_action(self, action, **kwargs):
        self.actions.append((action, kwargs))

    def get_registered_players(self):
        return list(self.players)

    def get_week_lineup_admin(self, week_id):
        return list(self.lineup_admin)

    def get_full_week_pool(self, week_id):
        return [
            {"id": "a", "position": "QB", "is_visible": True, "player_name": "A"},
            {"id": "b", "position": "QB", "is_visible": False, "player_name": "B"},
        ]

    def get_pool_usage(self, week_id, pool_player_id):
        return {"starter_count": 1, "backup_count": 0, "affected_lineups": 1, "affected_nicknames": ["Mike"]}

    def replace_visible_pool_player(self, week_id, *, outgoing_pool_id, replacement_pool_id, reason):
        self.replaced = (week_id, outgoing_pool_id, replacement_pool_id, reason)
        return {
            "position": "QB",
            "outgoing_name": "A",
            "replacement_name": "B",
            "affected_lineups": 1,
            "affected_nicknames": ["Mike"],
        }

    def set_manual_score_override(self, week_id, pool_player_id, score, note):
        self.score_set = (week_id, pool_player_id, score, note)
        return {"id": pool_player_id, "player_name": "A", "score_total": score}

    def clear_manual_score_override(self, week_id, pool_player_id):
        self.score_cleared = (week_id, pool_player_id)
        return {"id": pool_player_id, "player_name": "A", "score_total": 12.3}

    def get_week(self, week_id):
        return None


def _week(*, locked=False, published=True, opened=True, status="LIVE"):
    now = datetime.now(UTC)
    return {
        "id": "w1",
        "season": 2026,
        "nfl_week": 1,
        "opens_at": (now - timedelta(hours=1) if opened else now + timedelta(hours=1)).isoformat(),
        "locks_at": (now - timedelta(hours=1) if locked else now + timedelta(hours=1)).isoformat(),
        "published_at": now.isoformat() if published else None,
        "data_status": status,
    }


def test_pin_reset_hashes_with_normal_security_path_and_records_audit():
    store = FakeStore()
    reset_player_pin(store, player_id="p1", new_pin="2468", pin_confirm="2468", pin_pepper="pepper")
    assert store.reset_args is not None
    player_id, salt, digest, revoke = store.reset_args
    assert player_id == "p1"
    assert revoke is True
    assert verify_pin("2468", "pepper", salt, digest)
    assert store.actions[0][0] == "pin_reset"


def test_pin_reset_rejects_mismatch():
    with pytest.raises(CommissionerError):
        reset_player_pin(FakeStore(), player_id="p1", new_pin="2468", pin_confirm="1357", pin_pepper="pepper")


def test_week_snapshot_surfaces_incomplete_players():
    snapshot = week_snapshot(FakeStore(), _week())
    assert snapshot["registered"] == 2
    assert snapshot["ready"] == 1
    assert snapshot["incomplete"] == 1
    assert snapshot["needs_attention"][0]["nickname"] == "Jenny"


def test_pool_override_rejected_after_lock_and_allowed_before_lock():
    store = FakeStore()
    with pytest.raises(CommissionerError):
        replace_pool_player(store, _week(locked=True), outgoing_pool_id="a", replacement_pool_id="b", reason="wrong pool")
    result = replace_pool_player(store, _week(locked=False), outgoing_pool_id="a", replacement_pool_id="b", reason="wrong pool")
    assert result["replacement_name"] == "B"
    assert store.replaced is not None


def test_score_override_only_after_lock():
    store = FakeStore()
    with pytest.raises(CommissionerError):
        set_score_override(store, _week(locked=False), pool_player_id="a", score=14.2, note="provider fix")
    result = set_score_override(store, _week(locked=True), pool_player_id="a", score=14.2, note="provider fix")
    assert result["score_total"] == 14.2
    assert store.score_set[2] == 14.2


def test_clear_score_override_only_after_lock():
    store = FakeStore()
    with pytest.raises(CommissionerError):
        clear_score_override(store, _week(locked=False), pool_player_id="a")
    result = clear_score_override(store, _week(locked=True), pool_player_id="a")
    assert result["score_total"] == 12.3


def test_generate_again_refuses_early_or_already_published(monkeypatch):
    store = FakeStore()
    with pytest.raises(CommissionerError):
        generate_pool_again(store, _week(published=True, opened=True))
    with pytest.raises(CommissionerError):
        generate_pool_again(store, _week(published=False, opened=False))
