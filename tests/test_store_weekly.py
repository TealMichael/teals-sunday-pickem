from store import PICKEM_SCHEMA, SupabaseStore


class FakeSchemaClient:
    def __init__(self, options):
        self.options = options
        self.postgrest = object()
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return (name, self.options.schema)


def test_all_gate2_tables_still_route_explicitly_to_pickem_schema(monkeypatch):
    import supabase
    monkeypatch.setattr(supabase, "create_client", lambda url, key, options: FakeSchemaClient(options))
    store = SupabaseStore("https://audit.invalid", "test-only-key")
    fake = store.client
    for name in ["weeks", "player_pool", "lineups", "lineup_picks"]:
        assert store._table(name) == (name, PICKEM_SCHEMA)
    assert fake.options.schema == PICKEM_SCHEMA
    assert fake.tables == ["weeks", "player_pool", "lineups", "lineup_picks"]
