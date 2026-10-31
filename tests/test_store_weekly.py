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
        from refresh_protocol import ProtectedTable
        routed = store._table(name)
        if isinstance(routed, ProtectedTable):
            assert routed.store is store and routed.name == name
            routed = routed.store.client.table(routed.name)
        assert routed == (name, PICKEM_SCHEMA)
    assert fake.options.schema == PICKEM_SCHEMA
    assert fake.tables == ["weeks", "player_pool", "lineups", "lineup_picks"]
