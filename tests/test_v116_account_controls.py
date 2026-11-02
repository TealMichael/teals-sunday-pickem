"""v1.0.16 account gate contracts. No live Supabase credentials needed."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from auth import login_player, register_player, restore_from_cookie
from store import SupabaseStore, StoreError


class Query:
    def __init__(self, records):
        self.records = records
        self.filters = []
        self.patch = None

    def select(self, *args, **kwargs):
        return self

    def update(self, values):
        self.patch = values
        return self

    def eq(self, name, value):
        self.filters.append((name, value))
        return self

    def in_(self, name, values):
        self.filters.append((name, tuple(values)))
        return self

    def limit(self, amount):
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        rows = [row for row in self.records if all(
            row.get(name) in value if isinstance(value, tuple) else row.get(name) == value
            for name, value in self.filters
        )]
        if self.patch is not None:
            for row in rows:
                row.update(self.patch)
        return SimpleNamespace(data=[dict(row) for row in rows])


def make_store():
    db = [
        {"id": str(uuid4()), "nickname": "Family", "account_status": "approved", "emoji": "🏈"},
        {"id": str(uuid4()), "nickname": "New", "account_status": "pending", "emoji": "🦆"},
        {"id": str(uuid4()), "nickname": "Removed", "account_status": "disabled", "emoji": "👾"},
    ]
    store = SupabaseStore.__new__(SupabaseStore)
    store._public_cache = {}
    store._table = lambda name: Query(db)
    return store, db


def test_only_approved_are_eligible_for_public_game_lists():
    store, db = make_store()
    listed = store.get_registered_players()
    assert [row["nickname"] for row in listed] == ["Family"]
    assert [row["nickname"] for row in store.list_pending_accounts()] == ["New"]
    assert store.get_account_status(db[2]["id"]) == "disabled"


def test_commissioner_approval_requires_pending_state():
    store, db = make_store()
    account = store.approve_player_account(db[1]["id"])
    assert account["account_status"] == "approved"
    assert account["approved_at"]
    assert {row["nickname"] for row in store.get_registered_players()} == {"Family", "New"}
    with pytest.raises(StoreError, match="no longer pending"):
        store.approve_player_account(db[1]["id"])


def test_removal_routes_through_atomic_rpc_not_player_table_delete():
    store, db = make_store()
    seen = []

    class Client:
        def rpc(self, name, params):
            seen.append((name, params))
            return SimpleNamespace(execute=lambda: SimpleNamespace(data="deleted"))

    store.client = Client()
    assert store.remove_player_account(db[1]["id"]) == "deleted"
    assert seen == [("commissioner_remove_account", {"p_player_id": db[1]["id"]})]


def test_migration_preserves_history_and_existing_accounts():
    migration = (Path(__file__).parents[1] / "db" / "015_commissioner_approval_accounts.sql").read_text()
    assert "default 'approved'" in migration
    assert "set default 'pending'" in migration
    assert "pickem.lineups where player_id" in migration
    assert "pickem.weekly_results where player_id" in migration
    assert "pickem.season_champions where player_id" in migration
    assert "player_sessions set revoked_at" in migration
    assert "commissioner_owner:v1" in migration
    assert "revoke all on function pickem.commissioner_remove_account" in migration
