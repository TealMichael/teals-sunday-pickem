from store import PICKEM_SCHEMA, SupabaseStore


class FakeSchemaClient:
    def __init__(self, options):
        self.options = options
        self.postgrest = object()
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return (name, self.options.schema)


def test_store_uses_explicit_pickem_schema_per_query(monkeypatch):
    import supabase
    monkeypatch.setattr(supabase, "create_client", lambda url, key, options: FakeSchemaClient(options))
    store = SupabaseStore("https://audit.invalid", "test-only-key")
    fake = store.client

    result = store._table("players")

    assert result == ("players", PICKEM_SCHEMA)
    assert fake.options.schema == PICKEM_SCHEMA
    assert fake.tables == ["players"]
